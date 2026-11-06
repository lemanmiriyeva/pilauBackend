from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """
    Butun hessas emeliyyatlarin logu: login/logout, sehv cehdler, icaze deyisiklikleri,
    admin emeliyyatlari. Mexfi proyektde bu cedvel HEC VAXT silinmemelidir (append-only).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Audit qeydi"
        verbose_name_plural = "Audit qeydləri"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} - {self.action} - {self.user}"
    
class OperatorActivity(models.Model):
    OBJECT_TYPES = (
        ("permit_document", "İcazə / lisenziya sənədi"), ("certificate", "Sertifikat"),
        ("organization", "Təşkilat"), ("nomenclature", "Nomenklatura"), ("other", "Digər"),
    )
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="operator_activities")
    operator_username = models.CharField(max_length=150, blank=True)
    operator_name = models.CharField(max_length=255, blank=True)
    action = models.CharField("Əməliyyat kodu", max_length=80)
    action_label = models.CharField("Əməliyyat", max_length=255)
    object_type = models.CharField("Obyekt növü", max_length=30, choices=OBJECT_TYPES, default="other")
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_label = models.CharField("Obyekt", max_length=255, blank=True)
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    detail = models.JSONField("Detallar (sorğu məlumatı)", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Operator fəaliyyəti"
        verbose_name_plural = "Operator fəaliyyət jurnalı"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["operator", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["created_at"]),
        ]