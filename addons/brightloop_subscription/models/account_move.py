from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    brightloop_subscription_id = fields.Many2one(
        'brightloop.subscription', string='Subscription', copy=False)
