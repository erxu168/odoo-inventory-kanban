# -*- coding: utf-8 -*-
from odoo import models, fields


class RestaurantLocationWasteType(models.Model):
    """A kind of waste that leaves the building in its own container.

    Configurable rather than a fixed selection because the list keeps
    growing: a new site brings a new hauler, and a new hauler brings a new
    container. The seeded types cover a German restaurant's usual set.
    """
    _name = 'restaurant.location.waste.type'
    _description = 'Waste Stream Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Short code, e.g. GEW for Gewerbeabfall.")
    sequence = fields.Integer(default=10)
    color = fields.Integer(string='Colour', default=0)
    active = fields.Boolean(default=True)
    is_recycling = fields.Boolean(
        string='Recycling', default=True,
        help="Sorted fraction (packaging, glass, paper, organic) as opposed "
             "to mixed commercial waste.",
    )
    is_hazardous = fields.Boolean(
        string='Needs Disposal Certificate',
        help="Streams such as used cooking oil or grease-trap sludge come "
             "with a disposal certificate (Entsorgungsnachweis) that has to "
             "be kept for the authorities.",
    )
    default_unit = fields.Selection([
        ('container', 'Container'),
        ('litre', 'Litre'),
        ('kg', 'Kilogram'),
    ], string='Billed Per', default='container')
    description = fields.Text(translate=True)
