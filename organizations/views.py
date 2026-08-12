from rest_framework import generics, permissions

from .models import Organization
from .serializers import OrganizationDetailSerializer, OrganizationListSerializer


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
