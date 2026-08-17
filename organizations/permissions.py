"""
Təşkilat-səviyyəli görünürlük/icazə üçün ortaq köməkçilər.

İstifadə sahələri: licenses (PermitDocument), organizations (Organization),
authentication (User siyahısı/redaktəsi). Qayda sadədir:

- is_staff / is_superuser (MSN inzibatçısı) - məhdudiyyət yoxdur, hər şeyi görür/redaktə edir.
- is_org_admin=True (qurum admini) - öz təşkilatı VƏ onun bütün alt-təşkilatları daxilində
  tam görünürlük və redaktə icazəsi var (Lisenziya/icazə sənədləri, Təşkilatlar, İstifadəçilər).
- Adi istifadəçi (nə staff, nə də org admin) - yalnız öz təşkilatının məlumatlarını görür,
  redaktə edə bilmir (view səviyyəsində ayrıca yoxlanılır).
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


def is_full_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def is_org_admin(user) -> bool:
    return bool(user and user.is_authenticated and getattr(user, "is_org_admin", False))


def scoped_organization_ids(user):
    """İstifadəçinin baxa biləcəyi təşkilat id-lərinin siyahısı.

    Tam admin üçün None qaytarılır (= filtr tətbiq olunmasın, hər şey görünsün).
    Təşkilatı olmayan istifadəçi üçün boş siyahı (heç nə görünmür).
    """
    if is_full_admin(user):
        return None
    if not getattr(user, "organization_id", None):
        return []
    return user.organization.descendant_ids()


class IsStaffOrOrgAdmin(BasePermission):
    """Sadəcə MSN inzibatçısı və ya qurum adminini buraxır (İstifadəçilər idarəetməsi kimi
    həssas endpoint-lər üçün). Queryset-in özünü öz təşkilatına məhdudlaşdırmaq view-in işidir."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser or is_org_admin(u)))


class IsStaffOrOrgAdminForWrite(BasePermission):
    """Oxumaq (GET/HEAD/OPTIONS) hər authenticated istifadəçiyə açıqdır (queryset öz təşkilatına
    görə məhdudlaşdırılır); yazma (POST/PATCH/PUT/DELETE) yalnız staff və ya qurum adminindən
    qəbul olunur. Obyektin doğrudan həmin istifadəçinin təşkilatına aid olub-olmadığını view-dəki
    queryset scoping həll edir (bax: scoped_organization_ids)."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(u.is_staff or u.is_superuser or is_org_admin(u))