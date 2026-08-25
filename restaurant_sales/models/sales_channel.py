# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SalesChannel(models.Model):
    """A revenue stream that never touches the POS terminal — delivery
    platforms, catering invoices, event bookings."""
    _name = 'restaurant.sales.channel'
    _description = 'Off-POS Sales Channel'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Short label used in reporting exports.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
        help="Leave empty to make the channel available to every company.",
    )
    commission_percent = fields.Float(
        string='Commission %', digits=(5, 2),
        help="Default commission the platform keeps. Can be overridden on "
             "each daily line.",
    )
    note = fields.Text()

    @api.constrains('commission_percent')
    def _check_commission_percent(self):
        for channel in self:
            if not 0.0 <= channel.commission_percent <= 100.0:
                raise ValidationError(
                    _("The commission of %s must be between 0 and 100%%.",
                      channel.display_name)
                )
