import re

from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    """Backend password policy:

    - MORE than 8 characters (so at least 9)
    - at least one uppercase letter
    - at least one lowercase letter
    - at least one special character (anything that is not a letter or digit)
    """

    min_length = 9

    def validate(self, password, user=None):
        errors = []
        if len(password) < self.min_length:
            errors.append("Password must be more than 8 characters long.")
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter.")
        if not re.search(r"[^A-Za-z0-9]", password):
            errors.append("Password must contain at least one special character.")
        if errors:
            raise ValidationError(errors, code="password_too_weak")

    def get_help_text(self):
        return (
            "Your password must be more than 8 characters and include an uppercase letter, "
            "a lowercase letter and a special character."
        )
