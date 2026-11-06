"""Nomenklatura (ümumi kataloq + təşkilatlara many-to-many təyinat).

Kataloqlar (autocomplete üçün, əvvəlcədən yaradılır):
GET/POST   /api/organizations/nomenclature-catalog/categories/?search=
GET/POST   /api/organizations/nomenclature-catalog/subcategories/?category=<id>&search=
GET/POST   /api/organizations/nomenclature-catalog/operation-types/?search=
DELETE     /api/organizations/nomenclature-catalog/<categories|subcategories|operation-types>/<pk>/

Nomenklatura:
GET/POST   /api/organizations/nomenclatures/?q=&operation_type=&category=&subcategory=&organization=
GET/PATCH/DELETE /api/organizations/nomenclatures/<pk>/
GET        /api/organizations/<id>/nomenclature/?search=   - YALNIZ həmin təşkilata təyin olunmuşlar
POST       /api/organizations/<id>/nomenclature/           - {"nomenclature_ids": [..]} təşkilata təyin et
DELETE     /api/organizations/<id>/nomenclature/<nid>/     - təyinatı götür

Yazma əməliyyatları yalnız Nazirlik admini (staff/superuser) üçündür. Oxuma: hər istifadəçi öz
görünürlük dairəsindəki təşkilatlara təyin olunmuş nomenklaturaları görür.
"""
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.utils import get_client_ip, log_security_event

from .models import (
    Nomenclature, NomenclatureCategory, NomenclatureOperationType, NomenclatureSubcategory, Organization,
)
from .permissions import is_full_admin, scoped_organization_ids
from .profile_views import get_visible_organization

DEFAULT_OPERATION_TYPES = ["İdxal", "İxrac", "ƏDV azad olma", "Satış", "İstehsal"]


def _need_admin(user):
    if not is_full_admin(user):
        raise PermissionDenied("Bu əməliyyat yalnız Nazirlik admini üçündür.")


def _log(request, event, extra):
    """Nomenklaturada hər əlavə/dəyişiklik/silmə audit jurnalına (audit.AuditLog) yazılır."""
    log_security_event(event, user=request.user, ip=get_client_ip(request) or "", extra=extra)


def _snapshot(n):
    return {
        "ad": n.name, "emeliyyat_novu": n.operation_type.name, "kateqoriya": n.category.name,
        "alt_kateqoriya": n.subcategory.name if n.subcategory_id else "", "olcu_vahidi": n.unit,
        "qeyd": n.note, "teskilatlar": sorted(n.organizations.values_list("full_name", flat=True)),
    }


def _diff(before, after):
    return "; ".join(f"{k}: {before[k]!r} -> {after[k]!r}" for k in after if before.get(k) != after[k]) or "dəyişiklik yoxdur"


def visible_nomenclatures(user):
    qs = Nomenclature.objects.select_related("operation_type", "category", "subcategory") \
        .prefetch_related("organizations")
    if is_full_admin(user):
        return qs
    ids = scoped_organization_ids(user)
    if ids is None:
        return qs
    return qs.filter(organizations__id__in=ids).distinct()


