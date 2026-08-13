from django.contrib import admin

from licenses.models import PermitDocument, PermitDocumentFile


class PermitDocumentFileInline(admin.TabularInline):
    model = PermitDocumentFile
    extra = 0


@admin.register(PermitDocument)
class PermitDocumentAdmin(admin.ModelAdmin):
    list_display = ["number", "title", "doc_type", "status", "issue_date", "expiry_date", "organization"]
    list_filter = ["doc_type", "status", "submission_mode"]
    search_fields = ["number", "title", "applicant_name", "voen"]
    inlines = [PermitDocumentFileInline]