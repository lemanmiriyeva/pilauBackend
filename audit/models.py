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
