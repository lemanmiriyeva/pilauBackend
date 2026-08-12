from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("authentication.urls")),
    path("api/organizations/", include("organizations.urls")),
    path("api/permissions/", include("permissions_module.urls")),
]
