from django.db.models import Count
from rest_framework import generics, permissions

from .models import Organization
from .serializers import (
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    OrganizationSummarySerializer,
)


class OrganizationSummaryListView(generics.ListAPIView):
    """Image 4-dəki 'İcazələrin idarə edilməsi' siyahısı - hər təşkilatın istifadəçi sayı ilə."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationSummarySerializer

    def get_queryset(self):
        return Organization.objects.annotate(
            user_count=Count("users", distinct=True)
        ).order_by("full_name")


class OrganizationTreeView(generics.ListAPIView):
    """Image 2-dəki 'Təşkilatı seçin' ağacı üçün - yalnız kök (parent-i olmayan) təşkilatlar,
    children daxildə nested gəlir."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationListSerializer

    def get_queryset(self):
        return Organization.objects.filter(parent__isnull=True).prefetch_related("children")


class OrganizationListCreateView(generics.ListCreateAPIView):
    """Image 3 - 'Təşkilat yarat' formu bu endpoint-ə POST edir."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationDetailSerializer
    queryset = Organization.objects.all().prefetch_related("authorized_persons")


class OrganizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationDetailSerializer
    queryset = Organization.objects.all().prefetch_related("authorized_persons")