from django.contrib import admin

from .models import Module, UserModulePermission


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "key", "order")
    search_fields = ['title', 'key']


@admin.register(UserModulePermission)
class UserModulePermissionAdmin(admin.ModelAdmin):
    list_display = ("user", "module", "can_view", "can_edit", "can_approve", "granted_by", "granted_at")
    list_filter = ("module", "can_view", "can_edit", "can_approve")
    search_fields = ("user__username", "module__title")
