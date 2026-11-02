from django.conf import settings
from django.db import models


class Organization(models.Model):
    """Image 3 - 'Təşkilat yarat' formuna uyğun. parent ilə iyerarxiya (AzərSilah, Miras Holding və s. altı)."""

    CODE_MSN = "msn"
    CODE_OTHER = "other"
    CODE_CHOICES = [
        (CODE_MSN, "Müdafiə Sənayesi Nazirliyi"),
        (CODE_OTHER, "Qurum"),
    ]

    # Təşkilatın növünü ayırmaq üçün (MSN - nazirliyin özü, digər - bütün digər hüquqi şəxslər).
    # İdxal/ixrac icazə sənədi formasında müraciətçi məlumatlarının redaktə oluna bilməsi
    # bu koda görə müəyyən olunur: MSN istifadəçiləri üçün hər şey editable, digərləri üçün
    # yalnız səlahiyyətli şəxs seçimi mümkündür.
    code = models.CharField("Kod", max_length=20, choices=CODE_CHOICES, default=CODE_OTHER)

    # --- İdentifikasiya (Eyniləşdirmə) ---
    full_name = models.CharField("Tam adı", max_length=255)
    voen = models.CharField("VÖEN", max_length=20, unique=True)
    state_reg_number = models.CharField("Dövlət qeydiyyat nömrəsi", max_length=50, blank=True)
    director_name = models.CharField("Direktor (ad, soyad)", max_length=255, blank=True)
    director_phone = models.CharField("Direktorun telefon nömrəsi", max_length=30, blank=True)
    director_email = models.EmailField("Direktorun e-poçt ünvanı", blank=True)

    # --- Əlaqə məlumatları ---
    email = models.EmailField("Əsas elektron poçt ünvanı", blank=True)
    phone = models.CharField("Əsas telefon nömrəsi", max_length=20, blank=True)
    address = models.CharField("Tam ünvan", max_length=500, blank=True)

    # --- İyerarxiya ---
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )

    is_active = models.BooleanField("Aktiv", default=True)

    # --- Əlavə məlumatlar ---
    notes = models.TextField("Əlavə məlumatlar", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Təşkilat"
        verbose_name_plural = "Təşkilatlar"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    def descendant_ids(self):
        """Bu təşkilat + bütün alt-təşkilatların (children) id-ləri (recursive)."""
        ids = [self.id]
        for child in self.children.all():
            ids += child.descendant_ids()
        return ids


class AuthorizedPerson(models.Model):
    """Image 3 - 'Səlahiyyətli şəxs' bölməsi. Bir təşkilatın bir neçə səlahiyyətli şəxsi ola bilər (+ düyməsi)."""

    TYPE_MAIN = "main"
    TYPE_OTHER = "other"
    TYPE_CHOICES = [
        (TYPE_MAIN, "Əsas"),
        (TYPE_OTHER, "Digər"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="authorized_persons")
    person_type = models.CharField("Növ", max_length=10, choices=TYPE_CHOICES, default=TYPE_MAIN)
    full_name = models.CharField("Tam adı", max_length=255)
    fin_kod = models.CharField("FİN kod", max_length=10, blank=True)
    department = models.CharField("Departament/Şöbə", max_length=255, blank=True)
    position = models.CharField("Vəzifə", max_length=255, blank=True)
    email = models.EmailField("Elektron poçt ünvanı", blank=True)
    phone = models.CharField("Əlaqə nömrəsi", max_length=20, blank=True)

    class Meta:
        verbose_name = "Səlahiyyətli şəxs"
        verbose_name_plural = "Səlahiyyətli şəxslər"
        ordering = ["person_type", "full_name"]  # "main" (əsas) əlifba sırası ilə "other"dan (digər) əvvəl gəlir

    def __str__(self):
        return f"{self.full_name} ({self.organization.full_name})"


class OrganizationDepartment(models.Model):
    """Təşkilatın departamentləri. 'parent' ilə iyerarxiya qurula bilər (məsələn 'İnformasiya
    Texnologiyaları Departamenti' daxilində 'Şəbəkə Strukturu' və 'Proqram Təminatı Strukturu'
    kimi alt-bölmələr) - hər alt-bölmənin öz müdiri ('head') ola bilər."""
    organization = models.ForeignKey(
        "Organization",
        on_delete=models.CASCADE,
        related_name="departments",
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.CASCADE, related_name="children",
        verbose_name="Ana departament",
        help_text="Boş buraxılsa, bu ali (top-level) departamentdir. Seçilsə, bu, həmin "
                  "departamentin daxili strukturu/bölməsidir.",
    )
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        verbose_name="Müdir",
    )
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ("organization", "parent", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrganizationPosition(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="positions"
    )

    department = models.ForeignKey(
        OrganizationDepartment,
        on_delete=models.CASCADE,
        related_name="positions",
        null=True,
        blank=True
    )

    name = models.CharField(max_length=255)


class OrganizationDocument(models.Model):
    """Təşkilatın fəaliyyətinə dair sənədlər (nizamnamə, dövlət qeydiyyatı şəhadətnaməsi və s.).
    Lisenziya/icazə sənədlərindən (licenses.PermitDocument) fərqli olaraq bunlar təşkilatın
    profilinə birbaşa yüklənən ümumi fayllardır."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="activity_documents")
    title = models.CharField("Sənədin adı", max_length=255)
    file = models.FileField("Fayl", upload_to="organization_documents/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fəaliyyətə dair sənəd"
        verbose_name_plural = "Fəaliyyətə dair sənədlər"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.organization.full_name})"


class OrganizationNomenclature(models.Model):
    """Təşkilata məxsus nomenklatura - təşkilatın istehsal etdiyi/təmir etdiyi/saxladığı
    məhsul və avadanlıqların siyahısı (ad, kod, kateqoriya, ölçü vahidi)."""

    CATEGORY_CHOICES = [
        ("herbi_texnika", "Hərbi texnika"),
        ("herbi_silah", "Hərbi silah"),
        ("doyus_sursati", "Döyüş sursatı"),
        ("avadanliq", "Avadanlıq"),
        ("diger", "Digər"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="nomenclature_items")
    name = models.CharField("Adı", max_length=255)
    code = models.CharField("Nomenklatura kodu", max_length=100, blank=True)
    category = models.CharField("Kateqoriya", max_length=20, choices=CATEGORY_CHOICES, default="avadanliq")
    unit = models.CharField("Ölçü vahidi", max_length=30, blank=True)
    note = models.TextField("Qeyd", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Nomenklatura"
        verbose_name_plural = "Nomenklatura"
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.organization.full_name})"


class SubordinateInstitution(models.Model):
    """Təşkilata tabe olan qurum (yalnız məlumat qeydi - sistem təşkilatı deyil).
    Ad və VÖEN məcburidir; ünvan və direktor könüllüdür."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="subordinates")
    name = models.CharField("Adı", max_length=255)
    voen = models.CharField("VÖEN", max_length=20)
    address = models.CharField("Ünvan", max_length=500, blank=True)
    director_name = models.CharField("Direktor", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tabeli qurum"
        verbose_name_plural = "Tabeli qurumlar"
        ordering = ["name"]
        unique_together = ("organization", "voen")

    def __str__(self):
        return f"{self.name} ({self.voen})"


class FixedAsset(models.Model):
    """Təşkilatın əsas avadanlığı: ad + inventar kodu (+ könüllü qrup)."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="fixed_assets")
    name = models.CharField("Avadanlığın adı", max_length=255)
    inventory_code = models.CharField("İnventar kodu", max_length=100)
    group = models.CharField("Qrup", max_length=150, blank=True)
    note = models.TextField("Qeyd", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Əsas avadanlıq"
        verbose_name_plural = "Əsas avadanlıqlar"
        ordering = ["group", "name", "inventory_code"]
        unique_together = ("organization", "inventory_code")

    def __str__(self):
        return f"{self.name} [{self.inventory_code}]"
