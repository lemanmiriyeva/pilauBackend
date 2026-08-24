from django.conf import settings
from django.db import models
from django.utils import timezone

from licenses.field_schema import DOC_TYPES, STATUS_CHOICES, SUBMISSION_MODES


APPROVAL_STAGE_CHOICES = (
    (1, "1-ci mərhələ"),
    (2, "2-ci mərhələ"),
)


class ApprovalSettings(models.Model):
    """Hər lisenziya kateqoriyası (doc_type) üçün AYRICA tənzimlənən mərhələli təsdiq keçidi.
    Konkret kateqoriyada 'staged_approval_enabled' söndürüləndə, HƏMİN kateqoriyada yeni
    yaradılan sənədlər heç bir təsdiqə ehtiyac olmadan birbaşa 'aktiv' statusu ilə yaradılır
    (bax PermitDocument.save). Digər kateqoriyalara təsir etmir."""

    doc_type = models.CharField("Lisenziya kateqoriyası", max_length=20, choices=DOC_TYPES, unique=True)
    staged_approval_enabled = models.BooleanField("Mərhələli təsdiq aktivdir", default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Təsdiq tənzimləməsi"
        verbose_name_plural = "Təsdiq tənzimləmələri"
        ordering = ["doc_type"]

    def __str__(self):
        state = "AÇIQ" if self.staged_approval_enabled else "SÖNÜK"
        return f"{self.get_doc_type_display()}: Mərhələli təsdiq {state}"

    @classmethod
    def get_for(cls, doc_type: str) -> "ApprovalSettings":
        obj, _ = cls.objects.get_or_create(doc_type=doc_type)
        return obj

    @classmethod
    def all_as_dict(cls) -> dict:
        """Bütün kateqoriyalar üçün cari vəziyyət - hələ sətri yaradılmayan kateqoriyalar
        defolt olaraq AÇIQ sayılır (mərhələli təsdiqin defolt davranışı)."""
        existing = {row.doc_type: row.staged_approval_enabled for row in cls.objects.all()}
        return {dt: existing.get(dt, True) for dt, _ in DOC_TYPES}


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
        # Bu kateqoriyada mərhələli təsdiq söndürülübsə, yeni sənəd birbaşa aktiv olaraq
        # yaradılır - bax ApprovalSettings, licenses/views.py PermitDocumentCreateSerializer.
        if creating and self.status == "gozleyir" and not ApprovalSettings.get_for(self.doc_type).staged_approval_enabled:
            self.status = "aktiv"
        super().save(*args, **kwargs)

    def approve_stage(self, user, comment: str = "") -> "LicenseCertificate | None":
        """Cari mərhələni təsdiqləyir: 1-ci mərhələdən 2-ciyə keçir, 2-ci mərhələ
        təsdiqlənəndə isə sənəd 'aktiv' olur VƏ avtomatik olaraq (LicenseCertificate) rəsmi
        sənəd qeydi yaradılır - bax LicenseCertificate, workflow.notify.notify_certificate_ready.
        Yaradılmış sənəd qeydini qaytarır (yalnız indicə 2-ci mərhələ təsdiqləndikdə), əks halda None.

        QEYD: 1-ci mərhələ təsdiqlənəndə, əgər təşkilat admini bu kateqoriya üçün 2-ci mərhələni
        söndürübsə (bax workflow.models.OrgStage2Setting - 'Qurum yoxlaması icazələri' səhifəsi)
        VƏ YA Nazirlik admini bu kateqoriya üçün 2-ci mərhələni ümumiyyətlə söndürübsə (bax
        workflow.models.DocumentWorkflowConfig.stage2_enabled - 'Təsdiq axını' səhifəsi),
        sənəd MSN-ə getmədən birbaşa aktivləşir."""
        from workflow.models import DocumentWorkflowConfig, OrgStage2Setting

        now = timezone.now()
        certificate = None
        if self.approval_stage == 1:
            self.stage1_approved_by = user
            self.stage1_approved_at = now
            self.stage1_comment = comment
            self.approval_stage = 2

            config = DocumentWorkflowConfig.objects.filter(doc_type=self.doc_type).first()
            msn_stage2_disabled = bool(config and not config.stage2_enabled)

            if msn_stage2_disabled:
                self.status = "aktiv"
                self.stage2_comment = (
                    "2-ci mərhələ Nazirlik admini tərəfindən bu kateqoriya üçün söndürülüb - "
                    "avtomatik keçildi."
                )
            elif OrgStage2Setting.is_skipped(self.organization_id, self.doc_type):
                self.status = "aktiv"
                self.stage2_comment = (
                    "2-ci mərhələ təşkilat admini tərəfindən bu kateqoriya üçün söndürülüb - "
                    "avtomatik keçildi."
                )
        else:
            self.stage2_approved_by = user
            self.stage2_approved_at = now
            self.stage2_comment = comment
            self.status = "aktiv"
        self.save()

        if self.status == "aktiv":
            certificate, _ = LicenseCertificate.objects.get_or_create(
                permit_document=self, defaults={"form_data": self.form_data}
            )
        return certificate

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


def _default_certificate_number() -> str:
    year = timezone.now().year
    count = LicenseCertificate.objects.filter(number__startswith=f"SND-{year}-").count() + 1
    return f"SND-{year}-{count:04d}"


class LicenseCertificate(models.Model):
    """Lisenziya tam təsdiqləndikdən (2-ci mərhələ) sonra AVTOMATİK yaranan rəsmi sənəd qeydi.

    PermitDocument-dən (müraciət/iş axını modeli) QƏSDƏN AYRI bir modeldir - konseptual olaraq
    "müraciət" ilə "nəticədə yaranan rəsmi sənəd" fərqli şeylərdir, gələcəkdə sənədin öz həyat
    dövrü (yenidən çap, ləğv, dublikat və s.) ola bilər. OneToOne ilə müraciətə bağlıdır.

    Hazırda vizual şablon hazır olmadığı üçün yalnız müraciət zamanı doldurulan anketin JSON
    köçürməsini (snapshot - mənbə sənəd sonradan dəyişsə belə bu qeyd təsirlənməməlidir) saxlayır;
    real şablon/dizayn təqdim ediləndə buradan render ediləcək.

    'Tamamlandı' düyməsi bu qeydi YARATMIR (avtomatik, təsdiqlə birlikdə yaranır) - yalnız
    istifadəçinin sənədi nəzərdən keçirib təsdiqlədiyini (status='tamamlandi') qeyd edir."""

    STATUS_CHOICES = (
        ("qaralama", "Qaralama"),
        ("tamamlandi", "Tamamlandı"),
    )

    SIGNATURE_METHOD_CHOICES = (
        ("sim", "SİM İmza"),
        ("asan", "Asan İmza"),
    )

    permit_document = models.OneToOneField(
        PermitDocument, on_delete=models.CASCADE, related_name="certificate",
    )
    number = models.CharField("Sənəd nömrəsi", max_length=30, unique=True, blank=True)
    form_data = models.JSONField("Lisenziya anketi (snapshot)", default=dict, blank=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default="qaralama")

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="completed_certificates",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # --- Elektron imza (SİM İmza / Asan İmza) ---
    # QEYD: hazırda real e-imza şlüzü (mobil operator SİM İmza API-si və ya Asan İmza SDK/API-si)
    # inteqrasiya edilməyib - LicenseCertificateView.sign action-ı MOCK işləyir (bax views.py).
    # Real inteqrasiya üçün müvafiq operatorlardan/DVX-dən API təsdiqi, sertifikat və endpoint
    # məlumatları tələb olunur; həmin məlumatlar əldə ediləndə sign action-ın daxili məntiqi
    # əvəz olunmalıdır - bu sahələr və serializer artıq hazırdır.
    is_signed = models.BooleanField("İmzalanıb", default=False)
    signature_method = models.CharField(
        "İmza üsulu", max_length=10, choices=SIGNATURE_METHOD_CHOICES, blank=True
    )
    signed_phone = models.CharField("İmza üçün istifadə olunan nömrə", max_length=20, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lisenziya sənədi"
        verbose_name_plural = "Lisenziya sənədləri"
        ordering = ["-created_at"]

    def __str__(self):
        return self.number or f"Sənəd #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = _default_certificate_number()
        super().save(*args, **kwargs)

    def mark_completed(self, user) -> None:
        self.status = "tamamlandi"
        self.completed_by = user
        self.completed_at = timezone.now()
        self.save()