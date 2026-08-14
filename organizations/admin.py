from django.contrib import admin

from .models import AuthorizedPerson, Organization


class AuthorizedPersonInline(admin.TabularInline):
    model = AuthorizedPerson
    extra = 1


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "code", "voen", "parent", "phone", "email")
    search_fields = ("full_name", "voen", "state_reg_number")
    list_filter = ("code", "parent")
    inlines = [AuthorizedPersonInline]