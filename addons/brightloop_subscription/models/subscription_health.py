from datetime import timedelta
from odoo import models, fields, api


class BrightloopSubscriptionHealth(models.Model):
    _inherit = 'brightloop.subscription'

    price = fields.Float(related='plan_id.price', string='Price', store=True)
    health = fields.Selection([
        ('healthy', 'Healthy'), ('at_risk', 'At Risk'), ('critical', 'Critical'),
    ], compute='_compute_health', store=True)

    @api.depends('state', 'next_renewal_date', 'invoice_ids.state',
                 'invoice_ids.payment_state', 'invoice_ids.invoice_date_due')
    def _compute_health(self):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=7)
        for rec in self:
            if rec.state not in ('active', 'paused'):
                rec.health = False
                continue
            overdue = rec.invoice_ids.filtered(
                lambda m: m.state != 'cancel'
                and m.payment_state in ('not_paid', 'partial')
                and m.invoice_date_due and m.invoice_date_due < today)
            if overdue:
                rec.health = 'critical'
            elif rec.state == 'paused' or (rec.next_renewal_date and rec.next_renewal_date <= soon):
                rec.health = 'at_risk'
            else:
                rec.health = 'healthy'

    @api.model
    def _cron_process_subscriptions(self):
        super()._cron_process_subscriptions()
        self.search([])._compute_health()
