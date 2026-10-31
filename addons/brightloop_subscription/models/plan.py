from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BrightloopPlan(models.Model):
    _name = 'brightloop.plan'
    _description = 'Subscription Plan'

    name = fields.Char(required=True)
    price = fields.Float(required=True)
    billing_period = fields.Selection(
        [('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')],
        required=True, default='monthly')
    description = fields.Text()
    active = fields.Boolean(default=True)

    @api.constrains('price')
    def _check_price(self):
        for rec in self:
            if rec.price <= 0:
                raise ValidationError("Price must be greater than 0.")
