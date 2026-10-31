from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.exceptions import BusinessRuleError
from apps.core.utils import MONEY_FIELD, ZERO


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    # Draft -> Confirmed -> Paid. PAID is reached only through payments (see payments service).
    ALLOWED_TRANSITIONS = {
        Status.DRAFT: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.PAID, Status.CANCELLED},
        Status.PAID: set(),
        Status.CANCELLED: set(),
    }

    invoice_number = models.CharField(max_length=30, unique=True, null=True, blank=True, editable=False)
    customer = models.ForeignKey("accounts.Customer", on_delete=models.PROTECT, related_name="invoices")
    subscription = models.ForeignKey("subscriptions.Subscription", on_delete=models.PROTECT, related_name="invoices")
    period_start = models.DateField()
    period_end = models.DateField()

    subtotal = models.DecimalField(**MONEY_FIELD, default=ZERO)
    discount_amount = models.DecimalField(**MONEY_FIELD, default=ZERO)
    tax_amount = models.DecimalField(**MONEY_FIELD, default=ZERO)
    total_amount = models.DecimalField(**MONEY_FIELD, default=ZERO)
    amount_paid = models.DecimalField(**MONEY_FIELD, default=ZERO)
    outstanding_amount = models.DecimalField(**MONEY_FIELD, default=ZERO)

    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    idempotency_key = models.CharField(max_length=120, unique=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status"], name="inv_status_idx"),
            models.Index(fields=["due_date"], name="inv_due_date_idx"),
            models.Index(fields=["status", "due_date"], name="inv_status_due_idx"),
            models.Index(fields=["customer", "status"], name="inv_customer_status_idx"),
        ]
        constraints = [
            # Double-billing guard: one invoice per subscription per billing period, enforced by the database.
            models.UniqueConstraint(
                fields=["subscription", "period_start", "period_end"], name="uniq_invoice_subscription_period"
            ),
            models.CheckConstraint(condition=Q(period_end__gte=F("period_start")), name="inv_period_end_after_start"),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0) & Q(discount_amount__gte=0) & Q(tax_amount__gte=0) & Q(total_amount__gte=0),
                name="inv_amounts_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(amount_paid__gte=0) & Q(amount_paid__lte=F("total_amount")),
                name="inv_paid_between_0_and_total",
            ),
            models.CheckConstraint(
                condition=Q(outstanding_amount=F("total_amount") - F("amount_paid")),
                name="inv_outstanding_equals_total_minus_paid",
            ),
            # PAID only when nothing is outstanding.
            models.CheckConstraint(
                condition=~Q(status="paid") | Q(outstanding_amount=0), name="inv_paid_requires_zero_outstanding"
            ),
        ]

    def __str__(self):
        return self.invoice_number or f"Invoice #{self.pk}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.invoice_number:
            self.invoice_number = f"INV-{self.pk:06d}"
            super().save(update_fields=["invoice_number"])

    def can_transition_to(self, new_status) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status):
        if not self.can_transition_to(new_status):
            raise BusinessRuleError(
                f"Cannot move an invoice from {self.get_status_display()} to {Invoice.Status(new_status).label}."
            )
        if new_status == self.Status.PAID and self.outstanding_amount != 0:
            raise BusinessRuleError("An invoice can only be Paid when its outstanding balance is zero.")
        self.status = new_status
        self.save()
        return self

    @property
    def is_overdue(self) -> bool:
        return (
            self.status == self.Status.CONFIRMED
            and self.outstanding_amount > 0
            and self.due_date < timezone.localdate()
        )


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=300)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(**MONEY_FIELD)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    total = models.DecimalField(**MONEY_FIELD)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="invline_quantity_gte_1"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="invline_unit_price_gte_0"),
            models.CheckConstraint(condition=Q(total__gte=0), name="invline_total_gte_0"),
        ]

    def __str__(self):
        return f"{self.invoice} - {self.description}"


class DiscountRedemption(models.Model):
    """Records that a discount was applied to an invoice (drives usage limits and audit)."""

    discount = models.ForeignKey("catalog.DiscountRule", on_delete=models.PROTECT, related_name="redemptions")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="discount_redemptions")
    amount = models.DecimalField(**MONEY_FIELD)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["discount", "invoice"], name="uniq_discount_per_invoice"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="redemption_amount_gt_0"),
        ]

    def __str__(self):
        return f"{self.discount} on {self.invoice}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        UPI = "upi", "UPI"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CHEQUE = "cheque", "Cheque"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(**MONEY_FIELD, validators=[MinValueValidator(Decimal("0.01"))])
    payment_method = models.CharField(max_length=20, choices=Method.choices, default=Method.BANK_TRANSFER)
    transaction_reference = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=120, unique=True)
    payment_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMPLETED)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="recorded_payments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        indexes = [
            models.Index(fields=["status"], name="pay_status_idx"),
            models.Index(fields=["payment_date"], name="pay_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_gt_0"),
        ]

    def __str__(self):
        return f"{self.amount} on {self.invoice}"
