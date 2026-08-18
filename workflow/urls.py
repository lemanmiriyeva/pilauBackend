from django.urls import path

from workflow import views

urlpatterns = [
    path("stage1-permissions/", views.Stage1PermissionsView.as_view(), name="stage1_permissions"),
    path("stage2-permissions/", views.Stage2PermissionsView.as_view(), name="stage2_permissions"),
    path("approvers/", views.ApproversListView.as_view(), name="approvers_list"),
    path("workflow-config/", views.WorkflowConfigView.as_view(), name="workflow_config"),
    path("notifications/", views.NotificationListView.as_view(), name="notifications_list"),
    path("notifications/read-all/", views.NotificationMarkReadView.as_view(), name="notifications_read_all"),
    path("notifications/<int:pk>/read/", views.NotificationMarkReadView.as_view(), name="notifications_read"),
]