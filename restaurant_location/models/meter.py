# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _

METER_TYPES = [
    ('electricity', 'Electricity'),
    ('gas', 'Gas'),
    ('water_cold', 'Water (Cold)'),
    ('water_hot', 'Water (Hot)'),
    ('heating', 'Heating / District Heat'),
    ('other', 'Other'),
]
DEFAULT_UNITS = {
    'electricity': 'kWh',
    'gas': 'm³',
    'water_cold': 'm³',
    'water_hot': 'm³',
    'heating': 'kWh',
}
# Which contract types can supply which meter.
CONTRACT_TYPES_FOR_METER = {
    'electricity': ['electricity'],
    'gas': ['gas', 'heating'],
    'water_cold': ['water'],
    'water_hot': ['water', 'heating'],
    'heating': ['heating', 'gas'],
    'other': [],
}


class RestaurantLocationMeter(models.Model):
    """A physical meter at a site.

    Readings belong to the meter, never to a supplier: switch from one
    electricity provider to another and the meter, its number and every
    past reading stay exactly where they are. The meter simply points at
    whichever contract currently supplies it.
    """
    _name = 'restaurant.location.meter'
    _description = 'Location Meter'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'location_id, meter_type, name'
    _check_company_auto = True

    name = fields.Char(string='Meter Number', required=True, tracking=True)
    meter_type = fields.Selection(
        METER_TYPES, string='Type', required=True, default='electricity', tracking=True,
    )
    location_id = fields.Many2one(
        'restaurant.location', string='Location', required=True,
        ondelete='cascade', index=True, check_company=True,
    )
    company_id = fields.Many2one(
        'res.company', related='location_id.company_id', store=True, readonly=True,
    )
    contract_id = fields.Many2one(
        'restaurant.location.contract', string='Supplied By',
        domain="[('location_id', '=', location_id), ('contract_type', 'in', allowed_contract_types)]",
        help="The supply contract currently feeding this meter.",
    )
    allowed_contract_types = fields.Char(compute='_compute_allowed_contract_types')
    # (kept non-stored: only used to filter the contract picker)
    provider_id = fields.Many2one(
        'res.partner', related='contract_id.provider_id', string='Provider', readonly=True,
    )
    active = fields.Boolean(default=True)
    unit = fields.Char(
        string='Unit', compute='_compute_unit', store=True, precompute=True,
        readonly=False, required=True,
    )
    conversion_factor = fields.Float(
        string='Conversion Factor', digits=(12, 4), default=1.0, aggregator=None,
        help="Multiplier applied to the raw reading to get billed units, "
             "e.g. gas m³ → kWh (Brennwert × Zustandszahl). Leave 1 if the "
             "meter already counts in the billed unit.",
    )
    physical_location = fields.Char(
        string='Where Is It', help="e.g. basement, next to the fuse box.",
    )
    market_location_id = fields.Char(
        string='MaLo-ID', help="Marktlokations-ID (11 digits) from the supplier's paperwork.",
    )
    metering_point_id = fields.Char(
        string='Metering Point (Zählpunkt / MeLo)',
        help="Zählpunktbezeichnung or Messlokations-ID.",
    )
    grid_operator_id = fields.Many2one(
        'res.partner', string='Grid Operator (Netzbetreiber)',
    )
    installed_on = fields.Date(string='Installed On')
    calibration_due = fields.Date(
        string='Calibration Due (Eichfrist)',
        help="Legal recalibration date; the grid operator usually swaps the meter.",
    )
    reading_interval_days = fields.Integer(
        string='Read Every (Days)', default=30, aggregator=None,
        help="How often a reading should be taken. Leave 0 to disable the reminder.",
    )
    reading_ids = fields.One2many(
        'restaurant.location.meter.reading', 'meter_id', string='Readings',
    )
    reading_count = fields.Integer(compute='_compute_reading_count')
    last_reading_value = fields.Float(
        string='Last Reading', digits=(14, 3), compute='_compute_last_reading', store=True,
        aggregator=None,
    )
    last_reading_date = fields.Date(compute='_compute_last_reading', store=True)
    days_since_reading = fields.Integer(compute='_compute_days_since_reading', aggregator=None)
    reading_overdue = fields.Boolean(compute='_compute_days_since_reading', search='_search_reading_overdue')
    notes = fields.Text()

    _name_location_uniq = models.Constraint(
        'UNIQUE(name, location_id)',
        'This meter number already exists at this location.',
    )

    @api.depends('meter_type')
    def _compute_unit(self):
        for rec in self:
            if not rec.unit or rec.meter_type in DEFAULT_UNITS:
                rec.unit = DEFAULT_UNITS.get(rec.meter_type, rec.unit or 'units')

    @api.depends('meter_type')
    def _compute_allowed_contract_types(self):
        for rec in self:
            types = CONTRACT_TYPES_FOR_METER.get(rec.meter_type, [])
            rec.allowed_contract_types = ','.join(types) if types else 'none'

    @api.depends('reading_ids')
    def _compute_reading_count(self):
        for rec in self:
            rec.reading_count = len(rec.reading_ids)

    @api.depends('reading_ids.value', 'reading_ids.date')
    def _compute_last_reading(self):
        for rec in self:
            readings = rec.reading_ids.sorted(lambda r: (r.date, r.id), reverse=True)
            last = readings[:1]
            rec.last_reading_value = last.value if last else 0.0
            rec.last_reading_date = last.date if last else False

    @api.depends('last_reading_date', 'reading_interval_days')
    def _compute_days_since_reading(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.last_reading_date:
                rec.days_since_reading = (today - rec.last_reading_date).days
            else:
                rec.days_since_reading = 0
            rec.reading_overdue = bool(
                rec.reading_interval_days
                and (not rec.last_reading_date or rec.days_since_reading > rec.reading_interval_days)
            )

    def _search_reading_overdue(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return NotImplemented
        want_overdue = (operator == '=') == value
        overdue = self.search([('reading_interval_days', '>', 0)]).filtered('reading_overdue')
        return [('id', 'in' if want_overdue else 'not in', overdue.ids)]

    @api.depends('name', 'meter_type', 'location_id.code')
    def _compute_display_name(self):
        types = dict(self._fields['meter_type']._description_selection(self.env))
        for rec in self:
            label = types.get(rec.meter_type, '')
            rec.display_name = f"{label} {rec.name}".strip()

    # ── Consumption helpers ──

    def _consumption_between(self, date_from, date_to):
        """Billed units consumed between two dates, interpolated linearly
        from the readings that bracket each date. Returns None when the
        readings do not cover the period."""
        self.ensure_one()
        readings = self.reading_ids.sorted(lambda r: (r.date, r.id))
        if len(readings) < 2:
            return None

        def value_at(day):
            before = [r for r in readings if r.date <= day]
            after = [r for r in readings if r.date >= day]
            if not before or not after:
                return None
            lo, hi = before[-1], after[0]
            if lo.date == hi.date:
                return hi.value
            span = (hi.date - lo.date).days
            frac = (day - lo.date).days / span
            return lo.value + (hi.value - lo.value) * frac

        start, end = value_at(date_from), value_at(date_to)
        if start is None or end is None:
            return None
        return (end - start) * (self.conversion_factor or 1.0)

    def action_view_readings(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'restaurant_location.action_location_meter_reading')
        action['domain'] = [('meter_id', '=', self.id)]
        action['context'] = {'default_meter_id': self.id, 'search_default_meter_id': self.id}
        return action

    def action_add_reading(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Reading'),
            'res_model': 'restaurant.location.meter.reading',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meter_id': self.id},
        }

    # ── Cron ──

    @api.model
    def _cron_reading_reminders(self):
        """Ask the location manager for a reading once a meter is overdue.
        One open activity per meter at a time."""
        meters = self.search([('reading_interval_days', '>', 0)]).filtered('reading_overdue')
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo:
            return
        for meter in meters:
            if meter.activity_ids.filtered(lambda a: a.activity_type_id == todo):
                continue
            managers = meter.location_id.manager_user_ids
            user = managers[:1] or self.env.user
            meter.activity_schedule(
                act_type_xmlid='mail.mail_activity_data_todo',
                date_deadline=fields.Date.context_today(self),
                summary=_("Read meter %(meter)s at %(loc)s",
                          meter=meter.display_name, loc=meter.location_id.display_name),
                note=_("Last reading: %(value)s %(unit)s on %(date)s.",
                       value=meter.last_reading_value, unit=meter.unit,
                       date=meter.last_reading_date or _("never")),
                user_id=user.id,
            )
