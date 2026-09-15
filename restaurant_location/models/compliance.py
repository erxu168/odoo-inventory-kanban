# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _

COMPLIANCE_CATEGORIES = [
    ('permit', 'Permit / Licence'),
    ('inspection', 'Official Inspection'),
    ('safety_check', 'Safety Check'),
    ('maintenance', 'Maintenance Duty'),
    ('training', 'Staff Training / Briefing'),
    ('registration', 'Registration'),
    ('other', 'Other'),
]

COMPLIANCE_STATES = [
    ('ok', 'OK'),
    ('due', 'Due Soon'),
    ('overdue', 'Overdue'),
    ('none', 'No Date'),
]


class RestaurantLocationComplianceType(models.Model):
    """A recurring legal or contractual obligation a site has to meet.

    Seeded with the checks a German restaurant is normally asked for
    (grease trap emptying, DGUV V3, extinguishers, dispensing systems,
    hood cleaning, the Gaststättenerlaubnis…). Editable, so a new
    obligation is a configuration row, not a code change.
    """
    _name = 'restaurant.location.compliance.type'
    _description = 'Permit / Inspection Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category = fields.Selection(COMPLIANCE_CATEGORIES, required=True, default='inspection')
    interval_months = fields.Integer(
        string='Repeats Every (Months)', default=12, aggregator=None,
        help="0 for one-off items such as a licence without an expiry.",
    )
    reminder_days = fields.Integer(
        string='Remind (Days Before)', default=30, aggregator=None,
    )
    is_standard = fields.Boolean(
        string='Standard for Every Site', default=True,
        help="Added to a location by 'Add Standard Checks'.",
    )
    legal_basis = fields.Char(string='Legal Basis / Standard', translate=True)
    description = fields.Text(translate=True)


class RestaurantLocationCompliance(models.Model):
    """One obligation at one site, with its last and next date."""
    _name = 'restaurant.location.compliance'
    _description = 'Permit / Inspection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date asc, id'
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    type_id = fields.Many2one(
        'restaurant.location.compliance.type', string='Type', ondelete='restrict',
    )
    category = fields.Selection(
        COMPLIANCE_CATEGORIES, required=True,
        compute='_compute_from_type', store=True, precompute=True, readonly=False,
    )
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
    active = fields.Boolean(default=True)
    authority_id = fields.Many2one(
        'res.partner', string='Authority / Inspector',
        help="Who issues, inspects or services it.",
    )
    reference = fields.Char(string='Reference No.', help="Licence number, certificate number…")
    interval_months = fields.Integer(
        string='Repeats Every (Months)', compute='_compute_from_type',
        store=True, precompute=True, readonly=False, aggregator=None,
    )
    reminder_days = fields.Integer(
        string='Remind (Days Before)', compute='_compute_from_type',
        store=True, precompute=True, readonly=False, aggregator=None,
    )
    last_done = fields.Date(string='Last Done / Issued', tracking=True)
    due_date = fields.Date(
        string='Due / Valid Until', compute='_compute_due_date', store=True, readonly=False,
        tracking=True,
        help="Computed from the last date and the interval; can be typed "
             "over for a fixed expiry such as a licence.",
    )
    state = fields.Selection(
        COMPLIANCE_STATES, compute='_compute_state', store=True, string='Status',
    )
    days_left = fields.Integer(compute='_compute_state', store=True, aggregator=None)
    cost = fields.Monetary(string='Cost per Occurrence', currency_field='currency_id')
    contract_id = fields.Many2one(
        'restaurant.location.contract', string='Service Contract',
        domain="[('location_id', '=', location_id)]",
        help="The maintenance contract that covers this check, if any.",
    )
    user_id = fields.Many2one(
        'res.users', string='Responsible', default=lambda self: self.env.user,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment', 'restaurant_location_compliance_attachment_rel',
        'compliance_id', 'attachment_id', string='Certificates / Documents',
    )
    notes = fields.Text()
    reminder_sent_for = fields.Date(
        help="Due date the last reminder was raised for; stops repeats.",
    )

    @api.depends('type_id')
    def _compute_from_type(self):
        """Copy the type's defaults; all three fields stay editable per site.
        No field default here on purpose: a default would count as a
        user-supplied value and stop this compute from running on create."""
        for rec in self:
            if rec.type_id:
                rec.category = rec.type_id.category
                rec.interval_months = rec.type_id.interval_months
                rec.reminder_days = rec.type_id.reminder_days
            else:
                rec.category = rec.category or 'inspection'
                rec.interval_months = rec.interval_months or 12
                rec.reminder_days = rec.reminder_days or 30

    @api.onchange('type_id')
    def _onchange_type_id(self):
        if self.type_id and not self.name:
            self.name = self.type_id.name

    @api.depends('last_done', 'interval_months')
    def _compute_due_date(self):
        for rec in self:
            if rec.last_done and rec.interval_months:
                rec.due_date = rec.last_done + relativedelta(months=rec.interval_months)
            else:
                # Fixed expiry typed by hand (a licence) stays as it is.
                rec.due_date = rec.due_date

    @api.depends('due_date', 'reminder_days')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.due_date:
                rec.state = 'none'
                rec.days_left = 0
                continue
            rec.days_left = (rec.due_date - today).days
            if rec.days_left < 0:
                rec.state = 'overdue'
            elif rec.days_left <= (rec.reminder_days or 0):
                rec.state = 'due'
            else:
                rec.state = 'ok'

    @api.depends('name', 'location_id.code')
    def _compute_display_name(self):
        for rec in self:
            code = rec.location_id.code
            rec.display_name = f"{code} · {rec.name}" if code else rec.name

    def action_mark_done(self):
        """Record that the check happened today; the next due date follows."""
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({'last_done': today, 'reminder_sent_for': False})
            rec.message_post(body=_("Marked as done on %s.", today))
            if not rec.interval_months:
                rec.due_date = False

    @api.model
    def _cron_check_due(self):
        """Raise one activity per item when it enters its reminder window."""
        today = fields.Date.context_today(self)
        items = self.search([('due_date', '!=', False), ('active', '=', True)])
        for item in items:
            days_left = (item.due_date - today).days
            if days_left > (item.reminder_days or 0):
                continue
            if item.reminder_sent_for == item.due_date:
                continue
            state = _("overdue by %s days", -days_left) if days_left < 0 else _("due in %s days", days_left)
            item.activity_schedule(
                act_type_xmlid='mail.mail_activity_data_todo',
                date_deadline=item.due_date,
                summary=_("%(name)s at %(loc)s is %(state)s",
                          name=item.name, loc=item.location_id.display_name, state=state),
                note=item.notes or '',
                user_id=item.user_id.id or self.env.uid,
            )
            item.reminder_sent_for = item.due_date
