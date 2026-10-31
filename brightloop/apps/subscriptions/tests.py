from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Customer
from apps.catalog.models import Plan, Product, ProductVariant
from apps.core.exceptions import BusinessRuleError

from .models import Subscription, SubscriptionLine

User = get_user_model()
S = Subscription.Status


class SubscriptionLifecycleTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("c@example.com", "Abcdefg1!")
        self.customer = Customer.objects.create(user=user, full_name="C")
        self.plan = Plan.objects.create(product=Product.objects.create(name="P"), name="Pl", price=Decimal("100"))
        self.sub = Subscription.objects.create(customer=self.customer, plan=self.plan, start_date=date(2026, 3, 1))

    def add_line(self):
        SubscriptionLine.objects.create(subscription=self.sub, plan=self.plan, quantity=1, unit_price=self.plan.price)

    def test_happy_path_draft_to_closed(self):
        self.add_line()
        for status in (S.QUOTATION, S.CONFIRMED, S.ACTIVE, S.CLOSED):
            self.sub.transition_to(status)
        self.assertEqual(self.sub.status, S.CLOSED)

    def test_activation_sets_next_billing_date_to_start_date(self):
        self.add_line()
        self.sub.transition_to(S.CONFIRMED)
        self.sub.transition_to(S.ACTIVE)
        self.assertEqual(self.sub.next_billing_date, date(2026, 3, 1))

    def test_invalid_transitions_are_rejected(self):
        self.add_line()
        with self.assertRaises(BusinessRuleError):
            self.sub.transition_to(S.ACTIVE)  # Draft -> Active skips Confirmed
        self.sub.transition_to(S.CONFIRMED)
        self.sub.transition_to(S.ACTIVE)
        with self.assertRaises(BusinessRuleError):
            self.sub.transition_to(S.DRAFT)  # no going back

    def test_closed_is_terminal(self):
        self.sub.transition_to(S.CLOSED)
        with self.assertRaises(BusinessRuleError):
            self.sub.transition_to(S.ACTIVE)

    def test_cannot_confirm_without_lines(self):
        with self.assertRaises(BusinessRuleError):
            self.sub.transition_to(S.CONFIRMED)


class VariantPricingTests(TestCase):
    def test_variant_extra_price_is_added_to_plan_price(self):
        product = Product.objects.create(name="ERP")
        odoo = ProductVariant.objects.create(
            product=product, name="Odoo", attribute="Brand", extra_price=Decimal("560.00")
        )
        plan = Plan.objects.create(product=product, variant=odoo, name="ERP Odoo", price=Decimal("1000.00"))
        self.assertEqual(plan.effective_price, Decimal("1560.00"))
