from django.urls import path

from . import views

urlpatterns = [
    path("tree/", views.OrganizationTreeView.as_view(), name="organization_tree"),
    path("summary/", views.OrganizationSummaryListView.as_view(), name="organization_summary"),
    path("table/", views.OrganizationTableListView.as_view(), name="organization_table"),
    path("", views.OrganizationListCreateView.as_view(), name="organization_list_create"),
    path("<int:pk>/", views.OrganizationDetailView.as_view(), name="organization_detail"),
]