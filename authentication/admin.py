from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from permissions_module.models import UserModulePermission

from .models import PasswordResetCode, User


class UserModulePermissionInline(admin.TabularInline):
    """Bu istifadəçiyə verilmiş modul icazələri - istifadəçinin detalına girəndə
    bütün modul/submodul siyahısı burada inline şəkildə idarə olunur."""
    model = UserModulePermission
    fk_name = "user"
    fields = ("module", "can_view", "can_edit", "can_approve", "granted_by")
    autocomplete_fields = ["module", "granted_by"]
    extra = 1
    verbose_name = "Modul icazəsi"
    verbose_name_plural = "Modul icazələri (Lisenziya/Hesabat/İnzibatçı və s. bütün modul ağacı)"

    def get_queryset(self, request):
        # Modul ağacını "valideyn -> alt-modul" ardıcıllığı ilə düz sırada göstərmək üçün.
        return super().get_queryset(request).select_related("module", "module__parent").order_by(
            "module__parent__order", "module__parent__title", "module__order", "module__title",
        )


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # list_display-ə must_change_password əlavə edirik ki, siyahıda görə biləsiniz
    list_display = ("username", "email", "first_name", "last_name",
                    "organization", "is_locked", "totp_confirmed", "must_change_password", "is_active")

    # list_filter-ə əlavə edirik ki, şifrəsini dəyişməli olanları filtr edə biləsiniz
    list_filter = ("is_locked", "totp_confirmed", "must_change_password", "is_active", "organization")

    search_fields = ("username", "email", "first_name", "last_name", "fin_kod")
    readonly_fields = ("totp_secret_encrypted", "failed_login_attempts", "locked_at")
    inlines = [UserModulePermissionInline]

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Əlavə məlumat", {"fields": ("phone", "fin_kod", "id_card_serial", "organization")}),
        # Təhlükəsizlik bölməsinə must_change_password əlavə olundu
        ("Təhlükəsizlik", {"fields": (
            "must_change_password",
            "failed_login_attempts", "is_locked", "locked_at",
            "totp_confirmed", "totp_secret_encrypted",
        )}),
    )

    actions = ["unlock_users", "reset_totp_for_users", "force_password_change"]

    @admin.action(description="Seçilmiş istifadəçilərin kilidini aç")
    def unlock_users(self, request, queryset):
        queryset.update(is_locked=False, locked_at=None, failed_login_attempts=0)

    @admin.action(description="Seçilmiş istifadəçilərin 2FA-sını sıfırla")
    def reset_totp_for_users(self, request, queryset):
        for user in queryset:
            user.reset_totp()

    # İrəlidəadmin paneldən toplu şəkildə istifadəçini şifrə dəyişməyə məcbur etmək üçün action da əlavə edə bilərsiniz:
    @admin.action(description="Seçilmiş istifadəçiləri şifrə dəyişməyə məcbur et (must_change_password=True)")
    def force_password_change(self, request, queryset):
        queryset.update(must_change_password=True)

        
@admin.register(PasswordResetCode)
class PasswordResetCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used", "requested_ip")
    list_filter = ("used",)
    readonly_fields = ("code_hash",)