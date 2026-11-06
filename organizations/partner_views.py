"""Partnyor şirkətlər (təşkilatlarla many-to-many).

GET/POST         /api/organizations/partners/?q=&organization=
GET/PATCH/DELETE /api/organizations/partners/<pk>/
GET              /api/organizations/<id>/partners/          - yalnız həmin təşkilatın partnyorları
POST             /api/organizations/<id>/partners/          - {"partner_ids": [..]} təşkilata təyin et
DELETE           /api/organizations/<id>/partners/<pid>/    - təyinatı götür

Yazma yalnız Nazirlik admini üçündür; oxuma - istifadəçinin görünürlük dairəsindəki təşkilatların
partnyorları. Hər dəyişiklik audit jurnalına yazılır.
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.utils import get_client_ip, log_security_event

from .models import Organization, PartnerCompany
from .permissions import is_full_admin, scoped_organization_ids
from .profile_views import get_visible_organization


def _need_admin(user):
    if not is_full_admin(user):
        raise PermissionDenied("Bu əməliyyat yalnız Nazirlik admini üçündür.")


def _log(request, event, extra):
    log_security_event(event, user=request.user, ip=get_client_ip(request) or "", extra=extra)


def _snapshot(p):
    return {
        "ad": p.name, "voen": p.voen, "olke": p.country, "unvan": p.address, "elaqe_sexsi": p.contact_person,
        "telefon": p.phone, "email": p.email, "qeyd": p.note, "aktiv": p.is_active,
        "teskilatlar": sorted(p.organizations.values_list("full_name", flat=True)),
    }


def _diff(before, after):
    return "; ".join(f"{k}: {before[k]!r} -> {after[k]!r}" for k in after if before.get(k) != after[k]) or "dəyişiklik yoxdur"


def visible_partners(user):
    qs = PartnerCompany.objects.prefetch_related("organizations")
    if is_full_admin(user):
        return qs
    ids = scoped_organization_ids(user)
    if ids is None:
        return qs
    return qs.filter(organizations__id__in=ids).distinct()


class PartnerSerializer(serializers.ModelSerializer):
    organizations = serializers.SerializerMethodField()
    organization_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Organization.objects.all(), source="organizations", required=False, write_only=True,
    )

    class Meta:
        model = PartnerCompany
        fields = [
            "id", "name", "voen", "country", "address", "contact_person", "phone", "email", "note",
            "is_active", "organizations", "organization_ids", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_organizations(self, obj):
        return [{"id": o.id, "name": o.full_name} for o in obj.organizations.all()]

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Şirkətin adı boş ola bilməz.")
        return value.strip()

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
        qs = qs.filter(Q(name__icontains=q) | Q(voen__icontains=q) | Q(country__icontains=q))
    org = params.get("organization")
    if org and org.isdigit():
        qs = qs.filter(organizations__id=int(org))
    return qs.distinct()


class PartnerListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(PartnerSerializer(_filter(visible_partners(request.user), request.query_params), many=True).data)

    def post(self, request):
        _need_admin(request.user)
        ser = PartnerSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        _log(request, "PARTNER_CREATED", f"id={obj.id} {_snapshot(obj)}")
        return Response(ser.data, status=201)


class PartnerDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, pk):
        return get_object_or_404(visible_partners(request.user), pk=pk)

    def get(self, request, pk):
        return Response(PartnerSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _need_admin(request.user)
        obj = self._get(request, pk)
        before = _snapshot(obj)
        ser = PartnerSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        obj = PartnerCompany.objects.get(pk=pk)
        _log(request, "PARTNER_UPDATED", f"id={obj.id} {_diff(before, _snapshot(obj))}")
        return Response(PartnerSerializer(obj).data)

    def delete(self, request, pk):
        _need_admin(request.user)
        obj = self._get(request, pk)
        snap, obj_id = _snapshot(obj), obj.id
        obj.delete()
        _log(request, "PARTNER_DELETED", f"id={obj_id} {snap}")
        return Response(status=204)


class OrganizationPartnerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        org = get_visible_organization(request, pk)
        qs = _filter(PartnerCompany.objects.filter(organizations=org).prefetch_related("organizations"),
                     request.query_params)
        return Response(PartnerSerializer(qs, many=True).data)

    def post(self, request, pk):
        _need_admin(request.user)
        org = get_object_or_404(Organization, pk=pk)
        ids = request.data.get("partner_ids") or []
        if not isinstance(ids, list):
            raise ValidationError({"partner_ids": "Siyahı göndərin."})
        items = PartnerCompany.objects.filter(pk__in=ids)
        org.partner_companies.add(*items)
        _log(request, "PARTNER_ASSIGNED", f"teşkilat={org.full_name!r} (id={org.id}) partnyorlar={[i.name for i in items]}")
        return Response({"assigned": items.count()}, status=201)


class OrganizationPartnerUnassignView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, partner_id):
        _need_admin(request.user)
        org = get_object_or_404(Organization, pk=pk)
        item = get_object_or_404(PartnerCompany, pk=partner_id)
        org.partner_companies.remove(item)
        _log(request, "PARTNER_UNASSIGNED", f"teşkilat={org.full_name!r} (id={org.id}) partnyor={item.name!r} (id={item.id})")
        return Response(status=204)
