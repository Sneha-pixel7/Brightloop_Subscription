from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    STAFF = "staff", "Staff"
    CUSTOMER = "customer", "Customer"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.CUSTOMER)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["role"] = Role.ADMIN
        extra_fields["is_superuser"] = True
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CUSTOMER, db_index=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can open the Django admin site (admins only).")
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]
        constraints = [
            # Emails are unique regardless of letter case.
            models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci"),
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        # Only the Admin role may enter the Django admin site.
        self.is_staff = self.role == Role.ADMIN or self.is_superuser
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN

    @property
    def is_staff_role(self):
        return self.role == Role.STAFF

    @property
    def is_customer_role(self):
        return self.role == Role.CUSTOMER

    @property
    def is_internal(self):
        """Admin or Staff - people who work inside Brightloop."""
        return self.role in (Role.ADMIN, Role.STAFF)


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    @property
    def email(self):
        return self.user.email
