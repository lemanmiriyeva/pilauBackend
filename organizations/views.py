from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Organization
from .permissions import IsFullAdminForCreate, IsStaffOrOrgAdminForWrite, is_full_admin, scoped_organization_ids
from .serializers import (
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    OrganizationReportCardSerializer,
    OrganizationSummarySerializer,
    OrganizationTableSerializer,
)

_GRANULARITY_TRUNC = {"day": TruncDate, "month": TruncMonth, "year": TruncYear}


class OrganizationSummaryListView(generics.ListAPIView):
    """Image 4-dəki 'İcazələrin idarə edilməsi' siyahısı - hər təşkilatın istifadəçi sayı ilə."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationSummarySerializer

    def get_queryset(self):
        qs = Organization.objects.annotate(
            user_count=Count("users", distinct=True)
        ).order_by("full_name")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(id__in=org_ids)
        return qs


class OrganizationTreeView(generics.ListAPIView):
    """Image 2-dəki 'Təşkilatı seçin' ağacı üçün - yalnız kök (parent-i olmayan) təşkilatlar,
    children daxildə nested gəlir."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationListSerializer

    def get_queryset(self):
        qs = Organization.objects.filter(parent__isnull=True).prefetch_related("children")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(id__in=org_ids)
        return qs


class OrganizationTableListView(generics.ListAPIView):
    """Təşkilatlar siyahı səhifəsi (list) - səlahiyyətli şəxs sayı ilə birlikdə.

    Staff/superuser bütün təşkilatları görür; digərləri (adi işçi və ya qurum admini)
    yalnız öz təşkilatını + alt-təşkilatlarını görür (bax: scoped_organization_ids)."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationTableSerializer

    def get_queryset(self):
        qs = Organization.objects.annotate(
            authorized_person_count=Count("authorized_persons", distinct=True)
        ).order_by("full_name")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(id__in=org_ids)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(full_name__icontains=search)
        return qs


class OrganizationListCreateView(generics.ListCreateAPIView):
    """Image 3 - 'Təşkilat yarat' formu bu endpoint-ə POST edir.
    Yeni təşkilat yaratmaq YALNIZ Nazirlik admininə (is_staff/is_superuser) açıqdır - qurum
    admininin bu hüququ yoxdur (bax IsFullAdminForCreate); siyahı isə hər authenticated
    istifadəçiyə öz əhatəsi daxilində açıqdır."""
    permission_classes = [IsFullAdminForCreate]
    serializer_class = OrganizationDetailSerializer

    def get_queryset(self):
        qs = Organization.objects.all().prefetch_related("authorized_persons")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(id__in=org_ids)
        return qs


class OrganizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Təşkilat detalı/redaktəsi.

    Nazirlik admini (is_staff/is_superuser) - bütün təşkilatları görür/redaktə edir/silir.
    Qurum admini - görməsi öz təşkilatı + alt-təşkilatları daxilindədir (queryset), AMMA
    redaktə (PATCH/PUT) YALNIZ məhz ÖZ təşkilatı (alt-təşkilatlar DAXİL DEYİL) üçündür - bax
    check_object_permissions. Silmək (DELETE) yalnız staff/superuser-ə açıqdır."""
    permission_classes = [IsStaffOrOrgAdminForWrite]
    serializer_class = OrganizationDetailSerializer

    def get_queryset(self):
        qs = Organization.objects.all().prefetch_related("authorized_persons")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(id__in=org_ids)
        return qs

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method in ("PATCH", "PUT") and not is_full_admin(request.user):
            if obj.id != request.user.organization_id:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Yalnız öz təşkilatınızı redaktə edə bilərsiniz.")

    def delete(self, request, *args, **kwargs):
        if not is_full_admin(request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Təşkilatı yalnız sistem administratoru silə bilər.")
        return super().delete(request, *args, **kwargs)

class OrganizationReportCardsView(generics.ListAPIView):
    """Hesabatlar -> Təşkilatlar səhifəsi üçün kart şəklində siyahı - hər təşkilatın (bütün
    vaxtlar üzrə) yaratdığı ÜMUMİ lisenziya sənədi sayı ilə birlikdə. Kartın üzərinə klikləyəndə
    açılan detal (OrganizationStatsView) seçilmiş tarix aralığı üzrə süzür - bura isə yalnız
    ümumi say göstərilir (kartda tarix filtri yoxdur, sadəcə siyahı/naviqasiya üçündür).
    Görünürlük eyni qaydaya tabedir: Nazirlik admini/təsdiq icraçıları hamısını, qurum
    admini/işçi yalnız öz təşkilatını (və alt-təşkilatlarını) görür."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationReportCardSerializer

    def get_queryset(self):
        qs = Organization.objects.annotate(
            license_count=Count("permit_documents", distinct=True)
        ).order_by("full_name")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(id__in=org_ids)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(full_name__icontains=search)
        return qs


class OrganizationStatsView(APIView):
    """Hesabatlar -> Təşkilatlar -> tək təşkilatın detalı.

    GET /api/organizations/<id>/stats/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&granularity=day|month|year

    Seçilmiş tarix aralığında bu təşkilatın yaratdığı sənədlərin: ümumi sayı, status bölgüsü,
    lisenziya növü üzrə bölgüsü, zaman seriyası (qrafik üçün) və son sənədlərin detallı siyahısı
    (cədvəl üçün, ən çox 100 sətir) qaytarılır. date_from/date_to göndərilməzsə defolt son 12 ay.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        from licenses.field_schema import DOC_TYPES
        from licenses.models import PermitDocument

        organization = get_object_or_404(Organization, pk=pk)

        org_ids = scoped_organization_ids(request.user)
        if org_ids is not None and organization.id not in org_ids:
            return Response({"detail": "Bu təşkilatın hesabatına baxmaq hüququnuz yoxdur."}, status=403)

        granularity = request.query_params.get("granularity") or "month"
        if granularity not in _GRANULARITY_TRUNC:
            granularity = "month"

        today = timezone.localdate()
        date_from = parse_date(request.query_params.get("date_from") or "") or (today - timedelta(days=365))
        date_to = parse_date(request.query_params.get("date_to") or "") or today
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        qs = PermitDocument.objects.filter(
            organization=organization,
            created_at__date__gte=date_from, created_at__date__lte=date_to,
        )

        total = qs.count()

        status_breakdown = {
            row["status"]: row["c"] for row in qs.values("status").annotate(c=Count("id")).order_by()
        }

        dt_map = dict(DOC_TYPES)
        by_doc_type = [
            {"doc_type": row["doc_type"], "label": dt_map.get(row["doc_type"], row["doc_type"]), "count": row["c"]}
            for row in qs.values("doc_type").annotate(c=Count("id")).order_by("-c")
        ]

        trunc = _GRANULARITY_TRUNC[granularity]
        series = [
            {
                "period": row["period"].isoformat() if hasattr(row["period"], "isoformat") else str(row["period"]),
                "count": row["c"],
            }
            for row in qs.annotate(period=trunc("created_at")).values("period").annotate(c=Count("id")).order_by("period")
        ]

        documents = list(
            qs.order_by("-created_at").values("id", "number", "doc_type", "title", "status", "created_at")[:100]
        )
        for row in documents:
            row["category"] = dt_map.get(row["doc_type"], row["doc_type"])
            row["created_at"] = row["created_at"].isoformat()

        return Response({
            "organization": {"id": organization.id, "full_name": organization.full_name, "code": organization.code},
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "granularity": granularity,
            "total": total,
            "status_breakdown": status_breakdown,
            "by_doc_type": by_doc_type,
            "series": series,
            "documents": documents,
        })