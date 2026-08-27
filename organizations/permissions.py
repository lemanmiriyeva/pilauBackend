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


def is_msn_admin(user) -> bool:
    """Öz təşkilatı Nazirliyin ÖZÜ (Organization.code == 'msn') olan qurum admini - adi qurum
    admininin əksinə, bu şəxs BÜTÜN təşkilatların datasını görə bilməlidir (MSN-in daxili
    strukturu, tək bir 'qurum'a aid deyil)."""
    if not is_org_admin(user):
        return False
    org = getattr(user, "organization", None)
    return bool(org and org.code == org.CODE_MSN)


def can_view_all_organizations(user) -> bool:
    """Bütün təşkilatların datasını (lisenziyalar, hesabatlar, istifadəçilər, departament/vəzifə,
    təsdiq icazələri və s.) görə bilən istifadəçidirmi? Üç yoldan biri kifayətdir:
    - Nazirlik admini (is_staff/is_superuser)
    - MSN təşkilatının öz admini (is_msn_admin)
    - 'Rəhbər kadr' bayrağı aktiv olan istənilən istifadəçi (bax User.rehber_kadr)
    """
    return bool(is_full_admin(user) or is_msn_admin(user) or getattr(user, "rehber_kadr", False))


def scoped_organization_ids(user):
    """İstifadəçinin baxa biləcəyi təşkilat id-lərinin siyahısı.

    can_view_all_organizations(user) True olduqda None qaytarılır (= filtr tətbiq olunmasın,
    hər şey görünsün). Təşkilatı olmayan istifadəçi üçün boş siyahı (heç nə görünmür).
    """
    if can_view_all_organizations(user):
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


class IsFullAdminForCreate(BasePermission):
    """Yeni təşkilat yaratmaq (POST) YALNIZ Nazirlik admininə (is_staff/is_superuser) açıqdır -
    qurum admininin bu hüququ yoxdur (o, yalnız ÖZ təşkilatını redaktə edə bilər, bax
    OrganizationDetailView). Siyahı (GET) hər authenticated istifadəçiyə açıqdır (queryset öz
    əhatəsinə görə məhdudlaşdırılır, bax scoped_organization_ids)."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return is_full_admin(u)