# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StaffAttributeValue(models.Model):
    """One employee's value for one attribute, over a validity period.

    Values are effective-dated rather than overwritten. A promotion or a
    renewed certificate is a new row, so a roster built last month can still
    be explained with the values that applied at the time, and a certificate's
    validity on a given day is provable after the fact.
    """
    _name = 'restaurant.staff.attribute.value'
    _description = 'Staff Attribute Value'
    _inherit = ['mail.thread']
    _order = 'employee_id, attribute_id, valid_from desc'

    employee_id = fields.Many2one(
        'hr.employee', required=True, ondelete='cascade',
        index=True, tracking=True,
    )
    attribute_id = fields.Many2one(
        'restaurant.staff.attribute', required=True, ondelete='cascade',
        index=True, tracking=True,
    )
    value_type = fields.Selection(related='attribute_id.value_type', readonly=True)
    category = fields.Selection(related='attribute_id.category', readonly=True, store=True)

    value_bool = fields.Boolean(string='Holds It', tracking=True)
    value_number = fields.Float(string='Value', tracking=True)

    valid_from = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True,
    )
    valid_until = fields.Date(
        tracking=True, help='Leave empty for no end date.',
    )

    source = fields.Selection([
        ('manual', 'Manual'),
        ('computed', 'Computed'),
    ], default='manual', required=True)

    note = fields.Char()
    evidence = fields.Binary(attachment=True)
    evidence_filename = fields.Char()
    reviewed_on = fields.Date()

    display_value = fields.Char(compute='_compute_display_value')
    status = fields.Selection([
        ('future', 'Not Yet Valid'),
        ('current', 'Current'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
    ], compute='_compute_status', search='_search_status')
    review_due = fields.Boolean(compute='_compute_status',
                                search='_search_review_due')
    expiry_warned = fields.Boolean(default=False, copy=False)

    # ── Computed ─────────────────────────────────────────────

    @api.depends('attribute_id', 'value_bool', 'value_number')
    def _compute_display_value(self):
        for rec in self:
            if not rec.attribute_id:
                rec.display_value = ''
            elif rec.attribute_id.value_type in ('flag', 'certification'):
                rec.display_value = _('yes') if rec.value_bool else _('no')
            else:
                rec.display_value = rec.attribute_id._label_for(rec.value_number)

    @api.depends('valid_from', 'valid_until', 'reviewed_on',
                 'attribute_id.expiry_warning_days',
                 'attribute_id.review_interval_months')
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.valid_from and rec.valid_from > today:
                rec.status = 'future'
            elif rec.valid_until and rec.valid_until < today:
                rec.status = 'expired'
            elif rec.valid_until and (rec.valid_until - today).days <= (
                    rec.attribute_id.expiry_warning_days or 0):
                rec.status = 'expiring'
            else:
                rec.status = 'current'

            months = rec.attribute_id.review_interval_months or 0
            if not months:
                rec.review_due = False
            else:
                anchor = rec.reviewed_on or rec.valid_from
                rec.review_due = bool(
                    anchor and (today - anchor).days > months * 30
                )

    def _search_status(self, operator, value):
        # "Expiring" depends on each attribute's own warning window, so this
        # cannot be expressed as a plain domain. The table is one row per
        # person per attribute, so evaluating it in Python is cheap.
        wanted = value if isinstance(value, (list, tuple)) else [value]
        if operator in ('!=', 'not in'):
            wanted = [s for s in ('future', 'current', 'expiring', 'expired')
                      if s not in wanted]
        matches = self.search([]).filtered(lambda r: r.status in wanted)
        return [('id', 'in', matches.ids)]

    def _search_review_due(self, operator, value):
        matches = self.search([]).filtered('review_due')
        negate = (operator in ('=', '==') and not value) or (
            operator in ('!=',) and value)
        if negate:
            return [('id', 'not in', matches.ids)]
        return [('id', 'in', matches.ids)]

    @api.depends('employee_id', 'attribute_id', 'display_value')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s: %s' % (
                rec.employee_id.name or '',
                rec.attribute_id.name or '',
                rec.display_value or '',
            )

    # ── Constraints ──────────────────────────────────────────

    @api.constrains('valid_from', 'valid_until')
    def _check_dates(self):
        for rec in self:
            if rec.valid_until and rec.valid_from and rec.valid_until < rec.valid_from:
                raise ValidationError(_('The end date cannot precede the start date.'))

    @api.constrains('employee_id', 'attribute_id', 'valid_from', 'valid_until')
    def _check_no_overlap(self):
        """Two values for the same attribute must not both apply on one day.

        Without this, "which value applied on the 14th" has no single answer
        and the roster stops being reproducible.
        """
        for rec in self:
            overlapping = self.search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('attribute_id', '=', rec.attribute_id.id),
                '|', ('valid_until', '=', False),
                     ('valid_until', '>=', rec.valid_from),
            ])
            for other in overlapping:
                if not rec.valid_until or other.valid_from <= rec.valid_until:
                    raise ValidationError(_(
                        'These dates overlap an existing "%(attribute)s" value '
                        'for %(employee)s (%(other_from)s → %(other_until)s). '
                        'Close the old value first.',
                        attribute=rec.attribute_id.name,
                        employee=rec.employee_id.name,
                        other_from=other.valid_from,
                        other_until=other.valid_until or _('open'),
                    ))

    # ── Actions ──────────────────────────────────────────────

    def action_close_today(self):
        """End a value as of today — the normal way to supersede one."""
        today = fields.Date.context_today(self)
        for rec in self:
            rec.valid_until = today

    # ── Cron ─────────────────────────────────────────────────

    @api.model
    def _cron_certification_expiry(self):
        """Raise an activity for certifications about to lapse.

        Nobody tracks certificate dates by hand for long, so this has to be
        automatic or the hard requirements silently start failing.
        """
        today = fields.Date.context_today(self)
        candidates = self.search([
            ('expiry_warned', '=', False),
            ('valid_until', '!=', False),
            ('valid_until', '>=', today),
            ('attribute_id.value_type', '=', 'certification'),
        ])
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False,
        )
        for rec in candidates:
            warn_days = rec.attribute_id.expiry_warning_days or 0
            if (rec.valid_until - today).days > warn_days:
                continue
            employee = rec.employee_id
            user = employee.parent_id.user_id or employee.user_id
            if user and activity_type:
                employee.activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_todo',
                    date_deadline=rec.valid_until,
                    summary=_('%s expires') % rec.attribute_id.name,
                    note=_(
                        '%(name)s\'s %(attribute)s expires on %(date)s. '
                        'Shifts requiring it will stop accepting them from '
                        'that date.',
                        name=employee.name,
                        attribute=rec.attribute_id.name,
                        date=rec.valid_until,
                    ),
                    user_id=user.id,
                )
            rec.expiry_warned = True
