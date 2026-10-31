# Brightloop Subscription

A subscription management system built as a custom **Odoo 17** module for **Makeathon 9.0 (Odoo)**, an 8-hour online hackathon.

## Problem

Businesses that sell recurring plans need one place to manage plans, customers, billing, and renewals. Brightloop Subscription handles the full cycle: define plans, subscribe customers, generate invoices, renew or expire subscriptions automatically, and see which customers are at risk.

## Features

- **Plans:** name, price, billing period (monthly, quarterly, yearly), and description, with validation (price must be greater than 0)
- **Subscriptions:** customer, plan, start and end dates, and a lifecycle (Draft, Active, Paused, Cancelled, Expired) with Activate, Pause, and Cancel buttons and a full change history
- **Validation:** end date cannot be before the start date, and a customer cannot hold two active subscriptions to the same plan
- **Invoicing:** a Create Invoice button on active subscriptions creates a real Odoo customer invoice, linked back to the subscription
- **Scheduled job:** a daily Odoo scheduled action renews active subscriptions that reach their renewal date (creating an invoice and moving the billing period forward) and expires subscriptions past their end date
- **Health status:** each subscription is flagged Healthy, At Risk (paused, or renewal within 7 days), or Critical (overdue invoice), shown as a colored badge and available as a filter
- **Dashboard:** graph and pivot views of subscriptions by plan, status, health, and revenue
- **Dynamic data:** all screens read from the PostgreSQL database. A seed file (`data/demo_data.xml`) loads sample plans, customers, and subscriptions into the database at install, with dates relative to today

## Why a custom module

Odoo's built-in Subscriptions app is Enterprise-only. We built our own subscription models on Odoo Community so the whole project runs locally with no paid license, and the logic is ours to explain.

## Tech Stack

| Part | Choice |
|---|---|
| Platform | Odoo 17 Community (official Docker image) |
| Database | PostgreSQL 15 |
| Custom code | Python (models, validation, scheduled job) and XML (views, data) |
| Run environment | Docker Compose, fully local |
| Version control | Git and GitHub, feature branches with pull requests |

## Run Locally

Requirements: Docker and Git.

```bash
git clone https://github.com/Sneha-pixel7/Brightloop_Subscription.git
cd Brightloop_Subscription
docker compose up -d
```

Create a database with the module and sample data already installed:

```bash
docker compose run --rm odoo odoo -d brightloop -i brightloop_subscription --stop-after-init
docker compose restart odoo
```

Then open http://localhost:8069, choose the `brightloop` database, and log in with `admin` / `admin`. Open **Brightloop** from the app menu.

To stop: `docker compose down`. To reset everything: `docker compose down -v`, then delete the `postgres_data/` folder.

After pulling new code, upgrade the module:

```bash
docker compose run --rm odoo odoo -d brightloop -u brightloop_subscription --stop-after-init
docker compose restart odoo
```

## Demo Flow

1. **Dashboard:** subscriptions by plan and health, with the pivot table.
2. **Plans:** show the three plans and the price validation.
3. **Subscriptions:** create one, activate it, and watch the status and history update.
4. **Invoice:** click Create Invoice and open the generated invoice.
5. **Dashboard again:** refresh to show the numbers change live from the database.
6. **Health:** pause a subscription and see it become At Risk.
7. **Scheduled job:** run it manually (Settings > Technical > Scheduled Actions) to show a renewal and an expiry.

## Project Structure

```
.
├── docker-compose.yml
├── README.md
└── addons/brightloop_subscription/
    ├── __manifest__.py
    ├── models/      # plan, subscription, health, invoice link, scheduled job
    ├── views/       # subscription, dashboard, and UI views and menus
    ├── security/    # access rules
    └── data/        # scheduled action and demo data
```

## Team

| Name | GitHub |
|---|---|
| Sneha | @Sneha-pixel7 |
| (teammate name) | @(teammate-username) |

## Git Workflow

- `main` holds the working copy, and all changes go in through pull requests from feature branches.
- Commits are small and frequent, with messages like `feat:`, `fix:`, and `docs:`.

## Future Work

- Separate Admin and Staff roles with record rules
- Renewal reminder emails and payment links
- Automatic plan upgrades and downgrades with proration
