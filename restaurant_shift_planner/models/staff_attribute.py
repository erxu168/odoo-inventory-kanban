# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StaffAttribute(models.Model):
    """A property a staff member can hold, and that a shift can require.

    Four value types cover every matching rule we have found so far:

    * ``flag``          — yes/no, e.g. keyholder, till-trained
    * ``level``         — a graded scale, e.g. grill 0-3
    * ``number``        — a raw figure, e.g. tenure in days
    * ``certification`` — a flag that is only true while it is in date

    Whether a value is typed in by a manager or written by the system is a
    separate question, held in ``compute_method``: a computed attribute is
    still just an attribute, so requirements do not need to know the
    difference.
    """
    _name = 'restaurant.staff.attribute'
    _description = 'Staff Attribute'
    _order = 'category, sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help='Short technical identifier, unique. Used by computed '
             'attributes and by data imports.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()

    category = fields.Selection([
        ('skill', 'Skill'),
        ('certification', 'Certification'),
        ('authorisation', 'Authorisation'),
        ('trait', 'Trait'),
        ('performance', 'Performance'),
    ], default='skill', required=True)

    value_type = fields.Selection([
        ('flag', 'Yes / No'),
        ('level', 'Level'),
        ('number', 'Number'),
        ('certification', 'Certification (expires)'),
    ], default='level', required=True)

    scale_min = fields.Integer(default=0)
    scale_max = fields.Integer(default=3)
    scale_labels = fields.Char(
        string='Level Labels',
        help='Optional comma-separated labels, lowest first. '
             'For a 0-3 scale: "none, learning, works solo, can train others".',
    )

    compute_method = fields.Selection(
        selection='_selection_compute_method',
        default='none', required=True, string='Maintained By',
        help='Manual attributes are set by a manager. Computed attributes are '
             'written by the system and should not be edited by hand.',
    )

    review_interval_months = fields.Integer(
        default=12, string='Review Every (months)',
        help='Values older than this are flagged as due for review. '
             '0 disables the check.',
    )
    expiry_warning_days = fields.Integer(
        default=30, string='Warn Before Expiry (days)',
        help='Certifications raise an activity this many days before they lapse.',
    )

    requirement_ids = fields.One2many(
        'restaurant.shift.requirement', 'attribute_id', string='Used By',
    )
    requirement_count = fields.Integer(compute='_compute_counts')
    value_count = fields.Integer(compute='_compute_counts')

    @api.model
    def _selection_compute_method(self):
        """Extension point: later phases add computed sources here."""
        return [('none', 'Manual entry')]

    @api.depends('requirement_ids')
    def _compute_counts(self):
        Requirement = self.env['restaurant.shift.requirement']
        Value = self.env['restaurant.staff.attribute.value']
        req_counts = dict(Requirement._read_group(
            [('attribute_id', 'in', self.ids)],
            groupby=['attribute_id'], aggregates=['__count'],
        ))
        val_counts = dict(Value._read_group(
            [('attribute_id', 'in', self.ids)],
            groupby=['attribute_id'], aggregates=['__count'],
        ))
        for rec in self:
            rec.requirement_count = req_counts.get(rec, 0)
            rec.value_count = val_counts.get(rec, 0)

    @api.constrains('code')
    def _check_code_unique(self):
        for rec in self:
            if not rec.code:
                continue
            duplicate = self.with_context(active_test=False).search_count([
                ('code', '=', rec.code), ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(
                    _('Attribute code "%s" is already in use.') % rec.code
                )

    @api.constrains('scale_min', 'scale_max', 'value_type')
    def _check_scale(self):
        for rec in self:
            if rec.value_type == 'level' and rec.scale_max <= rec.scale_min:
                raise ValidationError(_(
                    'The highest level must be above the lowest one for "%s".'
                ) % rec.name)

    @api.onchange('value_type')
    def _onchange_value_type(self):
        if self.value_type == 'certification':
            self.category = 'certification'

    def _label_for(self, number):
        """Render a numeric value using the attribute's labels, if any."""
        self.ensure_one()
        if self.value_type in ('flag', 'certification'):
            return _('yes') if number else _('no')
        labels = [p.strip() for p in (self.scale_labels or '').split(',') if p.strip()]
        index = int(number) - self.scale_min
        if labels and 0 <= index < len(labels):
            return '%g (%s)' % (number, labels[index])
        return '%g' % number

    def action_view_requirements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Requirements using %s') % self.name,
            'res_model': 'restaurant.shift.requirement',
            'view_mode': 'list,form',
            'domain': [('attribute_id', '=', self.id)],
            'context': {'default_attribute_id': self.id},
        }

    def action_view_values(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s — staff values') % self.name,
            'res_model': 'restaurant.staff.attribute.value',
            'view_mode': 'list,form',
            'domain': [('attribute_id', '=', self.id)],
            'context': {'default_attribute_id': self.id},
        }
