from django.conf import settings
from django.db import models
from django.utils import timezone

from licenses.field_schema import DOC_TYPES, STATUS_CHOICES, SUBMISSION_MODES


APPROVAL_STAGE_CHOICES = (
    (1, "1-ci mərhələ"),
    (2, "2-ci mərhələ"),
)


class ApprovalSettings(models.Model):
    """Tək qeydlik (singleton) qlobal tənzimləmə - bax ApprovalSettings.get_solo().
    'staged_approval_enabled' söndürüləndə yeni yaradılan sənədlər heç bir təsdiqə
    ehtiyac olmadan birbaşa 'aktiv' statusu ilə yaradılır (bax PermitDocument.save)."""

    staged_approval_enabled = models.BooleanField("Mərhələli təsdiq aktivdir", default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Təsdiq tənzimləməsi"
        verbose_name_plural = "Təsdiq tənzimləmələri"

    def __str__(self):
        return "Mərhələli təsdiq: AÇIQ" if self.staged_approval_enabled else "Mərhələli təsdiq: SÖNÜK"

    @classmethod
    def get_solo(cls) -> "ApprovalSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


def _default_number(doc_type: str) -> str:
    year = timezone.now().year
    count = PermitDocument.objects.filter(
        number__startswith=f"LSN-{year}-"
    ).count() + 1
    return f"LSN-{year}-{count:04d}"


class PermitDocument(models.Model):
    """İdxal / İxrac icazə sənədi (Image 1/2/3/4)."""

    doc_type = models.CharField("Növ", max_length=20, choices=DOC_TYPES)
    number = models.CharField("Sənəd nömrəsi", max_length=30, unique=True, blank=True)
    title = models.CharField("Başlıq", max_length=255, blank=True)

    submission_mode = models.CharField(
        "Müraciət üsulu", max_length=10, choices=SUBMISSION_MODES, default="file"
    )
    is_confidential = models.BooleanField("Məxfi lisenziya", default=False)
    form_data = models.JSONField("Elektron müraciət forması cavabları", default=dict, blank=True)

    # --- Müraciətçi məlumatları (snapshot - Organization/AuthorizedPerson-dan götürülür) ---
    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="permit_documents",
    )
    authorized_person = models.ForeignKey(
        "organizations.AuthorizedPerson", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="permit_documents",
    )
    applicant_name = models.CharField("Müraciətçi müəssisənin tam adı", max_length=255, blank=True)
    voen = models.CharField("VÖEN", max_length=20, blank=True)
    fin_kod = models.CharField("FİN kod", max_length=10, blank=True)
    department = models.CharField("Departament/Şöbə", max_length=255, blank=True)
    position = models.CharField("Vəzifə", max_length=255, blank=True)
    phone = models.CharField("Telefon nömrəsi", max_length=20, blank=True)
    email = models.EmailField("Elektron poçt ünvanı", blank=True)

    issue_date = models.DateField("Verilmə tarixi", null=True, blank=True)
    expiry_date = models.DateField("Bitmə tarixi", null=True, blank=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default="gozleyir")

    # --- Mərhələli təsdiq (bax ApprovalSettings, permissions_module 'tesdiq-merhele-1/2' modulları) ---
    # 'status'=='gozleyir' olduğu müddətcə sənəd hansı mərhələdə olduğunu göstərir.
    approval_stage = models.PositiveSmallIntegerField(
        "Təsdiq mərhələsi", choices=APPROVAL_STAGE_CHOICES, default=1
    )
    stage1_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="stage1_approved_documents",
    )
    stage1_approved_at = models.DateTimeField(null=True, blank=True)
    stage1_comment = models.TextField("1-ci mərhələ qeydi", blank=True)
    stage2_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="stage2_approved_documents",
    )
    stage2_approved_at = models.DateTimeField(null=True, blank=True)
    stage2_comment = models.TextField("2-ci mərhələ qeydi", blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="rejected_documents",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField("Rədd səbəbi", blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="permit_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "İdxal/İxrac icazə sənədi"
        verbose_name_plural = "İdxal/İxrac icazə sənədləri"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} - {self.title or self.get_doc_type_display()}"

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if not self.number:
            self.number = _default_number(self.doc_type)
        # Mərhələli təsdiq söndürülübsə, yeni sənəd birbaşa aktiv olaraq yaradılır -
        # bax ApprovalSettings, licenses/views.py PermitDocumentCreateSerializer istifadəsi.
        if creating and self.status == "gozleyir" and not ApprovalSettings.get_solo().staged_approval_enabled:
            self.status = "aktiv"
        super().save(*args, **kwargs)

    def approve_stage(self, user, comment: str = "") -> None:
        """Cari mərhələni təsdiqləyir: 1-ci mərhələdən 2-ciyə keçir, 2-ci mərhələ
        təsdiqlənəndə isə sənəd 'aktiv' olur."""
        now = timezone.now()
        if self.approval_stage == 1:
            self.stage1_approved_by = user
            self.stage1_approved_at = now
            self.stage1_comment = comment
            self.approval_stage = 2
        else:
            self.stage2_approved_by = user
            self.stage2_approved_at = now
            self.stage2_comment = comment
            self.status = "aktiv"
        self.save()

    def reject(self, user, reason: str) -> None:
        self.status = "legv"
        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.save()


class PermitDocumentFile(models.Model):
    """'Fayl yüklə' rejimində yüklənən sənədlər (field_schema.py-dəki file_fields-ə uyğun)."""

    document = models.ForeignKey(PermitDocument, on_delete=models.CASCADE, related_name="files")
    field_key = models.SlugField("Sahə açarı", max_length=100)
    field_label = models.CharField("Sahə adı", max_length=255, blank=True)
    file = models.FileField("Fayl", upload_to="permit_documents/%Y/%m/")
    original_name = models.CharField("Orijinal fayl adı", max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "İcazə sənədi faylı"
        verbose_name_plural = "İcazə sənədi faylları"

    def __str__(self):
        return f"{self.document.number} - {self.field_label or self.field_key}"