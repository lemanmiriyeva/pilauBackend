from django.urls import path

from . import views

urlpatterns = [
    path("modules/", views.ModuleListView.as_view(), name="module_list"),
    path("my-modules/", views.MyModulesView.as_view(), name="my_modules"),
    path("user-permissions/", views.UserPermissionListView.as_view(), name="user_permission_list"),
    path("grant/", views.GrantPermissionsView.as_view(), name="grant_permissions"),
]