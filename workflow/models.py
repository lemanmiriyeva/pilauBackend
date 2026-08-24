"""
Lisenziya/icazə sənədləri üçün mərhələli təsdiqləmə - icazə modelləri.

Hər lisenziya kateqoriyası (doc_type - bax licenses.field_schema.DOC_TYPES) üçün 2 sabit
mərhələ var:

  1-ci mərhələ - Qurum yoxlaması: müraciət edən təşkilatın öz daxilində sənədi ilkin yoxlayan
  şəxs. Kimin hansı kateqoriyanı yoxlaya biləcəyini HƏMİN TƏŞKİLATIN admini (is_org_admin=True)
  təyin edir (bax OrgReviewerPermission).

  2-ci mərhələ - Təsdiq: Nazirlik (mərkəzi) tərəfdən sənədi son təsdiqləyən şəxs. Kimin bu
  hüquqa sahib olduğunu Nazirliyin öz admini (is_staff/is_superuser) təyin edir
  (bax ApproverPermission).

Hər iki model sadəcə "kimin hansı kateqoriyada hansı mərhələdə səlahiyyəti var" sualına
cavab verir - konkret sənədin hazırkı mərhələsi/qərarı (təsdiq/rədd) ayrı bir işdir və
bu fayla daxil deyil (bax layihə qeydlərində "təsdiqdən sonrakı məsələlər").
"""
from django.conf import settings
from django.db import models

from licenses.field_schema import DOC_TYPES


class OrgReviewerPermission(models.Model):
    """1-ci mərhələ: Qurum yoxlaması icazəsi.

    Məsələn: "Ləman Başırova" (MDN təşkilatının işçisi) "İstehsal" kateqoriyalı sənədləri
    yoxlaya bilər - bunu MDN-in qurum admini bu modeldəki bir sətirlə təyin edir."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE,
        related_name="reviewer_permissions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="org_reviewer_permissions",
    )
    doc_type = models.CharField("Lisenziya kateqoriyası", max_length=20, choices=DOC_TYPES)
    can_review = models.BooleanField("Qurum yoxlaması apara bilər", default=True)

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Qurum yoxlaması icazəsi (1-ci mərhələ)"
        verbose_name_plural = "Qurum yoxlaması icazələri (1-ci mərhələ)"
        unique_together = ("organization", "user", "doc_type")
        ordering = ["organization_id", "user_id", "doc_type"]

    def __str__(self):
        return f"{self.user} · {self.get_doc_type_display()} · {'✓' if self.can_review else '—'}"

    @classmethod
    def eligible_user_ids(cls, organization_id, doc_type) -> set:
        """1-ci mərhələdə ('qurum' rejimi) bu təşkilatın bu kateqoriya üzrə sənədini kimlər
        yoxlaya/təsdiqləyə bilər: təşkilatın admini(ləri) VƏ bu kateqoriya üçün açıq-aşkar
        icazə verilmiş istənilən sayda istifadəçi. Nəticə TƏBİİ OLARAQ çoxlu (multiple) ola
        bilər - 'qurum' rejimində sənədi TƏK bir sabit şəxsə deyil, bu siyahıdakı istənilən
        şəxsə həvalə edir (kim əvvəl baxarsa)."""
        from authentication.models import User

        org_admin_ids = set(
            User.objects.filter(
                organization_id=organization_id, is_org_admin=True, is_active=True,
            ).values_list("id", flat=True)
        )
        reviewer_ids = set(
            cls.objects.filter(
                organization_id=organization_id, doc_type=doc_type, can_review=True,
            ).values_list("user_id", flat=True)
        )
        return org_admin_ids | reviewer_ids


class ApproverPermission(models.Model):
    """2-ci mərhələ: Təsdiq icazəsi (Nazirlik tərəfi).

    Təşkilata bağlı DEYİL - Nazirliyin hansı işçilərinin hansı kateqoriyalarda son təsdiq
    hüququ olduğunu göstərir. Yalnız Nazirlik admini (is_staff/is_superuser) təyin edə bilər."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="approver_permissions",
    )
    doc_type = models.CharField("Lisenziya kateqoriyası", max_length=20, choices=DOC_TYPES)
    can_approve = models.BooleanField("Yoxlama və təsdiq hüququ", default=True)

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Təsdiq icazəsi (2-ci mərhələ)"
        verbose_name_plural = "Təsdiq icazələri (2-ci mərhələ)"
        unique_together = ("user", "doc_type")
        ordering = ["user_id", "doc_type"]

    def __str__(self):
        return f"{self.user} · {self.get_doc_type_display()} · {'✓' if self.can_approve else '—'}"


