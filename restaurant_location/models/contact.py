# -*- coding: utf-8 -*-
from odoo import models, fields, api

CONTACT_ROLES = [
    ('landlord', 'Landlord'),
    ('property_manager', 'Property Manager (Hausverwaltung)'),
    ('caretaker', 'Caretaker (Hausmeister)'),
    ('electrician', 'Electrician'),
    ('plumber', 'Plumber'),
    ('hvac', 'HVAC / Refrigeration'),
    ('kitchen_tech', 'Kitchen Equipment Service'),
    ('it', 'IT / POS Support'),
    ('pest_control', 'Pest Control'),
    ('fire_safety', 'Fire Safety'),
    ('locksmith', 'Locksmith'),
    ('cleaning', 'Cleaning'),
    ('authority', 'Authority'),
    ('emergency', 'Emergency'),
    ('other', 'Other'),
]


class RestaurantLocationContact(models.Model):
    """Who to call. A thin row on purpose: the number on the wall, not a
    full CRM record, although one can be linked."""
    _name = 'restaurant.location.contact'
    _description = 'Location Contact'
    _order = 'location_id, sequence, id'
    _check_company_auto = True

    location_id = fields.Many2one(
        'restaurant.location', required=True, ondelete='cascade', index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company', related='location_id.company_id', store=True, readonly=True,
    )
    sequence = fields.Integer(default=10)
    role = fields.Selection(CONTACT_ROLES, required=True, default='other')
    partner_id = fields.Many2one('res.partner', string='Contact')
    name = fields.Char(compute='_compute_from_partner', store=True, readonly=False, required=True)
    phone = fields.Char(compute='_compute_from_partner', store=True, readonly=False)
    email = fields.Char(compute='_compute_from_partner', store=True, readonly=False)
    available = fields.Char(string='Reachable', help="e.g. Mon–Fri 8–17, 24h emergency line")
    notes = fields.Char(string='Note')

    @api.depends('partner_id')
    def _compute_from_partner(self):
        for rec in self:
            if rec.partner_id:
                rec.name = rec.partner_id.display_name
                rec.phone = rec.partner_id.phone or rec.partner_id.mobile
                rec.email = rec.partner_id.email
