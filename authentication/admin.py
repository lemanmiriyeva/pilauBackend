from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from permissions_module.models import UserModulePermission

from .constants import DEFAULT_INITIAL_PASSWORD
from .models import PasswordResetCode, User


class UserAddForm(forms.ModelForm):
    """Admin paneldə "İstifadəçi əlavə et" formu - şifrə sahəsi YOXDUR.

    Django-nun standart UserCreationForm-u password1/password2 tələb edir və bu şifrələri
    AUTH_PASSWORD_VALIDATORS-dan (min. 10 simvol) keçirir - ilkin şifrə "AA123456!" isə
    9 simvoldur, ona görə həmin formada heç vaxt qəbul olunmurdu. Burada şifrə soruşulmur:
    hər yeni istifadəçiyə sabit ilkin şifrə təyin olunur və ilk girişdə (2FA qurulandan sonra)
    onu dəyişməyə məcbur edilir (bax authentication/constants.py, İnzibatçı paneli API-si ilə
    eyni davranış - views.CreateUserView)."""

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(DEFAULT_INITIAL_PASSWORD)
        user.must_change_password = True
        if commit:
            user.save()
            self._save_m2m()
        return user


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

    # "İstifadəçi əlavə et" səhifəsi: şifrə sahəsi yoxdur, ilkin şifrə avtomatik təyin olunur.
    add_form = UserAddForm
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "first_name", "last_name"),
        }),
    )

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Əlavə məlumat", {"fields": ("phone", "fin_kod", "id_card_serial", "organization")}),
        # Təhlükəsizlik bölməsinə must_change_password əlavə olundu
        ("Təhlükəsizlik", {"fields": (
            "must_change_password",
            "failed_login_attempts", "is_locked", "locked_at",
            "totp_confirmed", "totp_secret_encrypted","is_org_admin"
        )}),
    )

    actions = ["unlock_users", "reset_totp_for_users", "force_password_change", "reset_to_initial_password"]

    @admin.action(description="Seçilmiş istifadəçilərin kilidini aç")
    def unlock_users(self, request, queryset):
        queryset.update(is_locked=False, locked_at=None, failed_login_attempts=0)

    @admin.action(description="Seçilmiş istifadəçilərin 2FA-sını sıfırla")
    def reset_totp_for_users(self, request, queryset):
        for user in queryset:
            user.reset_totp()

    @admin.action(description=f"Seçilmiş istifadəçiləri ilkin şifrəyə ({DEFAULT_INITIAL_PASSWORD}) sıfırla (ilk giriş axını yenidən başlayır)")
    def reset_to_initial_password(self, request, queryset):
        # 2FA da sıfırlanır: giriş axınında şifrə dəyişdirmə addımı yalnız 2FA QURULANDAN sonra
        # soruşulur (bax TOTPSetupConfirmView). 2FA sıfırlanmasa, istifadəçi ilkin şifrə ilə
        # qalardı, çünki normal giriş (TOTPVerifyView) şifrə dəyişdirməyə yönləndirmir.
        count = 0
        for user in queryset:
            user.set_password(DEFAULT_INITIAL_PASSWORD)
            user.must_change_password = True
            user.failed_login_attempts = 0
            user.is_locked = False
            user.locked_at = None
            user.totp_secret_encrypted = None
            user.totp_confirmed = False
            user.save()
            count += 1
        self.message_user(
            request,
            f"{count} istifadəçi ilkin şifrəyə sıfırlandı. İlk girişdə 2FA qurub yeni şifrə təyin edəcəklər.",
            messages.SUCCESS,
        )

    # Admin paneldən toplu şəkildə istifadəçini şifrə dəyişməyə məcbur etmək üçün action:
    @admin.action(description="Seçilmiş istifadəçiləri şifrə dəyişməyə məcbur et (must_change_password=True)")
    def force_password_change(self, request, queryset):
        queryset.update(must_change_password=True)

        
@admin.register(PasswordResetCode)
class PasswordResetCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used", "requested_ip")
    list_filter = ("used",)
    readonly_fields = ("code_hash",)