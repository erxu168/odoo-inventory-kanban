# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SalesPaymentLine(models.Model):
    """Expected (from POS) versus counted takings for one payment method."""
    _name = 'restaurant.sales.payment.line'
    _description = 'Daily Sales — Payment Line'
    _order = 'is_cash desc, id'

    entry_id = fields.Many2one(
        'restaurant.sales.entry', string='Sales Entry',
        required=True, ondelete='cascade', index=True,
    )
    payment_method_id = fields.Many2one(
        'pos.payment.method', string='Payment Method', required=True,
    )
    is_cash = fields.Boolean(
        related='payment_method_id.is_cash_count', store=True,
    )
    company_id = fields.Many2one(related='entry_id.company_id', store=True)
    currency_id = fields.Many2one(related='entry_id.currency_id')
    date = fields.Date(related='entry_id.date', store=True)

    pos_amount = fields.Monetary(
        string='Expected (POS)', readonly=True,
        help="Total taken through this payment method according to Point of "
             "Sale. Refreshed from the POS orders, never typed in.",
    )
    counted_amount = fields.Monetary(
        string='Counted',
        help="What was actually in the drawer or on the terminal report at "
             "close-out.",
    )
    difference = fields.Monetary(
        compute='_compute_difference', store=True,
        help="Counted less expected. Negative means money is missing.",
    )
    note = fields.Char(string='Comment')

    @api.depends('pos_amount', 'counted_amount')
    def _compute_difference(self):
        for line in self:
            line.difference = line.counted_amount - line.pos_amount

    @api.constrains('entry_id', 'payment_method_id')
    def _check_unique_method(self):
        for line in self:
            duplicate = self.search_count([
                ('entry_id', '=', line.entry_id.id),
                ('payment_method_id', '=', line.payment_method_id.id),
                ('id', '!=', line.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "%(method)s appears twice on this sales entry. Each "
                    "payment method may only be declared once.",
                    method=line.payment_method_id.display_name,
                ))