class DocumentWorkflowConfig(models.Model):
    """Sənəd növü üzrə mərhələli təsdiq axınının marşrutlanması.

    1-ci mərhələ ya müraciət edən təşkilatın öz admininə (stage1_mode='qurum'), ya da
    birbaşa Nazirliyin təyin etdiyi konkret bir işçiyə (stage1_mode='msn', bax stage1_user)
    gedir. 2-ci mərhələ (son təsdiq) hər zaman Nazirlik tərəfindəndir - stage2_user bunun
    üçün təyin edilmiş konkret işçidir.

    Hər iki halda 'msn' seçildikdə təyin oluna bilən istifadəçilər yalnız həmin doc_type
    üzrə ApproverPermission (Təsdiq hüquqları) verilmiş şəxslərdir - bax _eligible_user_ids.
    """
    STAGE1_CHOICES = [("qurum", "Qurum"), ("msn", "MSN")]

    doc_type = models.CharField("Lisenziya kateqoriyası", max_length=20, choices=DOC_TYPES, unique=True)
    stage1_mode = models.CharField("1-ci mərhələ", max_length=10, choices=STAGE1_CHOICES, default="qurum")
    stage1_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="1-ci mərhələ icraçısı",
    )

    stage1_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="workflow_stage1_configs",
        verbose_name="1-ci mərhələ təsdiqçiləri",
    )
    stage2_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        verbose_name="2-ci mərhələ icraçısı (MSN)",
    )
    stage2_enabled = models.BooleanField(
        "2-ci mərhələ aktivdir",
        default=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sənəd növü təsdiq axını"
        verbose_name_plural = "Sənəd növləri təsdiq axınları"
        ordering = ["doc_type"]

    def __str__(self):
        return f"{self.get_doc_type_display()} · 1-ci: {self.get_stage1_mode_display()} · 2-ci: MSN"


class OrgStage2Setting(models.Model):
    """Təşkilatın özü üçün, hər lisenziya kateqoriyası üzrə: MSN-in son (2-ci mərhələ)
    təsdiqini keçmək istəyirmi? Bax 'Qurum yoxlaması icazələri' ekranı (yalnız qurum admini
    özü, öz təşkilatı üçün dəyişə bilər - hər modul üçün ayrıca sətir/toggle).

    skip_stage2=True olduqda: 1-ci mərhələ (qurum) təsdiqi kifayət edir - sənəd MSN-ə
    göndərilmədən birbaşa 'aktiv' olur (bax PermitDocument.approve_stage)."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="stage2_settings",
    )
    doc_type = models.CharField("Lisenziya kateqoriyası", max_length=20, choices=DOC_TYPES)
    skip_stage2 = models.BooleanField("MSN son təsdiqini keçir (2-ci mərhələ söndürülüb)", default=False)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Təşkilat - 2-ci mərhələ tənzimləməsi"
        verbose_name_plural = "Təşkilatlar - 2-ci mərhələ tənzimləmələri"
        unique_together = ("organization", "doc_type")
        ordering = ["organization_id", "doc_type"]

    def __str__(self):
        state = "MSN keçilir" if self.skip_stage2 else "MSN aktiv"
        return f"{self.organization} · {self.get_doc_type_display()} · {state}"

    @classmethod
    def is_skipped(cls, organization_id, doc_type) -> bool:
        if not organization_id:
            return False
        return cls.objects.filter(
            organization_id=organization_id, doc_type=doc_type, skip_stage2=True,
        ).exists()


class Notification(models.Model):
    """Sadə daxili bildiriş - sənəd 1-ci/2-ci mərhələ yoxlamasına düşdükdə icraçılara göndərilir.
    E-poçt paralel olaraq (asinxron) göndərilir, bax workflow.notify."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications",
    )
    title = models.CharField("Başlıq", max_length=255)
    body = models.TextField("Mətn", blank=True)
    link = models.CharField("Keçid (frontend path)", max_length=255, blank=True)
    is_read = models.BooleanField("Oxunub", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bildiriş"
        verbose_name_plural = "Bildirişlər"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient} · {self.title}"