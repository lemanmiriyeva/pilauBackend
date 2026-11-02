"""Təşkilat səhifəsi: Tabeli qurumlar və Əsas avadanlıqlar.

GET/POST   /api/organizations/<id>/subordinates/        PATCH/DELETE /api/organizations/subordinates/<pk>/
GET/POST   /api/organizations/<id>/equipment/           PATCH/DELETE /api/organizations/equipment/<pk>/
  POST equipment: tək {name, inventory_code, group?} VƏ YA qrup halında
  {name, group?, inventory_codes: "K1, K2\nK3"} VƏ YA aralıq {name, group?, prefix, start, end}.

Tabeli qurumu YALNIZ həmin təşkilatın admini idarə edir; avadanlığı isə can_org_action
('Təşkilatlar' modulu icazələri) ilə təşkilat adminləri/icazəli işçilər.
"""
import re

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FixedAsset, SubordinateInstitution
from .permissions import is_org_admin
from .profile_views import can_org_action, get_visible_organization


def _can_manage_subordinates(user, org) -> bool:
    return bool(is_org_admin(user) and user.organization_id == org.id)


class SubordinateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubordinateInstitution
        fields = ["id", "name", "voen", "address", "director_name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, v):
        if not v.strip():
            raise serializers.ValidationError("Ad məcburidir.")
        return v.strip()

    def validate_voen(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("VÖEN məcburidir.")
        return v


class OrganizationSubordinatesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        org = get_visible_organization(request, pk)
        items = org.subordinates.all()
        return Response({
            "can_manage": _can_manage_subordinates(request.user, org),
            "results": SubordinateSerializer(items, many=True).data,
        })

    def post(self, request, pk):
        org = get_visible_organization(request, pk)
        if not _can_manage_subordinates(request.user, org):
            raise PermissionDenied("Tabeli qurumu yalnız təşkilatın admini əlavə edə bilər.")
        s = SubordinateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                s.save(organization=org)
        except IntegrityError:
            raise ValidationError({"voen": "Bu VÖEN ilə tabeli qurum artıq əlavə olunub."})
        return Response(s.data, status=201)


class OrganizationSubordinateDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, pk):
        item = get_object_or_404(SubordinateInstitution, pk=pk)
        org = get_visible_organization(request, item.organization_id)
        if not _can_manage_subordinates(request.user, org):
            raise PermissionDenied("Tabeli qurumu yalnız təşkilatın admini dəyişə bilər.")
        return item

    def patch(self, request, pk):
        item = self._get(request, pk)
        s = SubordinateSerializer(item, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                s.save()
        except IntegrityError:
            raise ValidationError({"voen": "Bu VÖEN ilə tabeli qurum artıq əlavə olunub."})
        return Response(s.data)

    def delete(self, request, pk):
        self._get(request, pk).delete()
        return Response(status=204)


class FixedAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = FixedAsset
        fields = ["id", "name", "inventory_code", "group", "note", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, v):
        if not v.strip():
            raise serializers.ValidationError("Avadanlığın adı məcburidir.")
        return v.strip()

    def validate_inventory_code(self, v):
        if not v.strip():
            raise serializers.ValidationError("İnventar kodu məcburidir.")
        return v.strip()


def _codes_from_request(data):
    """Qrup halında əlavə: siyahı/mətn (vergül, nöqtəli vergül, yeni sətir) və ya prefix+start+end aralığı."""
    raw = data.get("inventory_codes")
    if raw:
        if isinstance(raw, str):
            raw = re.split(r"[,;\n\r]+", raw)
        return [c.strip() for c in raw if str(c).strip()]
    prefix, start, end = data.get("prefix"), data.get("start"), data.get("end")
    if start not in (None, "") and end not in (None, ""):
        s, e = str(start).strip(), str(end).strip()
        if not (s.isdigit() and e.isdigit()):
            raise ValidationError({"start": "Aralıq yalnız rəqəmlərdən ibarət olmalıdır."})
        a, b = int(s), int(e)
        if b < a or b - a >= 1000:
            raise ValidationError({"end": "Aralıq düzgün deyil (ən çox 1000 kod)."})
        width = len(s)
        return [f"{prefix or ''}{str(i).zfill(width)}" for i in range(a, b + 1)]
    return []


class OrganizationEquipmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        org = get_visible_organization(request, pk)
        items = org.fixed_assets.all()
        search = (request.query_params.get("search") or "").strip()
        group = request.query_params.get("group")
        if search:
            items = items.filter(Q(name__icontains=search) | Q(inventory_code__icontains=search))
        if group is not None and group != "":
            items = items.filter(group="" if group == "__none__" else group)
        groups = sorted(set(org.fixed_assets.exclude(group="").values_list("group", flat=True)))
        return Response({"results": FixedAssetSerializer(items, many=True).data, "groups": groups})

    @transaction.atomic
    def post(self, request, pk):
        org = get_visible_organization(request, pk)
        if not can_org_action(request.user, org, "create"):
            raise PermissionDenied("Avadanlıq əlavə etmək üçün 'Yaratma' icazəniz yoxdur.")
        name = (request.data.get("name") or "").strip()
        group = (request.data.get("group") or "").strip()
        if not name:
            raise ValidationError({"name": "Avadanlığın adı məcburidir."})
        codes = _codes_from_request(request.data)
        if codes:  # qrup halında əlavə
            existing = set(org.fixed_assets.filter(inventory_code__in=codes).values_list("inventory_code", flat=True))
            seen, new = set(), []
            for c in codes:
                if c in existing or c in seen:
                    continue
                seen.add(c)
                new.append(FixedAsset(organization=org, name=name, inventory_code=c, group=group))
            FixedAsset.objects.bulk_create(new)
            return Response({"created": len(new), "skipped": len(codes) - len(new)}, status=201)
        s = FixedAssetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                s.save(organization=org)
        except IntegrityError:
            raise ValidationError({"inventory_code": "Bu inventar kodu artıq mövcuddur."})
        return Response(s.data, status=201)


class OrganizationEquipmentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, pk, action):
        item = get_object_or_404(FixedAsset, pk=pk)
        org = get_visible_organization(request, item.organization_id)
        if not can_org_action(request.user, org, action):
            raise PermissionDenied("Bu əməliyyat üçün icazəniz yoxdur.")
        return item

    def patch(self, request, pk):
        item = self._get(request, pk, "edit")
        s = FixedAssetSerializer(item, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                s.save()
        except IntegrityError:
            raise ValidationError({"inventory_code": "Bu inventar kodu artıq mövcuddur."})
        return Response(s.data)

    def delete(self, request, pk):
        self._get(request, pk, "delete").delete()
        return Response(status=204)


class OrganizationEquipmentBulkDeleteView(APIView):
    """Seçilmiş avadanlıqları (id siyahısı) və ya bütöv qrupu birdən silir."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        org = get_visible_organization(request, pk)
        if not can_org_action(request.user, org, "delete"):
            raise PermissionDenied("Silmə icazəniz yoxdur.")
        qs = org.fixed_assets.all()
        ids = request.data.get("ids")
        if ids:
            qs = qs.filter(id__in=ids)
        elif "group" in request.data:
            qs = qs.filter(group=request.data.get("group") or "")
        else:
            raise ValidationError({"detail": "ids və ya group göndərin."})
        deleted, _ = qs.delete()
        return Response({"deleted": deleted})
