# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockQuant(models.Model):
    """
    Extends stock.quant (used as inventory lines in Odoo 17+)
    to support fast kanban counting UI.

    In Odoo 17+ the physical inventory is managed via stock.quant
    with inventory_quantity and inventory_date fields.
    """
    _inherit = 'stock.quant'

    # Computed field: whether this line has been counted in current session
    inventory_counted = fields.Boolean(
        string='Counted',
        compute='_compute_inventory_counted',
        store=False,
    )

    # Difference between counted and on-hand
    inventory_diff = fields.Float(
        string='Difference',
        compute='_compute_inventory_diff',
        digits='Product Unit of Measure',
        store=False,
    )

    # Difference state for kanban stripe color
    inventory_diff_state = fields.Selection(
        selection=[
            ('match', 'Match'),
            ('over', 'Over'),
            ('short', 'Short'),
            ('pending', 'Pending'),
        ],
        compute='_compute_inventory_diff',
        store=False,
    )

    @api.depends('inventory_quantity', 'inventory_quantity_set')
    def _compute_inventory_counted(self):
        for rec in self:
            rec.inventory_counted = rec.inventory_quantity_set

    @api.depends('inventory_quantity', 'quantity')
    def _compute_inventory_diff(self):
        for rec in self:
            if not rec.inventory_quantity_set:
                rec.inventory_diff = 0.0
                rec.inventory_diff_state = 'pending'
            else:
                diff = rec.inventory_quantity - rec.quantity
                rec.inventory_diff = diff
                if abs(diff) < 0.001:
                    rec.inventory_diff_state = 'match'
                elif diff > 0:
                    rec.inventory_diff_state = 'over'
                else:
                    rec.inventory_diff_state = 'short'

    def action_set_inventory_quantity(self, qty):
        """Called from OWL component via RPC to set counted quantity."""
        self.ensure_one()
        self.inventory_quantity = qty
        self.inventory_quantity_set = True
        return {
            'diff': self.inventory_diff,
            'diff_state': self.inventory_diff_state,
        }

    def action_clear_inventory_quantity(self):
        """Reset a line back to uncounted."""
        self.ensure_one()
        self.inventory_quantity = 0
        self.inventory_quantity_set = False
