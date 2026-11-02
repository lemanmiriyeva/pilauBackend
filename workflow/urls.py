from django.urls import path

from workflow import views
from workflow.views import Stage1OrganizationUsersView
from workflow import operator_views, views

urlpatterns = [
    path("stage1-permissions/", views.Stage1PermissionsView.as_view(), name="stage1_permissions"),
    path("stage2-permissions/", views.Stage2PermissionsView.as_view(), name="stage2_permissions"),
    path("stage2-settings/", views.OrgStage2SettingsView.as_view(), name="org_stage2_settings"),
    path("approvers/", views.ApproversListView.as_view(), name="approvers_list"),
    path(
        "stage1-organization-users/",
        Stage1OrganizationUsersView.as_view(),
        name="stage1-organization-users",
    ),
    path("workflow-config/", views.WorkflowConfigView.as_view(), name="workflow_config"),
    path("notifications/", views.NotificationListView.as_view(), name="notifications_list"),
    path("notifications/read-all/", views.NotificationMarkReadView.as_view(), name="notifications_read_all"),
    path("notifications/<int:pk>/read/", views.NotificationMarkReadView.as_view(), name="notifications_read"),
    path("operators/", operator_views.OperatorListCreateView.as_view(), name="operators"),
    path("operators/settings/", operator_views.OperatorSettingsView.as_view(), name="operators_settings"),
    path("operators/<int:pk>/", operator_views.OperatorDetailView.as_view(), name="operator_detail"),
    path("operator-queue/", operator_views.OperatorQueueView.as_view(), name="operator_queue"),
]
