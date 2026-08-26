from django.urls import path

from . import views

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
]
