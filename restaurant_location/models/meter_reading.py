# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

READING_SOURCES = [
    ('manual', 'Read on Site'),
    ('invoice', 'From Invoice / Statement'),
    ('provider', 'Provider Estimate'),
    ('smart', 'Smart Meter'),
]


class RestaurantLocationMeterReading(models.Model):
    _name = 'restaurant.location.meter.reading'
    _description = 'Meter Reading'
    _order = 'date desc, id desc'
    _check_company_auto = True

    meter_id = fields.Many2one(
        'restaurant.location.meter', string='Meter', required=True,
        ondelete='cascade', index=True, check_company=True,
    )
    location_id = fields.Many2one(
        related='meter_id.location_id', store=True, readonly=True, index=True,
    )
    company_id = fields.Many2one(
        related='meter_id.company_id', store=True, readonly=True,
    )
    meter_type = fields.Selection(related='meter_id.meter_type', store=True, readonly=True)
    unit = fields.Char(related='meter_id.unit', readonly=True)
    date = fields.Date(
        string='Date', required=True, default=fields.Date.context_today, index=True,
    )
    value = fields.Float(string='Reading', digits=(14, 3), required=True, aggregator=None)
    source = fields.Selection(READING_SOURCES, default='manual', required=True)
    user_id = fields.Many2one(
        'res.users', string='Read By', default=lambda self: self.env.user,
    )
    photo = fields.Image(string='Photo', max_width=1920, max_height=1920)
    notes = fields.Char(string='Note')

    # Derived from the previous reading of the same meter.
    previous_reading_id = fields.Many2one(
        'restaurant.location.meter.reading', compute='_compute_consumption', store=True,
    )
    consumption = fields.Float(
        string='Consumption', digits=(14, 3), compute='_compute_consumption', store=True,
        help="Units used since the previous reading (raw meter units).",
    )
    days_elapsed = fields.Integer(compute='_compute_consumption', store=True, aggregator=None)
    daily_average = fields.Float(
        string='Per Day', digits=(14, 3), compute='_compute_consumption', store=True,
        aggregator='avg',
    )
    billed_units = fields.Float(
        string='Billed Units', digits=(14, 3), compute='_compute_consumption', store=True,
        help="Consumption × the meter's conversion factor.",
    )
    estimated_cost = fields.Monetary(
        string='Est. Cost', currency_field='currency_id',
        compute='_compute_estimated_cost', store=True,
        help="Billed units × the unit price of the contract supplying the "
             "meter on the reading date. Indicative only.",
    )
    currency_id = fields.Many2one(related='meter_id.company_id.currency_id', readonly=True)
    contract_id = fields.Many2one(
        'restaurant.location.contract', string='Contract at the Time',
        compute='_compute_estimated_cost', store=True,
    )

    @api.constrains('value', 'date', 'meter_id')
    def _check_monotonic(self):
        """A meter counts up. Allow equal (no consumption) but not a drop,
        which is almost always a typo or a swapped meter."""
        for rec in self:
            prev = rec._find_previous()
            if prev and rec.value < prev.value:
                raise ValidationError(_(
                    "Reading %(new)s on %(date)s is lower than the previous reading "
                    "%(old)s on %(old_date)s. If the meter was replaced, create a new "
                    "meter record instead.",
                    new=rec.value, date=rec.date, old=prev.value, old_date=prev.date,
                ))

    def _find_previous(self):
        self.ensure_one()
        return self.search([
            ('meter_id', '=', self.meter_id.id),
            ('id', '!=', self.id),
            '|', ('date', '<', self.date),
            '&', ('date', '=', self.date), ('id', '<', self.id),
        ], order='date desc, id desc', limit=1)

    @api.depends('meter_id', 'date', 'value', 'meter_id.conversion_factor',
                 'meter_id.reading_ids.date', 'meter_id.reading_ids.value')
    def _compute_consumption(self):
        for rec in self:
            prev = rec._find_previous() if rec.meter_id and rec.date else self.browse()
            rec.previous_reading_id = prev
            if prev:
                rec.consumption = rec.value - prev.value
                rec.days_elapsed = (rec.date - prev.date).days
                rec.daily_average = rec.consumption / rec.days_elapsed if rec.days_elapsed else 0.0
            else:
                rec.consumption = 0.0
                rec.days_elapsed = 0
                rec.daily_average = 0.0
            rec.billed_units = rec.consumption * (rec.meter_id.conversion_factor or 1.0)

    @api.depends('billed_units', 'date', 'meter_id.contract_id',
                 'meter_id.location_id.contract_ids.start_date',
                 'meter_id.location_id.contract_ids.end_date',
                 'meter_id.location_id.contract_ids.unit_price')
    def _compute_estimated_cost(self):
        for rec in self:
            contract = rec._contract_on(rec.date)
            rec.contract_id = contract
            rec.estimated_cost = (
                rec.billed_units * contract.unit_price if contract and contract.unit_price else 0.0
            )

    def _contract_on(self, day):
        """The contract supplying this meter on a given day: the one linked
        to the meter if its term covers the day, otherwise any contract of
        a matching type at the site whose term does."""
        self.ensure_one()
        meter = self.meter_id
        if not meter or not day:
            return self.env['restaurant.location.contract']
        candidates = meter.contract_id
        if candidates and not candidates._covers(day):
            candidates = self.env['restaurant.location.contract']
        if not candidates:
            allowed = (meter.allowed_contract_types or '').split(',')
            candidates = meter.location_id.contract_ids.filtered(
                lambda c: c.contract_type in allowed and c._covers(day)
            ).sorted('start_date', reverse=True)[:1]
        return candidates

    @api.depends('meter_id', 'date', 'value')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.meter_id.display_name} · {rec.date} · {rec.value:g} {rec.unit or ''}".strip()
