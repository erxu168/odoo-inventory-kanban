# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

WEEKDAYS = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]

SCHEDULES = [
    ('weekly', 'Every Week'),
    ('biweekly_odd', 'Every 2 Weeks — Odd Calendar Weeks'),
    ('biweekly_even', 'Every 2 Weeks — Even Calendar Weeks'),
    ('every_4_weeks', 'Every 4 Weeks'),
    ('monthly', 'Monthly — Nth Weekday'),
    ('on_call', 'On Call / As Needed'),
]

NTH = [
    ('1', 'First'),
    ('2', 'Second'),
    ('3', 'Third'),
    ('4', 'Fourth'),
    ('-1', 'Last'),
]

FREQUENCY_TO_YEARLY_PICKUPS = {
    'weekly': 52,
    'biweekly_odd': 26,
    'biweekly_even': 26,
    'every_4_weeks': 13,
    'monthly': 12,
    'on_call': 0,
}


class RestaurantLocationWasteStream(models.Model):
    """One container service at a site: what leaves, in what, who collects
    it, and on which days.

    The pickup rhythm is kept as a rule (weekday + week parity) rather than
    a free-text field so the module can lay the collections out on a
    calendar and check them off. Haulers in Berlin quote exactly that:
    "Donnerstag, gerade KW".
    """
    _name = 'restaurant.location.waste.stream'
    _description = 'Waste Stream'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'location_id, waste_type_id, id'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    location_id = fields.Many2one(
        'restaurant.location', string='Location', required=True,
        ondelete='cascade', index=True, check_company=True,
    )
    company_id = fields.Many2one(
        'res.company', related='location_id.company_id', store=True, readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True,
    )
    waste_type_id = fields.Many2one(
        'restaurant.location.waste.type', string='Waste Stream', required=True,
        ondelete='restrict',
    )
    color = fields.Integer(related='waste_type_id.color')
    active = fields.Boolean(default=True)
    hauler_id = fields.Many2one(
        'res.partner', string='Hauler (Entsorger)', tracking=True,
        help="The company that collects this container. Different streams "
             "often go to different haulers.",
    )
    contract_id = fields.Many2one(
        'restaurant.location.contract', string='Contract',
        domain="[('location_id', '=', location_id), ('contract_type', 'in', ('waste', 'service'))]",
        help="The disposal contract this service runs under, if it is written down.",
    )
    customer_no = fields.Char(string='Customer / Object No.')

    # ── Container ──
    container_size_l = fields.Integer(string='Container Size (L)', help="e.g. 240, 660, 1100", aggregator=None)
    container_count = fields.Integer(string='Containers', default=1)
    container_location = fields.Char(
        string='Where the Bins Stand', help="e.g. courtyard, left of the back door.",
    )
    key_required = fields.Boolean(
        string='Access Key Needed',
        help="The hauler needs a key or code to reach the bins.",
    )

    # ── Schedule ──
    schedule = fields.Selection(SCHEDULES, string='Rhythm', required=True, default='weekly')
    weekday = fields.Selection(WEEKDAYS, string='Weekday', default='0')
    weekday_2 = fields.Selection(
        WEEKDAYS, string='Second Weekday',
        help="For twice-weekly collections on the weekly rhythm.",
    )
    nth_weekday = fields.Selection(NTH, string='Which One', default='1')
    schedule_note = fields.Char(
        string='Schedule Note',
        help="e.g. bins out by 6:00; holiday shifts one day later.",
    )
    schedule_summary = fields.Char(compute='_compute_schedule_summary')
    next_pickup_date = fields.Date(compute='_compute_next_pickup', store=True)
    pickup_ids = fields.One2many(
        'restaurant.location.waste.pickup', 'stream_id', string='Pickups',
    )
    pickup_count = fields.Integer(compute='_compute_pickup_count')
    generate_horizon_weeks = fields.Integer(
        string='Plan Ahead (Weeks)', default=8, aggregator=None,
        help="How far ahead pickups are laid out on the calendar.",
    )

    # ── Money ──
    cost_per_pickup = fields.Monetary(
        string='Cost per Pickup', currency_field='currency_id',
        help="Per container per collection, if billed that way.",
    )
    monthly_fee = fields.Monetary(
        string='Flat Fee / Month', currency_field='currency_id',
        help="Fixed monthly rental/collection fee, if billed that way.",
    )
    annual_cost = fields.Monetary(
        string='Annual Cost', currency_field='currency_id',
        compute='_compute_annual_cost', store=True,
    )
    notes = fields.Text()

    # ── Constraints ──

    @api.constrains('weekday', 'schedule')
    def _check_weekday(self):
        for rec in self:
            if rec.schedule != 'on_call' and not rec.weekday:
                raise ValidationError(_("Pick the weekday the hauler comes."))

    @api.constrains('container_count')
    def _check_container_count(self):
        for rec in self:
            if rec.container_count < 0:
                raise ValidationError(_("The container count cannot be negative."))

    # ── Computes ──

    @api.depends('waste_type_id.name', 'location_id.code', 'location_id.name', 'container_size_l')
    def _compute_name(self):
        for rec in self:
            bits = [rec.waste_type_id.name or _('Waste')]
            if rec.container_size_l:
                bits.append(f"{rec.container_size_l} L")
            rec.name = ' '.join(bits)

    @api.depends('schedule', 'weekday', 'weekday_2', 'nth_weekday')
    def _compute_schedule_summary(self):
        days = dict(WEEKDAYS)
        nth = dict(NTH)
        for rec in self:
            day = days.get(rec.weekday, '')
            if rec.schedule == 'weekly':
                text = day
                if rec.weekday_2:
                    text = f"{day} & {days.get(rec.weekday_2, '')}"
                rec.schedule_summary = _("Every %s", text)
            elif rec.schedule == 'biweekly_odd':
                rec.schedule_summary = _("%s, odd weeks", day)
            elif rec.schedule == 'biweekly_even':
                rec.schedule_summary = _("%s, even weeks", day)
            elif rec.schedule == 'every_4_weeks':
                rec.schedule_summary = _("Every 4 weeks on %s", day)
            elif rec.schedule == 'monthly':
                rec.schedule_summary = _("%(nth)s %(day)s of the month",
                                         nth=nth.get(rec.nth_weekday, ''), day=day)
            else:
                rec.schedule_summary = _("On call")

    @api.depends('pickup_ids.date', 'pickup_ids.state')
    def _compute_next_pickup(self):
        today = fields.Date.context_today(self)
        for rec in self:
            upcoming = rec.pickup_ids.filtered(
                lambda p: p.date >= today and p.state == 'planned').sorted('date')
            rec.next_pickup_date = upcoming[:1].date if upcoming else False

    @api.depends('pickup_ids')
    def _compute_pickup_count(self):
        for rec in self:
            rec.pickup_count = len(rec.pickup_ids)

    @api.depends('cost_per_pickup', 'monthly_fee', 'schedule', 'container_count')
    def _compute_annual_cost(self):
        for rec in self:
            pickups = FREQUENCY_TO_YEARLY_PICKUPS.get(rec.schedule, 0)
            per_pickup = (rec.cost_per_pickup or 0.0) * max(rec.container_count or 1, 1) * pickups
            rec.annual_cost = per_pickup + (rec.monthly_fee or 0.0) * 12

    # ── Schedule engine ──

    def _pickup_dates(self, date_from, date_to):
        """Every collection date this rule produces in [date_from, date_to]."""
        self.ensure_one()
        if self.schedule == 'on_call' or not self.weekday:
            return []
        weekdays = {int(self.weekday)}
        if self.schedule == 'weekly' and self.weekday_2:
            weekdays.add(int(self.weekday_2))

        dates = []
        day = date_from
        while day <= date_to:
            if day.weekday() in weekdays and self._rule_matches(day):
                dates.append(day)
            day += timedelta(days=1)
        return dates

    def _rule_matches(self, day):
        self.ensure_one()
        iso_week = day.isocalendar()[1]
        if self.schedule == 'weekly':
            return True
        if self.schedule == 'biweekly_odd':
            return iso_week % 2 == 1
        if self.schedule == 'biweekly_even':
            return iso_week % 2 == 0
        if self.schedule == 'every_4_weeks':
            # Anchor on the first planned pickup ever recorded, else on the
            # first matching week of the current ISO year.
            anchor = self.pickup_ids.sorted('date')[:1].date
            if not anchor:
                return iso_week % 4 == 1
            weeks_between = (day - anchor).days // 7
            return weeks_between % 4 == 0 and (day - anchor).days % 7 == 0
        if self.schedule == 'monthly':
            return self._is_nth_weekday(day)
        return False

    def _is_nth_weekday(self, day):
        n = int(self.nth_weekday or '1')
        if n > 0:
            return (day.day - 1) // 7 + 1 == n
        # Last such weekday of the month.
        next_week = day + timedelta(days=7)
        return next_week.month != day.month

    def action_generate_pickups(self):
        """Lay out the planned pickups for the horizon. Idempotent: dates
        that already have a pickup (in any state) are left alone."""
        Pickup = self.env['restaurant.location.waste.pickup']
        today = fields.Date.context_today(self)
        created = Pickup
        for stream in self.filtered('active'):
            horizon = today + relativedelta(weeks=stream.generate_horizon_weeks or 8)
            existing = set(stream.pickup_ids.mapped('date'))
            for day in stream._pickup_dates(today, horizon):
                if day in existing:
                    continue
                created |= Pickup.create({'stream_id': stream.id, 'date': day})
        return created

    def action_view_pickups(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'restaurant_location.action_location_waste_pickup')
        action['domain'] = [('stream_id', '=', self.id)]
        action['context'] = {
            'default_stream_id': self.id,
            'default_location_id': self.location_id.id,
        }
        return action

    @api.model
    def _cron_generate_pickups(self):
        streams = self.search([('active', '=', True), ('schedule', '!=', 'on_call')])
        streams.action_generate_pickups()
        self.env['restaurant.location.waste.pickup']._mark_missed()

    def write(self, vals):
        res = super().write(vals)
        schedule_fields = {'schedule', 'weekday', 'weekday_2', 'nth_weekday', 'active'}
        if schedule_fields & set(vals):
            # The rule changed: drop untouched future plans and lay them out again.
            today = fields.Date.context_today(self)
            self.env['restaurant.location.waste.pickup'].search([
                ('stream_id', 'in', self.ids),
                ('date', '>=', today),
                ('state', '=', 'planned'),
            ]).unlink()
            self.action_generate_pickups()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        streams = super().create(vals_list)
        streams.action_generate_pickups()
        return streams
