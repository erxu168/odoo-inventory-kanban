# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

CONTRACT_TYPES = [
    ('lease', 'Lease (Mietvertrag)'),
    ('electricity', 'Electricity (Strom)'),
    ('gas', 'Gas'),
    ('water', 'Water / Sewage (Wasser)'),
    ('heating', 'District Heating (Fernwärme)'),
    ('telecom', 'Telecom / Internet'),
    ('waste', 'Waste & Recycling (Entsorgung)'),
    ('insurance', 'Insurance (Versicherung)'),
    ('service', 'Service / Maintenance (Wartung)'),
    ('other', 'Other'),
]
UTILITY_TYPES = ('electricity', 'gas', 'water', 'heating')

STATUS_TYPES = [
    ('draft', 'Draft'),
    ('active', 'Active'),
    ('expiring', 'Cancellation Window'),
    ('expired', 'Expired'),
    ('cancelled', 'Cancelled'),
]

FREQUENCIES = [
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly'),
    ('semi_annually', 'Semi-Annually'),
    ('annually', 'Annually'),
    ('one_time', 'One-Time'),
]
FREQUENCY_PER_YEAR = {
    'monthly': 12, 'quarterly': 4, 'semi_annually': 2, 'annually': 1, 'one_time': 0,
}

NOTICE_UNITS = [
    ('days', 'Days'),
    ('weeks', 'Weeks'),
    ('months', 'Months'),
]

PAYMENT_METHODS = [
    ('sepa', 'SEPA Direct Debit'),
    ('transfer', 'Bank Transfer'),
    ('card', 'Card'),
    ('included', 'Included in Rent'),
]

INSURANCE_KINDS = [
    ('liability', 'Public Liability (Betriebshaftpflicht)'),
    ('contents', 'Contents / Inventory (Inhaltsversicherung)'),
    ('interruption', 'Business Interruption (Betriebsunterbrechung)'),
    ('glass', 'Glass (Glasversicherung)'),
    ('building', 'Building (Gebäudeversicherung)'),
    ('legal', 'Legal Expenses (Rechtsschutz)'),
    ('electronics', 'Electronics (Elektronikversicherung)'),
    ('cyber', 'Cyber'),
    ('vehicle', 'Vehicle (Kfz)'),
    ('other', 'Other'),
]

UNIT_LABEL_BY_TYPE = {
    'electricity': 'kWh',
    'gas': 'kWh',
    'heating': 'kWh',
    'water': 'm³',
}


