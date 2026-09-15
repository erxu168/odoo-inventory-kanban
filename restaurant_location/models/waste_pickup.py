# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _

PICKUP_STATES = [
    ('planned', 'Planned'),
    ('done', 'Collected'),
    ('missed', 'Missed'),
    ('cancelled', 'Cancelled'),
]


class RestaurantLocationWastePickup(models.Model):
    """One collection on one day.

    Generated from the stream's rule, then checked off by whoever puts the
    bins out. Keeping every collection as a row gives two things the rule
    alone cannot: a calendar, and the paper trail the commercial-waste
    ordinance (GewAbfV) asks for when the authority wants proof that the
    fractions are actually collected.
    """
    _name = 'restaurant.location.waste.pickup'
    _description = 'Waste Pickup'
    _order = 'date, stream_id'
    _check_company_auto = True

    stream_id = fields.Many2one(
        'restaurant.location.waste.stream', string='Waste Service', required=True,
        ondelete='cascade', index=True, check_company=True,
    )
    location_id = fields.Many2one(
        related='stream_id.location_id', store=True, readonly=True, index=True,
    )
    company_id = fields.Many2one(
        related='stream_id.company_id', store=True, readonly=True,
    )
    waste_type_id = fields.Many2one(
        related='stream_id.waste_type_id', store=True, readonly=True,
    )
    hauler_id = fields.Many2one(related='stream_id.hauler_id', store=True, readonly=True)
    color = fields.Integer(related='waste_type_id.color')
    name = fields.Char(compute='_compute_name', store=True)
    date = fields.Date(required=True, index=True)
    state = fields.Selection(PICKUP_STATES, default='planned', required=True, index=True)
    container_count = fields.Integer(
        string='Containers Collected',
        help="Filled in when the collection is confirmed.",
    )
    weight_kg = fields.Float(string='Weight (kg)', digits=(10, 2))
    certificate_no = fields.Char(
        string='Certificate / Slip No.',
        help="Wiegeschein or Entsorgungsnachweis number, if one was handed over.",
    )
    confirmed_by_id = fields.Many2one('res.users', string='Confirmed By')
    confirmed_on = fields.Datetime()
    notes = fields.Char(string='Note')

    _stream_date_uniq = models.Constraint(
        'UNIQUE(stream_id, date)',
        'There is already a pickup for this stream on that day.',
    )

    @api.depends('stream_id.name', 'location_id.code', 'location_id.name')
    def _compute_name(self):
        for rec in self:
            loc = rec.location_id.code or rec.location_id.name or ''
            rec.name = f"{loc} · {rec.stream_id.name}" if loc else (rec.stream_id.name or '')

    def action_done(self):
        for rec in self:
            rec.write({
                'state': 'done',
                'confirmed_by_id': self.env.uid,
                'confirmed_on': fields.Datetime.now(),
                'container_count': rec.container_count or rec.stream_id.container_count,
            })

    def action_missed(self):
        self.write({'state': 'missed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset(self):
        self.write({'state': 'planned', 'confirmed_by_id': False, 'confirmed_on': False})

    @api.model
    def _mark_missed(self, grace_days=3):
        """Pickups still 'planned' a few days after their date were not
        confirmed by anyone; flag them so the gap is visible."""
        cutoff = fields.Date.context_today(self) - timedelta(days=grace_days)
        self.search([('state', '=', 'planned'), ('date', '<', cutoff)]).write({'state': 'missed'})
