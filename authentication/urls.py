from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    path("totp-setup-begin/", views.TOTPSetupBeginView.as_view(), name="totp_setup_begin"),
    path("totp-setup-confirm/", views.TOTPSetupConfirmView.as_view(), name="totp_setup_confirm"),
    path("totp-verify/", views.TOTPVerifyView.as_view(), name="totp_verify"),
    path("totp/request-admin-help/", views.TOTPRequestAdminHelpView.as_view(), name="totp_request_admin_help"),
    path("totp/request-admin-help/confirm/", views.TOTPAdminHelpConfirmView.as_view(), name="totp_admin_help_confirm"),

    path("password/forgot/", views.ForgotPasswordRequestView.as_view(), name="forgot_password_request"),
    path("password/forgot/confirm/", views.ForgotPasswordConfirmView.as_view(), name="forgot_password_confirm"),
    path("password/change/", views.ChangePasswordView.as_view(), name="change_password"),
    path("password/first-login-set/", views.FirstLoginPasswordSetView.as_view(), name="first_login_password_set"),

    path("me/", views.MeView.as_view(), name="me"),

    path("admin/users/", views.UserListView.as_view(), name="admin_user_list"),
    path("admin/users/create/", views.CreateUserView.as_view(), name="admin_create_user"),
    path("admin/users/unlock/", views.AdminUnlockUserView.as_view(), name="admin_unlock_user"),
    path("admin/users/reset-totp/", views.AdminResetTOTPView.as_view(), name="admin_reset_totp"),
    path("admin/users/<int:pk>/", views.UserAdminDetailView.as_view(), name="admin_user_detail"),
    path("my-organization-options/", views.MyOrganizationOptionsView.as_view(), name="my_organization_options"),
]
