from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Role

User = get_user_model()


class PasswordPolicyTests(TestCase):
    def assertRejected(self, password):
        with self.assertRaises(ValidationError):
            validate_password(password)

    def test_exactly_eight_characters_is_rejected(self):
        self.assertRejected("Abcdef1!")  # 8 chars: must be MORE than 8

    def test_nine_characters_with_all_classes_is_accepted(self):
        validate_password("Abcdefg1!")

    def test_missing_uppercase_rejected(self):
        self.assertRejected("abcdefgh1!x")

    def test_missing_lowercase_rejected(self):
        self.assertRejected("ABCDEFGH1!X")

    def test_missing_special_character_rejected(self):
        self.assertRejected("Abcdefgh1xyz")


class UserModelTests(TestCase):
    def test_email_is_normalised_and_unique_case_insensitively(self):
        User.objects.create_user("Person@Example.com", "Abcdefg1!")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("person@example.COM", "Abcdefg1!")

    def test_default_role_is_customer(self):
        user = User.objects.create_user("c@example.com", "Abcdefg1!")
        self.assertEqual(user.role, Role.CUSTOMER)
        self.assertFalse(user.is_staff)

    def test_only_admin_role_can_open_django_admin(self):
        staff = User.objects.create_user("s@example.com", "Abcdefg1!", role=Role.STAFF)
        admin = User.objects.create_user("a@example.com", "Abcdefg1!", role=Role.ADMIN)
        self.assertFalse(staff.is_staff)
        self.assertTrue(admin.is_staff)
