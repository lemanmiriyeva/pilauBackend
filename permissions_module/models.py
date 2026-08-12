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
    can_edit = models.BooleanField("Redaktə", default=False)
    can_approve = models.BooleanField("Təsdiq", default=False)

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


def has_module_permission(user, module_id: int, action: str) -> bool:
    """action: 'view' | 'edit' | 'approve'"""
    if user.is_superuser:
        return True
    field = f"can_{action}"
    if field not in {"can_view", "can_edit", "can_approve"}:
        raise ValueError("Yanlış action")
    return UserModulePermission.objects.filter(
        user=user, module_id=module_id, **{field: True}
    ).exists()


def get_visible_module_tree(user):
    all_modules = list(
        Module.objects.all().order_by("order", "title")
    )
    by_parent = {}
    for m in all_modules:
        by_parent.setdefault(m.parent_id, []).append(m)

    if user.is_superuser:
        permitted = {m.id: {"can_view": True, "can_edit": True, "can_approve": True} for m in all_modules}
    else:
        permitted = {
            p.module_id: {"can_view": p.can_view, "can_edit": p.can_edit, "can_approve": p.can_approve}
            for p in UserModulePermission.objects.filter(user=user)
        }

    def is_visible(module) -> bool:
        if permitted.get(module.id, {}).get("can_view"):
            return True
        return any(is_visible(c) for c in by_parent.get(module.id, []))

    def build(module):
        perm = permitted.get(module.id, {"can_view": False, "can_edit": False, "can_approve": False})
        return {
            "id": module.id,
            "key": module.key,
            "title": module.title,
            "description": module.description,
            "meta": module.meta,
            "icon": module.icon,
            "can_view": bool(perm.get("can_view")),
            "can_edit": bool(perm.get("can_edit")),
            "can_approve": bool(perm.get("can_approve")),
            "children": [build(c) for c in by_parent.get(module.id, []) if is_visible(c)],
        }

    top_level = by_parent.get(None, [])
    return [build(m) for m in top_level if is_visible(m)]