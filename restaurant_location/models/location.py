# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class RestaurantLocation(models.Model):
    """One physical restaurant site.

    The record is the hub every other model in this module hangs off:
    supply and service contracts, meters, waste streams, permits and the
    people to call when something breaks. It is deliberately independent of
    the rentals/property tooling: a restaurant is operated, not let.
    """
    _name = 'restaurant.location'
    _description = 'Restaurant Location'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _check_company_auto = True

    # ── Identity ──
    name = fields.Char(string='Location', required=True, tracking=True)
    code = fields.Char(
        string='Short Code', tracking=True,
        help="Short code used on bills and in reports, e.g. GBM38.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Colour')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True,
    )
    state = fields.Selection([
        ('planned', 'Planned'),
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], string='Status', default='open', tracking=True)
    opened_on = fields.Date(string='Opened On')
    closed_on = fields.Date(string='Closed On')

    # ── Address & contact ──
    street = fields.Char()
    street2 = fields.Char()
    zip = fields.Char(string='ZIP')
    city = fields.Char()
    country_id = fields.Many2one(
        'res.country', string='Country',
        default=lambda self: self.env.company.country_id,
    )
    full_address = fields.Char(compute='_compute_full_address', store=True)
    phone = fields.Char()
    email = fields.Char()
    website = fields.Char()
    partner_id = fields.Many2one(
        'res.partner', string='Contact Record',
        help="Optional partner record for this site, e.g. the one used as "
             "delivery address on supplier orders.",
    )

    # ── Premises ──
    floor_area_sqm = fields.Float(string='Floor Area (m²)', digits=(10, 2))
    seats_indoor = fields.Integer(string='Seats Indoor')
    seats_outdoor = fields.Integer(string='Seats Outdoor')
    seats_total = fields.Integer(compute='_compute_seats_total', store=True)
    business_registration_no = fields.Char(
        string='Gewerbeanmeldung No.',
        help="Trade registration reference (Gewerbeanmeldung).",
    )
    tax_office_no = fields.Char(string='Tax Number (Steuernummer)')
    broadcasting_fee_no = fields.Char(
        string='Rundfunkbeitrag No.',
        help="ARD/ZDF broadcasting-fee account number for this site.",
    )

    # ── Landlord (summary; the lease itself is a contract of type 'lease') ──
    landlord_id = fields.Many2one(
        'res.partner', string='Landlord', tracking=True,
        compute='_compute_lease_summary', store=True, readonly=False,
        help="Filled from the active lease contract; can be overridden.",
    )
    property_manager_id = fields.Many2one(
        'res.partner', string='Property Manager (Hausverwaltung)', tracking=True,
    )
    lease_contract_id = fields.Many2one(
        'restaurant.location.contract', string='Current Lease',
        compute='_compute_lease_summary', store=True,
    )
    monthly_rent_total = fields.Monetary(
        string='Monthly Rent (incl. charges)', currency_field='currency_id',
        compute='_compute_lease_summary', store=True,
    )
    lease_end_date = fields.Date(
        string='Lease Ends', compute='_compute_lease_summary', store=True,
    )
    lease_termination_deadline = fields.Date(
        string='Lease: Cancel By', compute='_compute_lease_summary', store=True,
    )

    # ── People ──
    manager_user_ids = fields.Many2many(
        'res.users', 'restaurant_location_manager_rel', 'location_id', 'user_id',
        string='Location Managers',
        help="Users who manage this site. Location managers see and edit "
             "everything recorded for the sites they are listed on.",
    )
    staff_user_ids = fields.Many2many(
        'res.users', 'restaurant_location_staff_rel', 'location_id', 'user_id',
        string='Staff Users',
        help="Users who can see this site and record meter readings and "
             "waste pickups for it.",
    )
    contact_ids = fields.One2many(
        'restaurant.location.contact', 'location_id', string='Key Contacts',
    )

    # ── Related records ──
    contract_ids = fields.One2many(
        'restaurant.location.contract', 'location_id', string='Contracts',
    )
    meter_ids = fields.One2many('restaurant.location.meter', 'location_id', string='Meters')
    waste_stream_ids = fields.One2many(
        'restaurant.location.waste.stream', 'location_id', string='Waste Streams',
    )
    compliance_ids = fields.One2many(
        'restaurant.location.compliance', 'location_id', string='Permits & Inspections',
    )
    notes = fields.Html(string='Notes')

    # ── Counters ──
    contract_count = fields.Integer(compute='_compute_counts')
    active_contract_count = fields.Integer(compute='_compute_counts')
    meter_count = fields.Integer(compute='_compute_counts')
    waste_stream_count = fields.Integer(compute='_compute_counts')
    compliance_count = fields.Integer(compute='_compute_counts')
    attention_count = fields.Integer(
        string='Needs Attention', compute='_compute_counts',
        help="Contracts inside their cancellation window plus permits and "
             "inspections that are due or overdue.",
    )
    annual_fixed_cost = fields.Monetary(
        string='Annual Fixed Cost', currency_field='currency_id',
        compute='_compute_annual_fixed_cost', store=True,
        help="Sum of the annualised recurring fees of every active contract "
             "and waste service at this site. Consumption is not included.",
    )

    _code_company_uniq = models.Constraint(
        'UNIQUE(code, company_id)',
        'The short code must be unique per company.',
    )

    # ── Computes ──

    @api.depends('street', 'street2', 'zip', 'city', 'country_id')
    def _compute_full_address(self):
        for rec in self:
            parts = [rec.street, rec.street2, ' '.join(p for p in (rec.zip, rec.city) if p)]
            rec.full_address = ', '.join(p for p in parts if p)

    @api.depends('seats_indoor', 'seats_outdoor')
    def _compute_seats_total(self):
        for rec in self:
            rec.seats_total = (rec.seats_indoor or 0) + (rec.seats_outdoor or 0)

    @api.depends(
        'contract_ids.contract_type', 'contract_ids.status',
        'contract_ids.provider_id', 'contract_ids.rent_total',
        'contract_ids.end_date', 'contract_ids.termination_deadline',
        'contract_ids.start_date',
    )
    def _compute_lease_summary(self):
        for rec in self:
            leases = rec.contract_ids.filtered(
                lambda c: c.contract_type == 'lease' and c.status in ('active', 'expiring')
            ).sorted('start_date', reverse=True)
            lease = leases[:1]
            rec.lease_contract_id = lease
            rec.monthly_rent_total = lease.rent_total if lease else 0.0
            rec.lease_end_date = lease.end_date if lease else False
            rec.lease_termination_deadline = lease.termination_deadline if lease else False
            if lease and lease.provider_id:
                rec.landlord_id = lease.provider_id

    @api.depends(
        'contract_ids.status', 'contract_ids.termination_deadline',
        'compliance_ids.state', 'meter_ids', 'waste_stream_ids.active',
    )
    def _compute_counts(self):
        today = fields.Date.context_today(self)
        for rec in self:
            contracts = rec.contract_ids
            rec.contract_count = len(contracts)
            rec.active_contract_count = len(contracts.filtered(
                lambda c: c.status in ('active', 'expiring')))
            rec.meter_count = len(rec.meter_ids)
            rec.waste_stream_count = len(rec.waste_stream_ids.filtered('active'))
            rec.compliance_count = len(rec.compliance_ids)
            rec.attention_count = (
                len(contracts.filtered(lambda c: c.status == 'expiring'))
                + len(rec.compliance_ids.filtered(lambda c: c.state in ('due', 'overdue')))
            )

    @api.depends(
        'contract_ids.status', 'contract_ids.annual_cost',
        'waste_stream_ids.active', 'waste_stream_ids.annual_cost',
    )
    def _compute_annual_fixed_cost(self):
        for rec in self:
            contracts = rec.contract_ids.filtered(lambda c: c.status in ('active', 'expiring'))
            streams = rec.waste_stream_ids.filtered('active')
            rec.annual_fixed_cost = (
                sum(contracts.mapped('annual_cost')) + sum(streams.mapped('annual_cost'))
            )

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    # ── Actions (stat buttons) ──

    def _open_related(self, action_xmlid, default_field='location_id', extra_context=None):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(action_xmlid)
        ctx = dict(self.env.context)
        ctx.pop('search_default_group_location', None)
        ctx.update({f'default_{default_field}': self.id, f'search_default_{default_field}': self.id})
        ctx.update(extra_context or {})
        action['context'] = ctx
        action['domain'] = [(default_field, '=', self.id)]
        return action

    def action_view_contracts(self):
        return self._open_related('restaurant_location.action_location_contract')

    def action_view_meters(self):
        return self._open_related('restaurant_location.action_location_meter')

    def action_view_waste_streams(self):
        return self._open_related('restaurant_location.action_location_waste_stream')

    def action_view_compliance(self):
        return self._open_related('restaurant_location.action_location_compliance')

    def action_view_pickup_calendar(self):
        return self._open_related('restaurant_location.action_location_waste_pickup')

    def action_add_standard_checks(self):
        """Seed the usual obligations (grease trap, DGUV V3, extinguishers…)
        on this site, skipping the types it already tracks."""
        Compliance = self.env['restaurant.location.compliance']
        types = self.env['restaurant.location.compliance.type'].search([('is_standard', '=', True)])
        created = Compliance
        for rec in self:
            present = rec.compliance_ids.mapped('type_id')
            for ctype in types - present:
                created |= Compliance.create({
                    'location_id': rec.id,
                    'type_id': ctype.id,
                    'name': ctype.name,
                })
        if not created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': _("Every standard check is already on this location."),
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("%s check(s) added. Set the last date on each to get a due date.", len(created)),
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
