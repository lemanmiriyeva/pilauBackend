from django.urls import path

from workflow import views

urlpatterns = [
    path("stage1-permissions/", views.Stage1PermissionsView.as_view(), name="stage1_permissions"),
    path("stage2-permissions/", views.Stage2PermissionsView.as_view(), name="stage2_permissions"),
    path("approvers/", views.ApproversListView.as_view(), name="approvers_list"),
]