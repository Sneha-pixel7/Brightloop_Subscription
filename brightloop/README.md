# Brightloop - Subscription Management Platform

Django + DRF + PostgreSQL 16 + Bootstrap 5, run entirely with Docker.

> **Status: foundation complete (Phases 1-2).** Docker, settings, custom user with roles,
> and the full data model with database-level integrity are done and tested.
> See `docs/PLAN.md` for what is next and how to split the work.

## Run it

```bash
docker compose up --build
```

- App: http://localhost:8000
- Health check: http://localhost:8000/health/
- Django admin (temporary data entry until the UI is built): http://localhost:8000/admin/

The web container waits for Postgres, runs migrations, then starts the server.
Database data lives in the `pgdata` Docker volume and survives restarts.
Create a first admin:

```bash
docker compose exec web python manage.py createsuperuser
```

## Run the tests (inside Docker)

```bash
docker compose run --rm web python manage.py test apps -v 2
```

## Project layout

```
config/             settings, urls
apps/core/          money helpers, billing-period math, /health/, wait_for_db command
apps/accounts/      custom User (admin/staff/customer), Customer, password policy
apps/catalog/       Product, Variant, Plan, TaxRule, DiscountRule
apps/subscriptions/ Subscription (state machine), lines, quotation templates
apps/billing/       Invoice, InvoiceLine, Payment, DiscountRedemption
```

## Integrity guarantees already enforced by PostgreSQL

- `UNIQUE(subscription, period_start, period_end)` on invoices (no double billing)
- unique `idempotency_key` on invoices and payments
- `outstanding_amount = total_amount - amount_paid`, `0 <= amount_paid <= total_amount`
- an invoice can be `paid` only when outstanding is 0
- payment amount > 0; case-insensitive unique email

## Password policy

More than 8 characters, with an uppercase letter, a lowercase letter and a special character
(`apps/accounts/validators.py`).

## Demo credentials

Added with the seed command in Phase 10.