class NomenclatureSerializer(serializers.ModelSerializer):
    operation_type_name = serializers.CharField(source="operation_type.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    subcategory_name = serializers.SerializerMethodField()
    organizations = serializers.SerializerMethodField()
    organization_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Organization.objects.all(), source="organizations", required=False, write_only=True,
    )

    class Meta:
        model = Nomenclature
        fields = [
            "id", "operation_type", "operation_type_name", "category", "category_name",
            "subcategory", "subcategory_name", "name", "unit", "note",
            "organizations", "organization_ids", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_subcategory_name(self, obj):
        return obj.subcategory.name if obj.subcategory_id else ""

    def get_organizations(self, obj):
        return [{"id": o.id, "name": o.full_name} for o in obj.organizations.all()]

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Məhsulun adı boş ola bilməz.")
        return value.strip()

    def validate(self, attrs):
        category = attrs.get("category") or getattr(self.instance, "category", None)
        sub = attrs.get("subcategory", getattr(self.instance, "subcategory", None))
        if sub and category and sub.category_id != category.id:
            raise serializers.ValidationError({"subcategory": "Alt kateqoriya seçilmiş kateqoriyaya aid deyil."})
        return attrs

    def create(self, validated_data):
        orgs = validated_data.pop("organizations", [])
        obj = super().create(validated_data)
        obj.organizations.set(orgs)
        return obj

    def update(self, instance, validated_data):
        orgs = validated_data.pop("organizations", None)
        obj = super().update(instance, validated_data)
        if orgs is not None:
            obj.organizations.set(orgs)
        return obj


def _filter(qs, params):
    q = (params.get("q") or params.get("search") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(note__icontains=q))
    for key, field in (("operation_type", "operation_type_id"), ("category", "category_id"),
                       ("subcategory", "subcategory_id")):
        val = params.get(key)
        if val and val.isdigit():
            qs = qs.filter(**{field: int(val)})
    org = params.get("organization")
    if org and org.isdigit():
        qs = qs.filter(organizations__id=int(org))
    return qs.distinct()


class NomenclatureListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = _filter(visible_nomenclatures(request.user), request.query_params)
        return Response(NomenclatureSerializer(qs, many=True).data)

    def post(self, request):
        _need_admin(request.user)
        ser = NomenclatureSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        _log(request, "NOMENCLATURE_CREATED", f"id={obj.id} {_snapshot(obj)}")
        return Response(ser.data, status=201)


class NomenclatureDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, pk):
        return get_object_or_404(visible_nomenclatures(request.user), pk=pk)

    def get(self, request, pk):
        return Response(NomenclatureSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _need_admin(request.user)
        obj = self._get(request, pk)
        before = _snapshot(obj)
        ser = NomenclatureSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        obj = Nomenclature.objects.get(pk=obj.pk)
        _log(request, "NOMENCLATURE_UPDATED", f"id={obj.id} {_diff(before, _snapshot(obj))}")
        return Response(ser.data)

    def delete(self, request, pk):
        _need_admin(request.user)
        obj = self._get(request, pk)
        snap = _snapshot(obj)
        obj_id = obj.id
        obj.delete()
        _log(request, "NOMENCLATURE_DELETED", f"id={obj_id} {snap}")
        return Response(status=204)


# ------------------------------------------------------------------ Kataloqlar

class CatalogView(APIView):
    """Kateqoriya / alt kateqoriya / əməliyyat növü üçün ortaq siyahı + yaratma (ada görə təkrarsız)."""
    permission_classes = [permissions.IsAuthenticated]
    kind = None  # 'categories' | 'subcategories' | 'operation-types'

    def _serialize(self, obj):
        data = {"id": obj.id, "name": obj.name}
        if self.kind == "subcategories":
            data.update(category=obj.category_id, category_name=obj.category.name)
        return data

    def _queryset(self, request):
        if self.kind == "categories":
            qs = NomenclatureCategory.objects.all()
        elif self.kind == "subcategories":
            qs = NomenclatureSubcategory.objects.select_related("category")
            cat = request.query_params.get("category")
            if cat and cat.isdigit():
                qs = qs.filter(category_id=int(cat))
        else:
            qs = NomenclatureOperationType.objects.all()
        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get(self, request):
        return Response([self._serialize(o) for o in self._queryset(request)])

    def post(self, request):
        _need_admin(request.user)
        name = " ".join(str(request.data.get("name") or "").split())
        if not name:
            raise ValidationError({"name": "Ad boş ola bilməz."})
        if self.kind == "categories":
            obj = NomenclatureCategory.objects.filter(name__iexact=name).first() \
                or NomenclatureCategory.objects.create(name=name)
        elif self.kind == "subcategories":
            cat_id = request.data.get("category")
            category = NomenclatureCategory.objects.filter(pk=cat_id).first() if str(cat_id or "").isdigit() else None
            if not category:
                raise ValidationError({"category": "Əvvəlcə kateqoriyanı seçin."})
            obj = NomenclatureSubcategory.objects.filter(category=category, name__iexact=name).first() \
                or NomenclatureSubcategory.objects.create(category=category, name=name)
        else:
            obj = NomenclatureOperationType.objects.filter(name__iexact=name).first() \
                or NomenclatureOperationType.objects.create(name=name)
        _log(request, "NOMENCLATURE_CATALOG_CREATED", f"{self.kind}: id={obj.id} ad={obj.name!r}")
        return Response(self._serialize(obj), status=201)


class CatalogDetailView(CatalogView):
    def _model(self):
        return {"categories": NomenclatureCategory, "subcategories": NomenclatureSubcategory,
                "operation-types": NomenclatureOperationType}[self.kind]

    def delete(self, request, pk):
        _need_admin(request.user)
        obj = get_object_or_404(self._model(), pk=pk)
        label = f"{self.kind}: id={obj.id} ad={obj.name!r}"
        try:
            obj.delete()
        except ProtectedError:
            raise ValidationError({"detail": "Bu qeyd nomenklaturada istifadə olunur, silmək olmaz."})
        _log(request, "NOMENCLATURE_CATALOG_DELETED", label)
        return Response(status=204)


# ------------------------------------------------------- Təşkilatın nomenklaturası

class OrganizationNomenclatureView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        org = get_visible_organization(request, pk)
        qs = _filter(
            Nomenclature.objects.filter(organizations=org)
            .select_related("operation_type", "category", "subcategory").prefetch_related("organizations"),
            request.query_params,
        )
        return Response(NomenclatureSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request, pk):
        _need_admin(request.user)
        org = get_object_or_404(Organization, pk=pk)
        ids = request.data.get("nomenclature_ids") or []
        if not isinstance(ids, list):
            raise ValidationError({"nomenclature_ids": "Siyahı göndərin."})
        items = Nomenclature.objects.filter(pk__in=ids)
        org.nomenclatures.add(*items)
        _log(request, "NOMENCLATURE_ASSIGNED",
             f"teşkilat={org.full_name!r} (id={org.id}) nomenklaturalar={[i.name for i in items]}")
        return Response({"assigned": items.count()}, status=201)


class OrganizationNomenclatureUnassignView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, nomenclature_id):
        _need_admin(request.user)
        org = get_object_or_404(Organization, pk=pk)
        item = get_object_or_404(Nomenclature, pk=nomenclature_id)
        org.nomenclatures.remove(item)
        _log(request, "NOMENCLATURE_UNASSIGNED", f"teşkilat={org.full_name!r} (id={org.id}) nomenklatura={item.name!r} (id={item.id})")
        return Response(status=204)
