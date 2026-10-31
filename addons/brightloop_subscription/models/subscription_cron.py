from odoo import models, fields, api


class BrightloopSubscriptionCron(models.Model):
    _inherit = 'brightloop.subscription'

    @api.model
    def _cron_process_subscriptions(self):
        today = fields.Date.context_today(self)

        # 1. Expire active subscriptions that passed their end date
        expired = self.search([
            ('state', '=', 'active'),
            ('end_date', '!=', False),
            ('end_date', '<', today),
        ])
        expired.write({'state': 'expired'})

        # 2. Renew: invoice active subscriptions whose renewal date has arrived.
        # start_date is moved to the renewal date, so it marks the start of the
        # current billing period and the next renewal is recomputed from it.
        due = self.search([
            ('state', '=', 'active'),
            ('next_renewal_date', '<=', today),
        ])
        for sub in due:
            sub.action_create_invoice()
            sub.start_date = sub.next_renewal_date
