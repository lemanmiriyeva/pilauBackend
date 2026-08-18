from django.contrib import admin

from workflow.models import ApproverPermission, OrgReviewerPermission


@admin.register(OrgReviewerPermission)
class OrgReviewerPermissionAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "doc_type", "can_review", "updated_at")
    list_filter = ("doc_type", "can_review", "organization")
    search_fields = ("user__username", "user__first_name", "user__last_name", "organization__full_name")


@admin.register(ApproverPermission)
class ApproverPermissionAdmin(admin.ModelAdmin):
    list_display = ("user", "doc_type", "can_approve", "updated_at")
    list_filter = ("doc_type", "can_approve")
    search_fields = ("user__username", "user__first_name", "user__last_name")