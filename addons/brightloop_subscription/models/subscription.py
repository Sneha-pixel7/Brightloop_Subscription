from dateutil.relativedelta import relativedelta
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BrightloopSubscription(models.Model):
    _name = 'brightloop.subscription'
    _description = 'Subscription'
    _inherit = ['mail.thread']
    _order = 'start_date desc'

    name = fields.Char(compute='_compute_name', store=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    plan_id = fields.Many2one('brightloop.plan', string='Plan', required=True, tracking=True)
    price = fields.Float(related='plan_id.price', string='Price')
    start_date = fields.Date(required=True, default=fields.Date.context_today)
    end_date = fields.Date()
    next_renewal_date = fields.Date(compute='_compute_next_renewal', store=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('active', 'Active'), ('paused', 'Paused'),
        ('cancelled', 'Cancelled'), ('expired', 'Expired'),
    ], default='draft', tracking=True)

    @api.depends('partner_id', 'plan_id')
    def _compute_name(self):
        for rec in self:
            rec.name = "%s - %s" % (rec.partner_id.name or '', rec.plan_id.name or '')

    @api.depends('start_date', 'plan_id.billing_period')
    def _compute_next_renewal(self):
        months = {'monthly': 1, 'quarterly': 3, 'yearly': 12}
        for rec in self:
            if rec.start_date and rec.plan_id:
                rec.next_renewal_date = rec.start_date + relativedelta(
                    months=months[rec.plan_id.billing_period])
            else:
                rec.next_renewal_date = False

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError("End date cannot be before the start date.")

    @api.constrains('partner_id', 'plan_id', 'state')
    def _check_duplicate_active(self):
        for rec in self:
            if rec.state == 'active' and self.search_count([
                ('id', '!=', rec.id), ('state', '=', 'active'),
                ('partner_id', '=', rec.partner_id.id),
                ('plan_id', '=', rec.plan_id.id),
            ]):
                raise ValidationError("This customer already has an active subscription to this plan.")

    def action_activate(self):
        self.write({'state': 'active'})

    def action_pause(self):
        self.write({'state': 'paused'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
