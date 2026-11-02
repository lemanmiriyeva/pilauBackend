from django.conf import settings
from django.db import models


class Module(models.Model):
    ICON_CHOICES = [
        ("description", "Sənəd"),
        ("assessment", "Hesabat"),
        ("apartment", "Bina/Təşkilat"),
        ("manage_accounts", "İdarəçi"),
        ("gavel", "Lisenziya"),
        ("local_shipping", "Nəqliyyat/Satış"),
        ("import_export", "İdxal-İxrac"),
        ("percent", "Güzəşt"),
    ]

    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    key = models.SlugField("Açar", max_length=100)
    title = models.CharField("Ad", max_length=100)
    description = models.CharField("Təsvir", max_length=255, blank=True)
    meta = models.CharField("Əlavə qeyd (məs. 'Müddətsiz')", max_length=100, blank=True)
    icon = models.CharField("İkon", max_length=30, choices=ICON_CHOICES, default="description")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Modul"
        verbose_name_plural = "Modullar"
        ordering = ["order", "title"]
        unique_together = ("parent", "key")

    def __str__(self):
        return f"{self.parent} / {self.title}" if self.parent_id else self.title

    def full_path(self):
        parts = [self.key]
        node = self.parent
        while node:
            parts.append(node.key)
            node = node.parent
        return list(reversed(parts))


class UserModulePermission(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="module_permissions"
    )
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="user_permissions")

    can_view = models.BooleanField("Baxış", default=False)
    can_create = models.BooleanField("Yaratma", default=False)
    can_edit = models.BooleanField("Redaktə", default=False)
    can_approve = models.BooleanField("Təsdiq", default=False)
    can_delete = models.BooleanField("Silmə", default=False)

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="granted_permissions",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "İstifadəçi modul icazəsi"
        verbose_name_plural = "İstifadəçi modul icazələri"
        unique_together = ("user", "module")

    def __str__(self):
        return f"{self.user} - {self.module}"


class OrganizationModuleAccess(models.Model):
    """Hansı təşkilata hansı modulların açıq olduğunu Nazirlik admini müəyyən edir.
    Qurum admini və işçiləri YALNIZ bu siyahıdakı modulları görə bilər."""
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="module_access"
    )
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="organization_access")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Təşkilat modul icazəsi"
        verbose_name_plural = "Təşkilat modul icazələri"
        unique_together = ("organization", "module")

    def __str__(self):
        return f"{self.organization_id} - {self.module_id}"


class GlobalOrgModuleAccess(models.Model):
    """Bütün təşkilatlar (qurum adminləri) üçün ÜMUMİ modul konfiqurasiyası - bas admin bir dəfə
    seçir, fərdi icazəsi olmayan hər təşkilata tətbiq olunur."""
    module = models.OneToOneField(Module, on_delete=models.CASCADE, related_name="global_org_access")

    class Meta:
        verbose_name = "Ümumi təşkilat modulu"
        verbose_name_plural = "Ümumi təşkilat modulları"


class OrganizationModuleSettings(models.Model):
    """use_custom=True olduqda təşkilat ümumi konfiqurasiyanı yox, OrganizationModuleAccess
    siyahısını (fərdi icazələr) istifadə edir."""
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="module_settings"
    )
    use_custom = models.BooleanField("Fərdi modul icazələri", default=False)

    class Meta:
        verbose_name = "Təşkilat modul tənzimləməsi"
        verbose_name_plural = "Təşkilat modul tənzimləmələri"


# Yeni təşkilata default verilməyən (yalnız Nazirlik üçün) modullar
NON_DEFAULT_MODULE_KEYS = {"tesdiq-huquqlari"}
ORG_MODULE_KEY = "teskilatlar"
FULL = {"can_view": True, "can_create": True, "can_edit": True, "can_approve": True, "can_delete": True}
NONE = {"can_view": False, "can_create": False, "can_edit": False, "can_approve": False, "can_delete": False}


def default_module_ids():
    return [m.id for m in Module.objects.all() if m.key not in NON_DEFAULT_MODULE_KEYS]


def grant_default_modules(org):
    """Yeni təşkilat ümumi konfiqurasiyanı istifadə edir - ayrıca sətir yaratmaq lazım deyil."""
    return None


