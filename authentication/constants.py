"""Autentifikasiya modulunun ortaq sabitləri.

DEFAULT_INITIAL_PASSWORD - admin tərəfindən (həm İnzibatçı paneli API-si, həm də Django admin
paneli vasitəsilə) yaradılan BÜTÜN yeni istifadəçilər üçün sabit ilkin şifrə. İstifadəçi bununla
ilk dəfə daxil olanda 2FA qurur, sonra məcburi qaydada öz şifrəsini təyin edir
(bax views.LoginView / TOTPSetupConfirmView / FirstLoginPasswordSetView).

QEYD: Bu şifrə 9 simvoldur, AUTH_PASSWORD_VALIDATORS (min. 10 simvol) isə ona uyğun gəlmir -
ona görə bu şifrə HEÇ VAXT validate_password()-dən keçirilməməlidir, birbaşa set_password() ilə
təyin olunur. İstifadəçinin özünün təyin etdiyi yeni şifrə isə validatorlardan keçir.
"""

DEFAULT_INITIAL_PASSWORD = "AA123456!"
