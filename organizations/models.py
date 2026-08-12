from django.db import models


class Organization(models.Model):
    """Image 3 - 'Təşkilat yarat' formuna uyğun. parent ilə iyerarxiya (AzərSilah, Miras Holding və s. altı)."""

    # --- İdentifikasiya (Eyniləşdirmə) ---
    full_name = models.CharField("Tam adı", max_length=255)
    voen = models.CharField("VÖEN", max_length=20, unique=True)
    state_reg_number = models.CharField("Dövlət qeydiyyat nömrəsi", max_length=50, blank=True)

    # --- Əlaqə məlumatları ---
    email = models.EmailField("Əsas elektron poçt ünvanı", blank=True)
    phone = models.CharField("Əsas telefon nömrəsi", max_length=20, blank=True)
    address = models.CharField("Tam ünvan", max_length=500, blank=True)

    # --- İyerarxiya ---
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )

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

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="authorized_persons")
    full_name = models.CharField("Tam adı", max_length=255)
    fin_kod = models.CharField("FİN kod", max_length=10, blank=True)
    department = models.CharField("Departament/Şöbə", max_length=255, blank=True)
    position = models.CharField("Vəzifə", max_length=255, blank=True)
    email = models.EmailField("Elektron poçt ünvanı", blank=True)
    phone = models.CharField("Əlaqə nömrəsi", max_length=20, blank=True)

    class Meta:
        verbose_name = "Səlahiyyətli şəxs"
        verbose_name_plural = "Səlahiyyətli şəxslər"

    def __str__(self):
        return f"{self.full_name} ({self.organization.full_name})"
