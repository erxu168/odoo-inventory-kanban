# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SalesChannelLine(models.Model):
    """One off-POS channel's takings for a single business day."""
    _name = 'restaurant.sales.channel.line'
    _description = 'Daily Sales — Channel Line'
    _order = 'sequence, id'

    entry_id = fields.Many2one(
        'restaurant.sales.entry', string='Sales Entry',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    channel_id = fields.Many2one(
        'restaurant.sales.channel', string='Channel', required=True,
    )
    company_id = fields.Many2one(related='entry_id.company_id', store=True)
    currency_id = fields.Many2one(related='entry_id.currency_id')
    date = fields.Date(related='entry_id.date', store=True)

    gross_amount = fields.Monetary(
        string='Gross', help="Value of the orders as billed to the customer.",
    )
    commission_percent = fields.Float(string='Commission %', digits=(5, 2))
    commission_amount = fields.Monetary(
        string='Commission', compute='_compute_amounts', store=True,
    )
    net_amount = fields.Monetary(
        string='Net Payout', compute='_compute_amounts', store=True,
        help="What the platform actually pays out: gross less commission.",
    )
    order_count = fields.Integer(string='Orders')
    note = fields.Char()

    @api.depends('gross_amount', 'commission_percent')
    def _compute_amounts(self):
        for line in self:
            line.commission_amount = line.gross_amount * line.commission_percent / 100.0
            line.net_amount = line.gross_amount - line.commission_amount

    @api.onchange('channel_id')
    def _onchange_channel_id(self):
        for line in self:
            if line.channel_id:
                line.commission_percent = line.channel_id.commission_percent

    @api.constrains('commission_percent')
    def _check_commission_percent(self):
        for line in self:
            if not 0.0 <= line.commission_percent <= 100.0:
                raise ValidationError(
                    _("The commission percentage must be between 0 and 100.")
                )
