# Brightloop - Hackathon Plan (3 people, 5 hours)

## What the problem statement (PDF) adds beyond the build spec

Already built into the data model (foundation done):

| PDF requirement | Where it lives |
|---|---|
| Product type, sales price, cost price, notes | `catalog.Product` |
| Variants that add to price (Odoo brand = +560) | `catalog.ProductVariant.extra_price`, `Plan.effective_price` |
| Daily / weekly / monthly / yearly billing | `catalog.BillingPeriod`, `core.utils.add_period` |
| Min quantity, availability dates | `catalog.Plan` |
| Per-plan auto-close / early close / pause / renew | `Plan.auto_close`, `allow_early_close`, `allow_pause`, `allow_renewal` |
| Quotation templates with validity days | `subscriptions.QuotationTemplate` (+ lines) |
| Subscription number, payment terms, expiry | `Subscription.number`, `payment_term_days`, `end_date` |
| Draft > Quotation > Confirmed > Active > Closed | `Subscription.transition_to` |
| Pause a subscription | `Subscription.is_paused` (billing skips paused) |
| Configurable taxes per line | `catalog.TaxRule`, `SubscriptionLine.tax_rule` |
| Discount rules (fixed/%, min purchase/qty, dates, usage limit, product or whole subscription) | `catalog.DiscountRule`, `billing.DiscountRedemption` |
| Cancel an invoice | `Invoice.Status.CANCELLED` |
| Payment method, amount, date, note | `billing.Payment` |
| Password reset by email | settings ready (console email); views in Phase 3 |
| Only admin can add staff | enforced in Phase 3 views |

Still to build (the work below): everything user-facing, billing engine, payments service, dashboard, seed, README demo guide.

## Suggested split (3 people)

| Person | Owns | Phases |
|---|---|---|
| **A - Backend core** | Billing engine (`run_billing`), discount application, payment service (idempotent), invoice confirm/cancel/send | 6, 7 |
| **B - Auth + CRUD + API** | Login/register/reset, role permissions, Products/Variants/Plans/Customers/Subscriptions CRUD, DRF endpoints | 3, 4, 5 |
| **C - UI + dashboard + seed** | Base layout/sidebar (Bootstrap 5), dashboards for 3 roles, invoice/payment pages, seed command, README/demo | 8, 9, 10 |

## 5-hour timeline

| Time | Goal |
|---|---|
| 0:00-0:30 | Foundation (done): everyone runs `docker compose up --build`, reads this plan |
| 0:30-2:00 | A: billing engine. B: auth + permissions + catalog CRUD. C: base template + dashboard skeleton |
| 2:00-3:30 | A: payments + invoice actions. B: subscriptions UI + customer portal. C: dashboard queries + invoice/payment pages |
| 3:30-4:15 | Seed data, full end-to-end run-through, fix bugs |
| 4:15-4:45 | Tests green inside Docker, README, demo script |
| 4:45-5:00 | Buffer. Do NOT start new features. |

## Rules to avoid merge pain

- One app per person where possible (models are already split by app).
- Never edit an existing migration; add a new one. If two people change models, re-run `makemigrations` after merging.
- All money is `Decimal`; use `apps.core.utils.money()`.
- Status changes only via `transition_to()`; payments only via the payment service (never edit `amount_paid` by hand).

## Nice-to-have extras if time remains (in priority order)

1. Invoice PDF / print view (browser print CSS is enough)
2. MRR (monthly recurring revenue) card: normalise yearly/weekly plans to monthly
3. Dashboard filters (date range, status) + CSV export
4. Subscription renew / pause buttons honouring the plan flags
5. Auto-close subscriptions past their end date inside `run_billing`
