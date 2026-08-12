import re

from django.core.exceptions import ValidationError


class ComplexityValidator:
    """
    Sifrede boyuk herf, kicik herf, reqem ve xususi simvol olmasini teleb edir.
    Django-nun default validatorlari yalnix uzunluq/common-password yoxlayir - bu daha serdir.
    """

    def validate(self, password, user=None):
        errors = []
        if not re.search(r"[A-Z]", password):
            errors.append("Şifrə ən azı 1 böyük hərf ehtiva etməlidir.")
        if not re.search(r"[a-z]", password):
            errors.append("Şifrə ən azı 1 kiçik hərf ehtiva etməlidir.")
        if not re.search(r"\d", password):
            errors.append("Şifrə ən azı 1 rəqəm ehtiva etməlidir.")
        if not re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>/?\\|`~]", password):
            errors.append("Şifrə ən azı 1 xüsusi simvol ehtiva etməlidir.")
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return "Şifrə böyük/kiçik hərf, rəqəm və xüsusi simvol ehtiva etməlidir (min. 10 simvol)."
