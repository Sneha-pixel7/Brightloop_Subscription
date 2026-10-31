from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.utils import MONEY_FIELD, ZERO

NON_NEGATIVE = [MinValueValidator(Decimal("0"))]


class Product(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    class ProductType(models.TextChoices):
        SOFTWARE = "software", "Software"
        SERVICE = "service", "Service"
        ADDON = "addon", "Add-on"
        PHYSICAL = "physical", "Physical goods"

    name = models.CharField(max_length=200, unique=True)
    product_type = models.CharField(max_length=20, choices=ProductType.choices, default=ProductType.SOFTWARE)
    sales_price = models.DecimalField(**MONEY_FIELD, default=ZERO, validators=NON_NEGATIVE)
    cost_price = models.DecimalField(**MONEY_FIELD, default=ZERO, validators=NON_NEGATIVE)
    description = models.TextField("Notes", blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(sales_price__gte=0), name="product_sales_price_gte_0"),
            models.CheckConstraint(condition=Q(cost_price__gte=0), name="product_cost_price_gte_0"),
        ]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    """A choice within a product, e.g. attribute='Brand', name='Odoo', extra_price=560."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=200)
    attribute = models.CharField(max_length=100, blank=True, help_text="e.g. Brand, Edition, Size")
    extra_price = models.DecimalField(
        **MONEY_FIELD, default=ZERO, validators=NON_NEGATIVE, help_text="Added to the plan price when chosen."
    )
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    class Meta:
        ordering = ["product__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["product", "name"], name="uniq_variant_name_per_product"),
            models.CheckConstraint(condition=Q(extra_price__gte=0), name="variant_extra_price_gte_0"),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class BillingPeriod(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"


class Plan(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="plans")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="plans"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(**MONEY_FIELD, validators=NON_NEGATIVE, help_text="Price per billing period.")
    billing_period = models.CharField(
        max_length=10, choices=BillingPeriod.choices, default=BillingPeriod.MONTHLY, db_index=True
    )
    min_quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    is_available = models.BooleanField(default=True, db_index=True)

    # Per-plan lifecycle rules chosen by the admin (from the problem statement).
    auto_close = models.BooleanField(default=False, help_text="Close subscriptions automatically when the plan ends.")
    allow_early_close = models.BooleanField(default=True, help_text="Allow closing before the end date.")
    allow_pause = models.BooleanField(default=True, help_text="Allow subscriptions on this plan to be paused.")
    allow_renewal = models.BooleanField(default=True, help_text="Allow subscriptions on this plan to be renewed.")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["product__name", "name"]
        constraints = [
            models.CheckConstraint(condition=Q(price__gte=0), name="plan_price_gte_0"),
            models.CheckConstraint(condition=Q(min_quantity__gte=1), name="plan_min_quantity_gte_1"),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=models.F("start_date")),
                name="plan_end_date_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_billing_period_display()})"

    def clean(self):
        if self.variant_id and self.product_id and self.variant.product_id != self.product_id:
            raise ValidationError({"variant": "This variant does not belong to the selected product."})
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})

    @property
    def effective_price(self) -> Decimal:
        """Plan price plus the chosen variant's add-on (e.g. +560 for the Odoo brand)."""
        extra = self.variant.extra_price if self.variant_id else ZERO
        return self.price + extra

    def is_open_on(self, day=None) -> bool:
        """Can new subscriptions be started on this plan on `day`?"""
        day = day or timezone.localdate()
        if not self.is_available:
            return False
        if self.start_date and day < self.start_date:
            return False
        if self.end_date and day > self.end_date:
            return False
        return True


class TaxRule(models.Model):
    name = models.CharField(max_length=100, unique=True)
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(percentage__gte=0) & Q(percentage__lte=100), name="taxrule_percentage_0_100"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.percentage}%)"


class DiscountRule(models.Model):
    """Admin-created discount. Applied automatically to the next invoice while valid."""

    class DiscountType(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENTAGE = "percentage", "Percentage"

    class AppliesTo(models.TextChoices):
        PRODUCT = "product", "Specific product"
        SUBSCRIPTION = "subscription", "Whole subscription"

    name = models.CharField(max_length=150)
    discount_type = models.CharField(max_length=12, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    value = models.DecimalField(**MONEY_FIELD, help_text="Rupees if fixed, 0-100 if percentage.")
    applies_to = models.CharField(max_length=14, choices=AppliesTo.choices, default=AppliesTo.SUBSCRIPTION)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, null=True, blank=True, related_name="discount_rules"
    )
    min_purchase = models.DecimalField(**MONEY_FIELD, default=ZERO, validators=NON_NEGATIVE)
    min_quantity = models.PositiveIntegerField(default=0)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Leave empty for unlimited use.")
    times_used = models.PositiveIntegerField(default=0, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name="discount_value_gt_0"),
            models.CheckConstraint(
                condition=Q(discount_type="fixed") | Q(value__lte=100), name="discount_percentage_lte_100"
            ),
            models.CheckConstraint(
                condition=Q(applies_to="subscription") | Q(product__isnull=False),
                name="discount_product_required_when_product_scope",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=models.F("start_date")),
                name="discount_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(usage_limit__isnull=True) | Q(times_used__lte=models.F("usage_limit")),
                name="discount_usage_within_limit",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.applies_to == self.AppliesTo.PRODUCT and not self.product_id:
            raise ValidationError({"product": "Choose a product for a product-level discount."})
        if self.discount_type == self.DiscountType.PERCENTAGE and self.value is not None and self.value > 100:
            raise ValidationError({"value": "A percentage discount cannot exceed 100."})

    def is_usable_on(self, day=None) -> bool:
        """Active, inside its date window and not out of uses."""
        day = day or timezone.localdate()
        if not self.is_active or day < self.start_date:
            return False
        if self.end_date and day > self.end_date:
            return False
        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return False
        return True
