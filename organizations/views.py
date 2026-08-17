from django.db.models import Count
from rest_framework import generics, permissions

from .models import Organization
from .permissions import IsStaffOrOrgAdminForWrite, scoped_organization_ids
from .serializers import (
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    OrganizationSummarySerializer,
    OrganizationTableSerializer,
)


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
    Yeni təşkilat yaratmaq yalnız staff/qurum adminindən qəbul olunur (bax: IsStaffOrOrgAdminForWrite);
    siyahı isə hər authenticated istifadəçiyə öz əhatəsi daxilində açıqdır."""
    permission_classes = [IsStaffOrOrgAdminForWrite]
    serializer_class = OrganizationDetailSerializer

    def get_queryset(self):
        qs = Organization.objects.all().prefetch_related("authorized_persons")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(id__in=org_ids)
        return qs


class OrganizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Təşkilat detalı/redaktəsi. Qurum admini yalnız öz təşkilatı (+ alt-təşkilatları) daxilindəki
    təşkilatları görə/redaktə edə bilər; silmək (DELETE) yalnız staff/superuser-ə açıqdır."""
    permission_classes = [IsStaffOrOrgAdminForWrite]
    serializer_class = OrganizationDetailSerializer

    def get_queryset(self):
        qs = Organization.objects.all().prefetch_related("authorized_persons")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(id__in=org_ids)
        return qs

    def delete(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Təşkilatı yalnız sistem administratoru silə bilər.")
        return super().delete(request, *args, **kwargs)