class RestaurantLocationContract(models.Model):
    """Every recurring agreement bound to a site, in one model.

    One model rather than one per type because the questions asked of a
    contract are the same whatever it covers: who is the counterparty, what
    does it cost per year, and by which date must notice be given so it
    does not silently renew. Type-specific details live in groups that the
    form shows only for the matching type.
    """
    _name = 'restaurant.location.contract'
    _description = 'Location Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'termination_deadline asc, end_date asc, id desc'
    _check_company_auto = True

    # ── Core ──
    name = fields.Char(string='Contract', required=True, tracking=True)
    contract_type = fields.Selection(
        CONTRACT_TYPES, string='Type', required=True, tracking=True, default='electricity',
    )
    is_utility = fields.Boolean(compute='_compute_is_utility')
    location_id = fields.Many2one(
        'restaurant.location', string='Location', required=True, tracking=True,
        ondelete='cascade', index=True, check_company=True,
    )
    company_id = fields.Many2one(
        'res.company', related='location_id.company_id', store=True, readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True,
    )
    provider_id = fields.Many2one(
        'res.partner', string='Provider / Counterparty', tracking=True,
        help="Supplier, hauler, insurer or landlord — the other party.",
    )
    contract_no = fields.Char(
        string='Contract No. (Vertragsnummer)', tracking=True,
        help="The reference printed on the contract itself.",
    )
    customer_no = fields.Char(
        string='Customer No. (Kundennummer)',
        help="Your account number with the provider. Suppliers ask for "
             "this one on the phone; it is not the contract number.",
    )
    tariff_name = fields.Char(string='Tariff / Product', help="e.g. Komfort 24, Gewerbestrom Basis")
    status = fields.Selection(
        STATUS_TYPES, string='Status',
        compute='_compute_status', store=True, precompute=True,
        tracking=True, readonly=False,
    )
    cancelled_on = fields.Date(string='Cancelled On', tracking=True)
    replaced_by_id = fields.Many2one(
        'restaurant.location.contract', string='Replaced By',
        help="The contract that took over from this one (e.g. after a supplier switch).",
    )
    user_id = fields.Many2one(
        'res.users', string='Responsible', default=lambda self: self.env.user, tracking=True,
        help="Receives the cancellation-deadline reminders.",
    )
    notes = fields.Html(string='Notes')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'restaurant_location_contract_attachment_rel',
        'contract_id', 'attachment_id', string='Documents',
        help="The signed contract, price sheets, annual statements.",
    )

    # ── Term & notice ──
    start_date = fields.Date(string='Start', required=True, tracking=True,
                             default=fields.Date.context_today)
    end_date = fields.Date(
        string='End of Term', tracking=True,
        help="End of the minimum term (Mindestlaufzeit). Leave empty for an "
             "open-ended contract; no cancellation deadline is then computed.",
    )
    notice_value = fields.Integer(string='Notice Period', default=3, aggregator=None)
    notice_unit = fields.Selection(NOTICE_UNITS, default='months')
    termination_deadline = fields.Date(
        string='Cancel By', compute='_compute_termination_deadline', store=True,
        precompute=True,
        help="Last day on which notice must reach the provider (Kündigungsfrist).",
    )
    days_to_deadline = fields.Integer(compute='_compute_days_to_deadline', aggregator=None)
    auto_renewal = fields.Boolean(string='Auto-Renews', default=True, tracking=True)
    renewal_months = fields.Integer(
        string='Renews By (Months)', default=12, aggregator=None,
        help="How long the contract extends when the cancellation deadline is missed.",
    )
    price_fixed_until = fields.Date(
        string='Price Fixed Until',
        help="End of the price guarantee (Preisgarantie).",
    )

    # ── Money ──
    amount = fields.Monetary(
        string='Recurring Fee', currency_field='currency_id', tracking=True,
        help="Premium, fee or rent charged per period.",
    )
    frequency = fields.Selection(FREQUENCIES, string='Billed', default='monthly')
    annual_cost = fields.Monetary(
        string='Annual Cost', currency_field='currency_id',
        compute='_compute_annual_cost', store=True,
        help="Recurring cost per year. For supply contracts this is the "
             "instalment (Abschlag) × 12, or the base fee × 12 when no "
             "instalment is set.",
    )
    payment_method = fields.Selection(PAYMENT_METHODS, string='Paid By', default='sepa')
    payment_day = fields.Integer(string='Payment Day of Month', aggregator=None)
    cost_center_note = fields.Char(string='Cost Reference', help="Booking reference or cost centre.")

    # ── Portal access ──
    portal_url = fields.Char(string='Portal URL')
    portal_login = fields.Char(
        string='Portal Login', groups='restaurant_location.group_location_manager',
    )
    portal_password = fields.Char(
        string='Portal Password', groups='restaurant_location.group_location_manager',
    )
    verification_code = fields.Char(
        string='Phone PIN / Kundenkennwort',
        groups='restaurant_location.group_location_manager',
        help="The password or PIN the hotline asks for.",
    )

    # ── Lease ──
    rent_net = fields.Monetary(string='Net Rent (Kaltmiete)', currency_field='currency_id')
    rent_charges = fields.Monetary(
        string='Service Charges (Nebenkosten)', currency_field='currency_id',
    )
    rent_vat = fields.Monetary(string='VAT on Rent', currency_field='currency_id')
    rent_total = fields.Monetary(
        string='Total Rent / Month', currency_field='currency_id',
        compute='_compute_rent_total', store=True,
    )
    deposit = fields.Monetary(string='Deposit (Kaution)', currency_field='currency_id')
    deposit_paid_on = fields.Date(string='Deposit Paid On')
    rent_indexed = fields.Boolean(
        string='Index-Linked (Indexmiete)',
        help="Rent follows the consumer price index.",
    )
    rent_step_note = fields.Char(
        string='Rent Steps (Staffel)',
        help="e.g. +2 % every 1 Jan; details in the notes.",
    )
    leased_area_sqm = fields.Float(string='Leased Area (m²)', digits=(10, 2))
    landlord_id = fields.Many2one(
        'res.partner', string='Landlord', related='provider_id', readonly=True,
    )

    # ── Supply (electricity / gas / water / heating) ──
    base_fee = fields.Monetary(
        string='Base Fee / Month (Grundpreis)', currency_field='currency_id',
    )
    unit_price = fields.Float(
        string='Unit Price (Arbeitspreis)', digits=(12, 4), aggregator=None,
        help="Price per unit, e.g. 0.2890 €/kWh. Four decimals matter here.",
    )
    unit_label = fields.Char(
        string='Unit', compute='_compute_unit_label', store=True, precompute=True,
        readonly=False,
    )
    monthly_installment = fields.Monetary(
        string='Instalment / Month (Abschlag)', currency_field='currency_id',
    )
    expected_annual_usage = fields.Float(
        string='Expected Annual Usage', digits=(12, 2),
        help="The consumption the instalment was calculated on.",
    )
    meter_ids = fields.One2many(
        'restaurant.location.meter', 'contract_id', string='Meters Supplied',
    )
    meter_count = fields.Integer(compute='_compute_meter_count')

    # ── Insurance ──
    insurance_kind = fields.Selection(INSURANCE_KINDS, string='Insurance Kind')
    policy_no = fields.Char(string='Policy No. (Versicherungsscheinnummer)')
    coverage_sum = fields.Monetary(
        string='Sum Insured (Versicherungssumme)', currency_field='currency_id',
    )
    deductible = fields.Monetary(
        string='Deductible (Selbstbeteiligung)', currency_field='currency_id',
    )
    main_due_date = fields.Date(
        string='Main Due Date (Hauptfälligkeit)',
        help="Anniversary on which the premium falls due; the German notice "
             "period usually counts back from this date.",
    )
    broker_id = fields.Many2one('res.partner', string='Broker / Agent')
    claims_phone = fields.Char(string='Claims Hotline')

    # ── Telecom ──
    phone_numbers = fields.Text(string='Phone Numbers')
    bandwidth = fields.Char(string='Bandwidth / Plan')

    # ── Service / maintenance ──
    service_interval_months = fields.Integer(string='Service Interval (Months)', aggregator=None)
    last_service_date = fields.Date(string='Last Service')
    next_service_date = fields.Date(
        string='Next Service', compute='_compute_next_service_date', store=True,
    )
    service_scope = fields.Char(
        string='Scope', help="e.g. hood cleaning, grease trap emptying, fire extinguishers.",
    )

    # ── Reminders sent ──
    alert_90_sent = fields.Boolean(default=False)
    alert_60_sent = fields.Boolean(default=False)
    alert_30_sent = fields.Boolean(default=False)

    # ── Constraints ──

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.end_date and rec.start_date and rec.end_date < rec.start_date:
                raise ValidationError(_("The end of term cannot be before the start date."))

    @api.constrains('replaced_by_id')
    def _check_replaced_by(self):
        for rec in self:
            if rec.replaced_by_id and rec.replaced_by_id == rec:
                raise ValidationError(_("A contract cannot replace itself."))

    # ── Computes ──

    @api.depends('contract_type')
    def _compute_is_utility(self):
        for rec in self:
            rec.is_utility = rec.contract_type in UTILITY_TYPES

    @api.depends('contract_type')
    def _compute_unit_label(self):
        for rec in self:
            if not rec.unit_label or rec.contract_type in UNIT_LABEL_BY_TYPE:
                rec.unit_label = UNIT_LABEL_BY_TYPE.get(rec.contract_type, rec.unit_label)

    @api.depends('meter_ids')
    def _compute_meter_count(self):
        for rec in self:
            rec.meter_count = len(rec.meter_ids)

    @api.depends('rent_net', 'rent_charges', 'rent_vat')
    def _compute_rent_total(self):
        for rec in self:
            rec.rent_total = (rec.rent_net or 0.0) + (rec.rent_charges or 0.0) + (rec.rent_vat or 0.0)

    @api.depends('last_service_date', 'service_interval_months')
    def _compute_next_service_date(self):
        for rec in self:
            if rec.last_service_date and rec.service_interval_months:
                rec.next_service_date = rec.last_service_date + relativedelta(
                    months=rec.service_interval_months)
            else:
                rec.next_service_date = False

    @staticmethod
    def _notice_delta(value, unit):
        if unit == 'days':
            return relativedelta(days=value)
        if unit == 'weeks':
            return relativedelta(weeks=value)
        return relativedelta(months=value)

    @api.depends('end_date', 'notice_value', 'notice_unit')
    def _compute_termination_deadline(self):
        for rec in self:
            if not rec.end_date or not rec.notice_value:
                rec.termination_deadline = False
                continue
            rec.termination_deadline = rec.end_date - self._notice_delta(
                rec.notice_value, rec.notice_unit or 'months')

    @api.depends('termination_deadline')
    def _compute_days_to_deadline(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_to_deadline = (
                (rec.termination_deadline - today).days if rec.termination_deadline else 0
            )

    @api.depends(
        'contract_type', 'amount', 'frequency', 'rent_total',
        'monthly_installment', 'base_fee',
    )
    def _compute_annual_cost(self):
        for rec in self:
            if rec.contract_type == 'lease':
                rec.annual_cost = (rec.rent_total or 0.0) * 12
            elif rec.contract_type in UTILITY_TYPES:
                monthly = rec.monthly_installment or rec.base_fee or 0.0
                rec.annual_cost = monthly * 12
            else:
                rec.annual_cost = (rec.amount or 0.0) * FREQUENCY_PER_YEAR.get(rec.frequency, 1)

    @api.depends('end_date', 'termination_deadline', 'cancelled_on', 'start_date')
    def _compute_status(self):
        """Derive the lifecycle state from the dates.

        'draft' and 'cancelled' are set by hand and survive; everything else
        follows from today's date so the list is always current.
        """
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.cancelled_on:
                rec.status = 'cancelled'
                continue
            if rec.status == 'draft':
                continue
            if rec.end_date and rec.end_date < today and not rec.auto_renewal:
                rec.status = 'expired'
            elif (rec.termination_deadline
                  and today <= rec.termination_deadline <= today + relativedelta(days=90)):
                rec.status = 'expiring'
            else:
                rec.status = 'active'

    @api.depends('name', 'location_id.code', 'contract_type')
    def _compute_display_name(self):
        for rec in self:
            code = rec.location_id.code or rec.location_id.name or ''
            rec.display_name = f"{code} · {rec.name}" if code else rec.name

    # ── CRUD ──

    def write(self, vals):
        # A changed term or notice period means the reminders start over.
        if any(k in vals for k in ('end_date', 'notice_value', 'notice_unit')):
            vals = dict(vals, alert_90_sent=False, alert_60_sent=False, alert_30_sent=False)
        return super().write(vals)

    # ── Actions ──

    def action_confirm(self):
        self.write({'status': 'active'})
        self._compute_status()

    def action_cancel(self):
        self.write({'cancelled_on': fields.Date.context_today(self)})

    def action_reset_active(self):
        self.write({'cancelled_on': False, 'status': 'active'})
        self._compute_status()

    def action_renew_now(self):
        """Extend the term by one renewal period, as the provider would."""
        for rec in self:
            rec._roll_forward(reason=_("Renewed manually"))

    def action_view_meters(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'restaurant_location.action_location_meter')
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {
            'default_contract_id': self.id,
            'default_location_id': self.location_id.id,
        }
        return action

    def _covers(self, day):
        """Whether this contract was in force on a given day."""
        self.ensure_one()
        if not self.start_date or day < self.start_date:
            return False
        if self.cancelled_on and day > self.cancelled_on:
            return False
        return not self.end_date or day <= self.end_date

    def _roll_forward(self, reason=None):
        self.ensure_one()
        if not self.end_date or not self.renewal_months:
            return False
        old_end = self.end_date
        new_end = old_end
        today = fields.Date.context_today(self)
        while new_end < today:
            new_end = new_end + relativedelta(months=self.renewal_months)
        if new_end == old_end:
            new_end = old_end + relativedelta(months=self.renewal_months)
        self.write({'end_date': new_end})
        self.message_post(body=_(
            "%(reason)s: term extended from %(old)s to %(new)s.",
            reason=reason or _("Auto-renewal"), old=old_end, new=new_end,
        ))
        return True

    # ── Cron ──

    @api.model
    def _cron_check_termination_alerts(self):
        """Remind the responsible user at 90, 60 and 30 days before the
        cancellation deadline; roll auto-renewing contracts forward once
        their term has passed unnoticed."""
        today = fields.Date.context_today(self)

        # 1. Auto-renewing contracts whose cancellation deadline was missed:
        #    the renewal is now certain, so the term is extended right away
        #    and the next deadline is already correct. Contracts without a
        #    notice period roll once their term has ended.
        rolled = self.search([
            ('auto_renewal', '=', True),
            ('cancelled_on', '=', False),
            ('status', 'not in', ('draft', 'cancelled')),
            ('end_date', '!=', False),
            ('renewal_months', '>', 0),
            '|', ('termination_deadline', '<', today),
            '&', ('termination_deadline', '=', False), ('end_date', '<', today),
        ])
        for contract in rolled:
            contract._roll_forward(reason=_("Cancellation deadline passed"))

        # 2. Reminders.
        contracts = self.search([
            ('status', 'in', ('active', 'expiring')),
            ('termination_deadline', '!=', False),
        ])
        for contract in contracts:
            days_left = (contract.termination_deadline - today).days
            if days_left < 0:
                continue
            if days_left <= 30:
                stage, flags = 30, ('alert_30_sent', 'alert_60_sent', 'alert_90_sent')
            elif days_left <= 60:
                stage, flags = 60, ('alert_60_sent', 'alert_90_sent')
            elif days_left <= 90:
                stage, flags = 90, ('alert_90_sent',)
            else:
                continue
            if contract[flags[0]]:
                continue
            contract._schedule_deadline_activity(days_left, urgent=(stage == 30))
            # A stage reached late covers the earlier ones as well, so the
            # 60-day reminder never fires after the 30-day one.
            contract.write({flag: True for flag in flags})

    def _schedule_deadline_activity(self, days_left, urgent=False):
        self.ensure_one()
        renew_note = ''
        if self.auto_renewal and self.renewal_months:
            renew_note = _(" Missing it renews the contract for another %s months.",
                           self.renewal_months)
        prefix = _("URGENT: ") if urgent else ''
        summary = _(
            "%(prefix)sCancel \"%(name)s\" (%(location)s) by %(deadline)s — %(days)s days left",
            prefix=prefix, name=self.name, location=self.location_id.display_name,
            deadline=self.termination_deadline, days=days_left,
        )
        self.activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            date_deadline=self.termination_deadline,
            summary=summary,
            note=_("Notice period: %(n)s %(u)s.", n=self.notice_value, u=self.notice_unit) + renew_note,
            user_id=self.user_id.id or self.env.uid,
        )
