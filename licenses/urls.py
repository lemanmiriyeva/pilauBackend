from django.urls import include, path
from rest_framework.routers import DefaultRouter

from licenses import views

router = DefaultRouter()
router.register("permit-documents", views.PermitDocumentViewSet, basename="permit-document")

urlpatterns = [
    path("permit-documents/schema/", views.PermitDocumentSchemaView.as_view(), name="permit_document_schema"),
    path("applicant-info/", views.ApplicantInfoView.as_view(), name="applicant_info"),
    path("approval-settings/", views.ApprovalSettingsView.as_view(), name="approval_settings"),
    path("", include(router.urls)),
]