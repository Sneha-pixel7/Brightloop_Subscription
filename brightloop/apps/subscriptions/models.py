from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.core.exceptions import BusinessRuleError
from apps.core.utils import MONEY_FIELD, ZERO, money

PAYMENT_TERM_CHOICES = [
    (0, "Immediate"),
    (15, "Net 15 days"),
    (30, "Net 30 days"),
    (45, "Net 45 days"),
    (60, "Net 60 days"),
]


class QuotationTemplate(models.Model):
    """Reusable starting point so reps don't build every offer from scratch."""

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    plan = models.ForeignKey("catalog.Plan", on_delete=models.PROTECT, related_name="quotation_templates")
    validity_days = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    payment_term_days = models.PositiveSmallIntegerField(choices=PAYMENT_TERM_CHOICES, default=15)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class QuotationTemplateLine(models.Model):
    template = models.ForeignKey(QuotationTemplate, on_delete=models.CASCADE, related_name="lines")
    plan = models.ForeignKey("catalog.Plan", on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    def __str__(self):
        return f"{self.plan} x {self.quantity}"


class Subscription(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUOTATION = "quotation", "Quotation"
        CONFIRMED = "confirmed", "Confirmed"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    # Draft -> Quotation -> Confirmed -> Active -> Closed.
    # A not-yet-active subscription may be cancelled straight to Closed.
    ALLOWED_TRANSITIONS = {
        Status.DRAFT: {Status.QUOTATION, Status.CONFIRMED, Status.CLOSED},
        Status.QUOTATION: {Status.CONFIRMED, Status.CLOSED},
        Status.CONFIRMED: {Status.ACTIVE, Status.CLOSED},
        Status.ACTIVE: {Status.CLOSED},
        Status.CLOSED: set(),
    }

    number = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    customer = models.ForeignKey("accounts.Customer", on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey("catalog.Plan", on_delete=models.PROTECT, related_name="subscriptions")
    template = models.ForeignKey(
        QuotationTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="subscriptions"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True, help_text="Expiry date.")
    next_billing_date = models.DateField(null=True, blank=True)
    quotation_valid_until = models.DateField(null=True, blank=True)
    payment_term_days = models.PositiveSmallIntegerField(choices=PAYMENT_TERM_CHOICES, default=15)
    is_paused = models.BooleanField(default=False, help_text="Paused subscriptions are skipped by billing.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_subscriptions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="sub_status_idx"),
            models.Index(fields=["next_billing_date"], name="sub_next_billing_idx"),
            models.Index(fields=["status", "next_billing_date"], name="sub_status_nextbill_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=models.F("start_date")),
                name="sub_end_date_after_start",
            ),
        ]

    def __str__(self):
        return self.number or f"Subscription #{self.pk}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.number:
            self.number = f"SUB-{self.pk:05d}"
            super().save(update_fields=["number"])

    # --- lifecycle ---------------------------------------------------------
    def can_transition_to(self, new_status) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    @transaction.atomic
    def transition_to(self, new_status):
        """Move to `new_status` or raise BusinessRuleError. The only way status should change."""
        if not self.can_transition_to(new_status):
            raise BusinessRuleError(
                f"Cannot move a subscription from {self.get_status_display()} to "
                f"{Subscription.Status(new_status).label}."
            )
        if new_status in (self.Status.CONFIRMED, self.Status.ACTIVE) and not self.lines.exists():
            raise BusinessRuleError("Add at least one subscription line before confirming or activating.")
        if new_status == self.Status.ACTIVE and self.next_billing_date is None:
            self.next_billing_date = self.start_date
        if new_status == self.Status.CLOSED:
            self.is_paused = False
        self.status = new_status
        self.save()
        return self

    @property
    def subtotal(self) -> Decimal:
        return self.lines.aggregate(total=Sum("line_total"))["total"] or ZERO


class SubscriptionLine(models.Model):
    """Agreed price is copied here, so later plan price changes never alter existing subscriptions."""

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="lines")
    plan = models.ForeignKey("catalog.Plan", on_delete=models.PROTECT, related_name="subscription_lines")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(**MONEY_FIELD, validators=[MinValueValidator(Decimal("0"))])
    tax_rule = models.ForeignKey(
        "catalog.TaxRule", on_delete=models.PROTECT, null=True, blank=True, related_name="subscription_lines"
    )
    line_total = models.DecimalField(**MONEY_FIELD, editable=False, default=ZERO)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="subline_quantity_gte_1"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="subline_unit_price_gte_0"),
            models.CheckConstraint(condition=Q(line_total__gte=0), name="subline_line_total_gte_0"),
        ]

    def __str__(self):
        return f"{self.subscription} - {self.plan.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        if self.unit_price is None:
            self.unit_price = self.plan.effective_price
        self.line_total = money(self.unit_price * self.quantity)
        super().save(*args, **kwargs)