def global_module_ids():
    return set(GlobalOrgModuleAccess.objects.values_list("module_id", flat=True))


def org_uses_custom(org) -> bool:
    return bool(org) and OrganizationModuleSettings.objects.filter(organization=org, use_custom=True).exists()


def org_module_ids(org):
    """Təşkilata açıq modul id çoxluğu. Fərdi icazə varsa - onların siyahısı, yoxsa ümumi
    konfiqurasiya. Heç nə konfiqurasiya olunmayıbsa None (= default: staff-only xaric hamısı)."""
    if not org:
        return None
    if org_uses_custom(org):
        return set(OrganizationModuleAccess.objects.filter(organization=org).values_list("module_id", flat=True))
    return global_module_ids() or None


def _is_unrestricted(user):
    from organizations.permissions import is_full_admin, is_msn_admin
    return is_full_admin(user) or is_msn_admin(user)


def effective_permissions(user):
    """{module_id: {can_*}} - istifadəçinin həqiqi icazələri."""
    modules = list(Module.objects.all())
    if user.is_superuser or user.is_staff:
        return {m.id: dict(FULL) for m in modules}
    explicit = {
        p.module_id: {
            "can_view": p.can_view, "can_create": p.can_create,
            "can_edit": p.can_edit, "can_approve": p.can_approve, "can_delete": p.can_delete,
        }
        for p in UserModulePermission.objects.filter(user=user)
    }
    if _is_unrestricted(user):
        return explicit
    org = getattr(user, "organization", None)
    allowed = org_module_ids(org)
    if getattr(user, "is_org_admin", False):
        if allowed is None:
            allowed = {m.id for m in modules if m.key not in NON_DEFAULT_MODULE_KEYS}
        return {mid: dict(FULL) for mid in allowed}
    if allowed is None:
        return explicit
    return {mid: v for mid, v in explicit.items() if mid in allowed}


def has_module_permission(user, module_id: int, action: str) -> bool:
    """action: 'view' | 'create' | 'edit' | 'approve'"""
    if action not in {"view", "create", "edit", "approve", "delete"}:
        raise ValueError("Yanlış action")
    perm = effective_permissions(user).get(module_id)
    return bool(perm and perm.get(f"can_{action}"))


def get_visible_module_tree(user):
    all_modules = list(Module.objects.all().order_by("order", "title"))
    by_parent = {}
    for m in all_modules:
        by_parent.setdefault(m.parent_id, []).append(m)

    permitted = effective_permissions(user)
    own_org_only = not (user.is_superuser or user.is_staff or _is_unrestricted(user))

    def is_visible(module) -> bool:
        if permitted.get(module.id, {}).get("can_view"):
            return True
        return any(is_visible(c) for c in by_parent.get(module.id, []))

    def build(module):
        perm = permitted.get(module.id, NONE)
        title, meta = module.title, module.meta
        if module.key == ORG_MODULE_KEY and own_org_only:
            title, meta = "Mənim təşkilatım", "own"
        return {
            "id": module.id,
            "key": module.key,
            "title": title,
            "description": module.description,
            "meta": meta,
            "icon": module.icon,
            "can_view": bool(perm.get("can_view")),
            "can_create": bool(perm.get("can_create")),
            "can_edit": bool(perm.get("can_edit")),
            "can_approve": bool(perm.get("can_approve")),
            "can_delete": bool(perm.get("can_delete")),
            "children": [build(c) for c in by_parent.get(module.id, []) if is_visible(c)],
        }

    return [build(m) for m in by_parent.get(None, []) if is_visible(m)]


def filter_grantable_modules(actor, modules_data):
    """Qurum admini yalnız ÖZ təşkilatına açıq modullara icazə verə bilər (və təsdiq-axını
    modullarına yox). Nazirlik admini üçün süzgəc yoxdur."""
    if actor.is_superuser or actor.is_staff:
        return list(modules_data or [])
    allowed = effective_permissions(actor)
    blocked = set(Module.objects.filter(key__in={"tesdiq-axini", "tesdiq-huquqlari", "inzibatci-paneli"}).values_list("id", flat=True))
    out = []
    for item in modules_data or []:
        mid = item.get("module")
        if mid in blocked:
            continue
        if _is_unrestricted(actor) or (mid in allowed and allowed[mid].get("can_view")):
            out.append(item)
    return out
