from django.urls import include, path
from rest_framework.routers import DefaultRouter

from licenses import views

router = DefaultRouter()
router.register("permit-documents", views.PermitDocumentViewSet, basename="permit-document")
router.register("certificates", views.LicenseCertificateView, basename="license-certificate")

urlpatterns = [
    path("permit-documents/schema/", views.PermitDocumentSchemaView.as_view(), name="permit_document_schema"),
    path("permit-documents/anket-template/", views.AnketTemplateDownloadView.as_view(), name="anket_template_download"),
    path("permit-documents/anket-parse/", views.AnketTemplateParseView.as_view(), name="anket_template_parse"),
    path("applicant-info/", views.ApplicantInfoView.as_view(), name="applicant_info"),
    path("approval-settings/", views.ApprovalSettingsView.as_view(), name="approval_settings"),
    path("stats/overview/", views.LicenseStatsOverviewView.as_view(), name="license_stats_overview"),
    path("", include(router.urls)),
]