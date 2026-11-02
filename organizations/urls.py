from django.urls import path

from . import assets_views, org_settings_views, profile_views, views

urlpatterns = [
    path(
        "tree/",
        views.OrganizationTreeView.as_view(),
        name="organization_tree"
    ),

    path(
        "summary/",
        views.OrganizationSummaryListView.as_view(),
        name="organization_summary"
    ),

    path(
        "table/",
        views.OrganizationTableListView.as_view(),
        name="organization_table"
    ),

    path(
        "report-cards/",
        views.OrganizationReportCardsView.as_view(),
        name="organization_report_cards"
    ),

    # =========================================================
    # TƏŞKİLATIN DEPARTAMENTLƏRİ
    # GET /api/organizations/<organization_id>/departments/
    # =========================================================
    path(
        "<int:organization_id>/departments/",
        views.OrganizationDepartmentsByOrganizationView.as_view(),
        name="organization_departments_by_organization",
    ),

    # =========================================================
    # TƏŞKİLATIN VƏZİFƏLƏRİ
    # GET /api/organizations/<organization_id>/positions/
    # =========================================================
    path(
        "<int:organization_id>/positions/",
        views.OrganizationPositionsByOrganizationView.as_view(),
        name="organization_positions_by_organization",
    ),

    # =========================================================
    # DEPARTAMENTLƏR ADMIN CRUD
    # =========================================================
    path(
        "departments/",
        views.OrganizationDepartmentViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="organization_departments",
    ),

    path(
        "departments/<int:pk>/",
        views.OrganizationDepartmentViewSet.as_view({
            "patch": "partial_update",
            "put": "update",
            "delete": "destroy",
        }),
        name="organization_department_detail",
    ),

    # =========================================================
    # VƏZİFƏLƏR ADMIN CRUD
    # =========================================================
    path(
        "positions/",
        views.OrganizationPositionViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="organization_positions",
    ),

    path(
        "positions/<int:pk>/",
        views.OrganizationPositionViewSet.as_view({
            "patch": "partial_update",
            "put": "update",
            "delete": "destroy",
        }),
        name="organization_position_detail",
    ),

    # =========================================================
    # TƏŞKİLAT CRUD
    # =========================================================
    path(
        "",
        views.OrganizationListCreateView.as_view(),
        name="organization_list_create",
    ),

    # --- Təşkilatın təfərrüat səhifəsi (bax profile_views.py) ---
    path("<int:pk>/profile/", profile_views.OrganizationProfileView.as_view(), name="organization_profile"),
    path("<int:pk>/employees/", profile_views.OrganizationEmployeesView.as_view(), name="organization_employees"),
    path("<int:pk>/employees/<int:user_id>/", profile_views.OrganizationEmployeeDetailView.as_view(),
         name="organization_employee_detail"),
    path("<int:pk>/nomenclature/", profile_views.OrganizationNomenclatureView.as_view(),
         name="organization_nomenclature"),
    path("nomenclature/<int:pk>/", profile_views.OrganizationNomenclatureDetailView.as_view(),
         name="organization_nomenclature_detail"),
    path("<int:pk>/permit-documents/", profile_views.OrganizationPermitDocumentsView.as_view(),
         name="organization_permit_documents"),
    path("<int:pk>/activity-documents/", profile_views.OrganizationActivityDocumentsView.as_view(),
         name="organization_activity_documents"),
    path("activity-documents/<int:pk>/", profile_views.OrganizationActivityDocumentDetailView.as_view(),
         name="organization_activity_document_detail"),
    path("activity-documents/<int:pk>/download/", profile_views.OrganizationActivityDocumentDownloadView.as_view(),
         name="organization_activity_document_download"),

    path("<int:pk>/subordinates/", assets_views.OrganizationSubordinatesView.as_view(), name="organization_subordinates"),
    path("subordinates/<int:pk>/", assets_views.OrganizationSubordinateDetailView.as_view(), name="organization_subordinate_detail"),
    path("<int:pk>/equipment/", assets_views.OrganizationEquipmentView.as_view(), name="organization_equipment"),
    path("<int:pk>/equipment/bulk-delete/", assets_views.OrganizationEquipmentBulkDeleteView.as_view(), name="organization_equipment_bulk_delete"),
    path("equipment/<int:pk>/", assets_views.OrganizationEquipmentDetailView.as_view(), name="organization_equipment_detail"),
    path("module-defaults/", org_settings_views.ModuleDefaultsView.as_view(), name="module_defaults"),
    path("<int:pk>/module-access/", org_settings_views.OrganizationModuleAccessView.as_view(),
         name="organization_module_access"),
    path("<int:pk>/approval-flow/", org_settings_views.OrganizationApprovalFlowView.as_view(),
         name="organization_approval_flow"),

    path(
        "<int:pk>/stats/",
        views.OrganizationStatsView.as_view(),
        name="organization_stats",
    ),

    path(
        "<int:pk>/",
        views.OrganizationDetailView.as_view(),
        name="organization_detail",
    ),
    path(
        "voen-lookup/",
        views.OrganizationVoenLookupView.as_view(),
        name="organization_voen_lookup"
    ),
]
