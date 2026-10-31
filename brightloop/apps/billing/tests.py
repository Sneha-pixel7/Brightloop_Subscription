"""Database-level integrity tests: these prove the DB itself refuses bad billing/payment data."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Customer, Role
from apps.catalog.models import Plan, Product
from apps.core.exceptions import BusinessRuleError
from apps.subscriptions.models import Subscription, SubscriptionLine

from .models import Invoice, Payment

User = get_user_model()


class BillingConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user("cust@example.com", "Abcdefg1!", role=Role.CUSTOMER)
        cls.customer = Customer.objects.create(user=user, full_name="Test Customer")
        product = Product.objects.create(name="CRM")
        cls.plan = Plan.objects.create(product=product, name="CRM Monthly", price=Decimal("1000.00"))
        cls.sub = Subscription.objects.create(customer=cls.customer, plan=cls.plan)

    def make_invoice(self, **overrides):
        data = dict(
            customer=self.customer, subscription=self.sub,
            period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            subtotal=Decimal("1000.00"), tax_amount=Decimal("180.00"),
            total_amount=Decimal("1180.00"), amount_paid=Decimal("0.00"),
            outstanding_amount=Decimal("1180.00"), due_date=date(2026, 1, 15),
            idempotency_key=f"sub{self.sub.pk}:2026-01-01:2026-01-31",
        )
        data.update(overrides)
        return Invoice.objects.create(**data)

    def test_subscription_and_invoice_numbers_are_generated(self):
        invoice = self.make_invoice()
        self.assertTrue(self.sub.number.startswith("SUB-"))
        self.assertTrue(invoice.invoice_number.startswith("INV-"))

    def test_same_subscription_period_cannot_be_invoiced_twice(self):
        self.make_invoice()
        with self.assertRaises(IntegrityError), transaction.atomic():
            # Different idempotency key on purpose: the period constraint alone must stop it.
            self.make_invoice(idempotency_key="another-key")

    def test_duplicate_idempotency_key_rejected(self):
        self.make_invoice()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_invoice(period_start=date(2026, 2, 1), period_end=date(2026, 2, 28))

    def test_outstanding_must_equal_total_minus_paid(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_invoice(amount_paid=Decimal("500.00"), outstanding_amount=Decimal("100.00"))

    def test_cannot_overpay_at_database_level(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_invoice(amount_paid=Decimal("2000.00"), outstanding_amount=Decimal("-820.00"))

    def test_paid_status_requires_zero_outstanding(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_invoice(status=Invoice.Status.PAID)

    def test_partial_payment_example_from_spec(self):
        invoice = self.make_invoice(
            amount_paid=Decimal("500.00"), outstanding_amount=Decimal("680.00"), status=Invoice.Status.CONFIRMED
        )
        invoice.amount_paid = Decimal("1180.00")
        invoice.outstanding_amount = Decimal("0.00")
        invoice.status = Invoice.Status.PAID
        invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_payment_must_be_positive_and_idempotency_key_unique(self):
        invoice = self.make_invoice()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(invoice=invoice, amount=Decimal("0.00"), idempotency_key="p0")
        Payment.objects.create(invoice=invoice, amount=Decimal("10.00"), idempotency_key="p1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(invoice=invoice, amount=Decimal("10.00"), idempotency_key="p1")


class InvoiceTransitionTests(TestCase):
    def test_paid_cannot_be_set_with_balance_outstanding(self):
        user = User.objects.create_user("x@example.com", "Abcdefg1!")
        customer = Customer.objects.create(user=user, full_name="X")
        plan = Plan.objects.create(product=Product.objects.create(name="P"), name="Pl", price=Decimal("10"))
        sub = Subscription.objects.create(customer=customer, plan=plan)
        invoice = Invoice.objects.create(
            customer=customer, subscription=sub, period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            total_amount=Decimal("10.00"), outstanding_amount=Decimal("10.00"), due_date=date(2026, 1, 15),
            idempotency_key="k", status=Invoice.Status.CONFIRMED,
        )
        with self.assertRaises(BusinessRuleError):
            invoice.transition_to(Invoice.Status.PAID)

    def test_draft_cannot_jump_to_paid(self):
        user = User.objects.create_user("y@example.com", "Abcdefg1!")
        customer = Customer.objects.create(user=user, full_name="Y")
        plan = Plan.objects.create(product=Product.objects.create(name="P2"), name="Pl2", price=Decimal("10"))
        sub = Subscription.objects.create(customer=customer, plan=plan)
        invoice = Invoice.objects.create(
            customer=customer, subscription=sub, period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            due_date=date(2026, 1, 15), idempotency_key="k2",
        )
        with self.assertRaises(BusinessRuleError):
            invoice.transition_to(Invoice.Status.PAID)


class SubscriptionLineTests(TestCase):
    def test_line_total_and_price_snapshot(self):
        user = User.objects.create_user("z@example.com", "Abcdefg1!")
        customer = Customer.objects.create(user=user, full_name="Z")
        plan = Plan.objects.create(product=Product.objects.create(name="P3"), name="Pl3", price=Decimal("999.99"))
        sub = Subscription.objects.create(customer=customer, plan=plan)
        line = SubscriptionLine.objects.create(subscription=sub, plan=plan, quantity=3, unit_price=plan.price)
        self.assertEqual(line.line_total, Decimal("2999.97"))
        plan.price = Decimal("5000.00")
        plan.save()
        line.refresh_from_db()
        self.assertEqual(line.unit_price, Decimal("999.99"))  # unaffected by later plan price change
