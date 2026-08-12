from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "user", "ip_address", "method", "status_code", "path")
    list_filter = ("action",)
    search_fields = ("user__username", "ip_address", "detail", "path")
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # audit qeydleri append-only olmalidir - superuser belə silə bilməməlidir
        return False
