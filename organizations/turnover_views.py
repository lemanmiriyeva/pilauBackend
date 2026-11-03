"""Dövriyyələr: təşkilatların xarici / yerli idxal-ixrac dövriyyə qeydləri.

Modul açarı: 'dovriyyeler' (permissions_module.Module). İcazələr modul səviyyəsində verilir:
  Baxış   (can_view)   -> bütün təşkilatların dövriyyəsini görür
  Yaratma (can_create) -> yeni qeyd əlavə edir
  Redaktə (can_edit)   -> mövcud qeydi dəyişir
Silmə yoxdur. "Modul admin" = Baxış + Yaratma + Redaktə verilmiş istifadəçi (staff/superuser avtomatik tam).
Bütün təşkilatları görmək yalnız Nazirlik tərəfi üçündür (staff / MSN təşkilatı işçisi).
"""
from datetime import date as date_cls
from decimal import Decimal

from django.utils.dateparse import parse_date
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from permissions_module.models import Module, has_module_permission

from .models import Organization, OrganizationTurnover
from .profile_views import get_visible_organization

MODULE_KEY = "dovriyyeler"
LIST_LIMIT = 1000


# ----------------------------------------------------------------------------
# İcazələr
# ----------------------------------------------------------------------------
def _is_ministry_side(user) -> bool:
    if user.is_superuser or user.is_staff:
        return True
    org = getattr(user, "organization", None)
    return bool(org and org.code == Organization.CODE_MSN)


def _can(user, action: str) -> bool:
    """action: 'view' | 'create' | 'edit'."""
    if user.is_superuser or user.is_staff:
        return True
    module = Module.objects.filter(key=MODULE_KEY, parent__isnull=True).first()
    return bool(module and has_module_permission(user, module.id, action))


def _need(user, action: str, message: str):
    if not (_is_ministry_side(user) and _can(user, action)):
        raise PermissionDenied(message)


# ----------------------------------------------------------------------------
# Serializasiya
# ----------------------------------------------------------------------------
def _full_name(user) -> str:
    if not user:
        return ""
    return f"{user.first_name} {user.last_name}".strip() or user.username


def _row(t: OrganizationTurnover) -> dict:
    return {
        "id": t.id,
        "organization_id": t.organization_id,
        "organization_name": t.organization.full_name,
        "scope": t.scope,
        "direction": t.direction,
        "date": t.date,
        "document_number": t.document_number,
        "product": t.product,
        "quantity": t.quantity,
        "unit": t.unit,
        "amount": t.amount,
        "currency": t.currency,
        "note": t.note,
        "created_by_name": _full_name(t.created_by),
        "updated_by_name": _full_name(t.updated_by),
        "updated_at": t.updated_at,
    }


class TurnoverWriteSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all())
    date = serializers.DateField(required=False)
    quantity = serializers.DecimalField(max_digits=16, decimal_places=3, min_value=Decimal("0"))
    amount = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True)

    class Meta:
        model = OrganizationTurnover
        fields = [
            "organization", "scope", "direction", "date", "document_number",
            "product", "quantity", "unit", "amount", "currency", "note",
        ]

    def validate_product(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Məhsul (nə) göstərilməlidir.")
        return value


def _filtered(request, qs):
    p = request.query_params
    if p.get("organization"):
        qs = qs.filter(organization_id=p["organization"])
    if p.get("scope") in ("xarici", "yerli"):
        qs = qs.filter(scope=p["scope"])
    if p.get("direction") in ("idxal", "ixrac"):
        qs = qs.filter(direction=p["direction"])
    d_from, d_to = parse_date(p.get("date_from") or ""), parse_date(p.get("date_to") or "")
    if d_from:
        qs = qs.filter(date__gte=d_from)
    if d_to:
        qs = qs.filter(date__lte=d_to)
    q = (p.get("q") or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(product__icontains=q) | Q(document_number__icontains=q))
    return qs


def _summary(rows: list) -> dict:
    out = {}
    for scope in ("xarici", "yerli"):
        items = [r for r in rows if r["scope"] == scope]
        out[scope] = {
            "count": len(items),
            "idxal": sum(1 for r in items if r["direction"] == "idxal"),
            "ixrac": sum(1 for r in items if r["direction"] == "ixrac"),
        }
    return out


# ----------------------------------------------------------------------------
# Modul: bütün təşkilatlar
# ----------------------------------------------------------------------------
class TurnoverListCreateView(APIView):
    """GET  /api/organizations/turnovers/?organization=&scope=&direction=&date_from=&date_to=&q=
       POST /api/organizations/turnovers/  (Yaratma icazəsi)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _need(request.user, "view", "Dövriyyələr modulunu görmək icazəniz yoxdur.")
        qs = _filtered(request, OrganizationTurnover.objects.select_related(
            "organization", "created_by", "updated_by"))[:LIST_LIMIT]
        rows = [_row(t) for t in qs]
        return Response({
            "permissions": {"can_create": _can(request.user, "create"), "can_edit": _can(request.user, "edit")},
            "organizations": [
                {"id": o.id, "name": o.full_name}
                for o in Organization.objects.filter(is_active=True).order_by("full_name")
            ],
            "summary": _summary(rows),
            "results": rows,
        })

    def post(self, request):
        _need(request.user, "create", "Dövriyyə əlavə etmək icazəniz yoxdur.")
        serializer = TurnoverWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(
            created_by=request.user, updated_by=request.user,
            **({} if serializer.validated_data.get("date") else {"date": date_cls.today()}),
        )
        obj = OrganizationTurnover.objects.select_related("organization", "created_by", "updated_by").get(pk=obj.pk)
        return Response(_row(obj), status=status.HTTP_201_CREATED)


class TurnoverDetailView(APIView):
    """PATCH /api/organizations/turnovers/<id>/ (Redaktə icazəsi). Silmə yoxdur."""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        _need(request.user, "edit", "Dövriyyəni redaktə etmək icazəniz yoxdur.")
        obj = OrganizationTurnover.objects.filter(pk=pk).first()
        if obj is None:
            return Response({"detail": "Qeyd tapılmadı."}, status=404)
        serializer = TurnoverWriteSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        obj = OrganizationTurnover.objects.select_related("organization", "created_by", "updated_by").get(pk=pk)
        return Response(_row(obj))


# ----------------------------------------------------------------------------
# Təşkilatın detalı: yalnız həmin təşkilatın dövriyyəsi
# ----------------------------------------------------------------------------
class OrganizationTurnoverView(APIView):
    """GET /api/organizations/<id>/turnover/ - təşkilatın öz dövriyyə qeydləri (təşkilatı görə bilənlər üçün)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        org = get_visible_organization(request, pk)
        qs = _filtered(request, OrganizationTurnover.objects.filter(organization=org).select_related(
            "organization", "created_by", "updated_by"))[:LIST_LIMIT]
        rows = [_row(t) for t in qs]
        return Response({"summary": _summary(rows), "results": rows})