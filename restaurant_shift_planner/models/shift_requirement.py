# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

WEEKDAY_FIELDS = ['day_mon', 'day_tue', 'day_wed', 'day_thu',
                  'day_fri', 'day_sat', 'day_sun']

# Plain strings, not _(): module-level translation happens before any
# environment exists. They are substituted into _()-wrapped sentences below.
OPERATOR_LABELS = {
    'gte': 'at least',
    'lte': 'at most',
    'eq': 'exactly',
    'is_true': 'must have',
    'is_valid': 'must hold a valid',
}


class ShiftRequirement(models.Model):
    """What a shift needs from the people working it.

    Two scopes, and both are necessary:

    ``each``  every person on the shift must satisfy it — "everyone holds a
              valid hygiene certificate". A team rule cannot express this.
    ``team``  the crew as a whole must satisfy it — "at least one keyholder",
              "at most one trainee", "average speed 3.5". A per-person rule
              cannot express this.

    A requirement is a data row, so a new rule never needs a code change.
    """
    _name = 'restaurant.shift.requirement'
    _description = 'Shift Requirement'
    _order = 'sequence, id'

    name = fields.Char(compute='_compute_name', store=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    template_id = fields.Many2one(
        'planning.slot.template', string='Shift Template',
        ondelete='cascade', index=True,
        help='Leave empty to apply this requirement to every shift.',
    )
    role_id = fields.Many2one(
        'planning.role', string='Only For Role',
        help='Restrict to shifts being filled for this role. '
             'Empty means every role on the shift.',
    )

    attribute_id = fields.Many2one(
        'restaurant.staff.attribute', required=True, ondelete='cascade',
    )
    value_type = fields.Selection(related='attribute_id.value_type', readonly=True)

    scope = fields.Selection([
        ('each', 'Every person on the shift'),
        ('team', 'The crew as a whole'),
    ], default='each', required=True)

    operator = fields.Selection([
        ('gte', 'At least'),
        ('lte', 'At most'),
        ('eq', 'Exactly'),
        ('is_true', 'Must have'),
        ('is_valid', 'Must be valid on the day'),
    ], default='gte', required=True)
    value = fields.Float(string='Threshold')

    aggregate = fields.Selection([
        ('count', 'Number of people meeting it'),
        ('avg', 'Crew average'),
        ('min', 'Crew lowest'),
        ('max', 'Crew highest'),
        ('sum', 'Crew total'),
    ], default='count', string='Measured As')
    min_count = fields.Integer(default=1, string='At Least (people)')
    use_max_count = fields.Boolean(string='Also Cap The Number')
    max_count = fields.Integer(default=1, string='At Most (people)')

    # Applicability — Friday's bar can be stricter than Tuesday's without
    # cloning the template into something that drifts out of sync.
    day_mon = fields.Boolean('Mon')
    day_tue = fields.Boolean('Tue')
    day_wed = fields.Boolean('Wed')
    day_thu = fields.Boolean('Thu')
    day_fri = fields.Boolean('Fri')
    day_sat = fields.Boolean('Sat')
    day_sun = fields.Boolean('Sun')
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')

    enforcement = fields.Selection([
        ('hard', 'Required'),
        ('soft', 'Preferred'),
    ], default='hard', required=True)
    weight = fields.Integer(default=5, help='Used when Preferred, 0-10.')

    message = fields.Char(
        string='Custom Message',
        help='Shown instead of the generated wording when this fails.',
    )

    # ── Naming ───────────────────────────────────────────────

    @api.depends('attribute_id', 'scope', 'operator', 'value', 'aggregate',
                 'min_count', 'max_count', 'use_max_count', 'role_id')
    def _compute_name(self):
        for rec in self:
            rec.name = rec._describe()

    def _describe(self):
        self.ensure_one()
        attribute = self.attribute_id.name or _('attribute')
        test = self._describe_test()
        if self.scope == 'each':
            text = _('Every person: %s') % test
        elif self.aggregate == 'count':
            parts = []
            if self.min_count:
                parts.append(_('at least %d') % self.min_count)
            if self.use_max_count:
                parts.append(_('at most %d') % self.max_count)
            text = _('Crew: %(counts)s with %(test)s',
                     counts=_(' and ').join(parts) or _('any number'), test=test)
        else:
            labels = dict(self._fields['aggregate'].selection)
            text = _('%(measure)s of %(attribute)s %(op)s %(value)g',
                     measure=labels.get(self.aggregate, ''),
                     attribute=attribute,
                     op=OPERATOR_LABELS.get(self.operator, ''),
                     value=self.value)
        if self.role_id:
            text = _('%(text)s (role: %(role)s)', text=text, role=self.role_id.name)
        return text

    def _describe_test(self):
        self.ensure_one()
        attribute = self.attribute_id.name or _('attribute')
        if self.operator == 'is_true':
            return attribute
        if self.operator == 'is_valid':
            return _('valid %s') % attribute
        return '%s %s %s' % (
            attribute,
            OPERATOR_LABELS.get(self.operator, ''),
            self.attribute_id._label_for(self.value) if self.attribute_id else self.value,
        )

    # ── Constraints ──────────────────────────────────────────

    @api.constrains('scope', 'aggregate', 'min_count', 'max_count', 'use_max_count')
    def _check_counts(self):
        for rec in self:
            if rec.scope != 'team' or rec.aggregate != 'count':
                continue
            if rec.use_max_count and rec.max_count < rec.min_count:
                raise ValidationError(_(
                    '"At most" cannot be below "at least" in requirement "%s".'
                ) % rec.name)

    @api.onchange('value_type')
    def _onchange_value_type(self):
        if self.value_type == 'certification':
            self.operator = 'is_valid'
        elif self.value_type == 'flag':
            self.operator = 'is_true'

    # ── Applicability ────────────────────────────────────────

    def _applies_on(self, on_date, role=None):
        """Is this requirement in force for a shift on ``on_date``?"""
        self.ensure_one()
        if self.date_from and on_date < self.date_from:
            return False
        if self.date_to and on_date > self.date_to:
            return False
        selected = [self[f] for f in WEEKDAY_FIELDS]
        # No day ticked means "every day" — the common case stays zero-effort.
        if any(selected) and not selected[on_date.weekday()]:
            return False
        if self.role_id and role and self.role_id != role:
            return False
        return True

    # ── Evaluation ───────────────────────────────────────────
    #
    # ``values`` throughout is the map returned by
    # hr.employee._shift_attribute_map(date): it is already filtered to the
    # values in force on the shift's date, so an expired certification simply
    # is not there — expiry needs no special case below.

    def _value_of(self, value_record):
        """Numeric reading of a value record; a missing value reads as 0."""
        self.ensure_one()
        if not value_record:
            return 0.0
        if self.attribute_id.value_type in ('flag', 'certification'):
            return 1.0 if value_record.value_bool else 0.0
        return value_record.value_number

    def _matches(self, value_record):
        """Does one person's value satisfy this requirement's test?"""
        self.ensure_one()
        if self.operator in ('is_true', 'is_valid'):
            return bool(value_record) and bool(value_record.value_bool)
        number = self._value_of(value_record)
        if self.operator == 'gte':
            return number >= self.value
        if self.operator == 'lte':
            return number <= self.value
        if self.operator == 'eq':
            return abs(number - self.value) < 1e-6
        return True

    def _evaluate_each(self, employee, values):
        """Check one person. Returns (ok, message)."""
        self.ensure_one()
        value_record = values.get(employee.id, {}).get(self.attribute_id.id)
        if self._matches(value_record):
            return True, ''
        return False, self.message or _(
            '%(employee)s does not meet "%(requirement)s" (has: %(actual)s).',
            employee=employee.name,
            requirement=self._describe_test(),
            actual=self._actual_text(value_record),
        )

    def _evaluate_team(self, employees, values):
        """Check the crew as a whole. Returns (ok, message)."""
        self.ensure_one()
        records = [values.get(e.id, {}).get(self.attribute_id.id) for e in employees]

        if self.aggregate == 'count':
            matching = sum(1 for r in records if self._matches(r))
            if matching < self.min_count:
                return False, self.message or _(
                    'Shift needs %(needed)d with %(test)s but has %(actual)d.',
                    needed=self.min_count, test=self._describe_test(),
                    actual=matching,
                )
            if self.use_max_count and matching > self.max_count:
                return False, self.message or _(
                    'Shift allows at most %(allowed)d with %(test)s but has '
                    '%(actual)d.',
                    allowed=self.max_count, test=self._describe_test(),
                    actual=matching,
                )
            return True, ''

        numbers = [self._value_of(r) for r in records]
        if not numbers:
            return True, ''
        actual = {
            'avg': sum(numbers) / len(numbers),
            'min': min(numbers),
            'max': max(numbers),
            'sum': sum(numbers),
        }[self.aggregate]
        ok = (
            actual >= self.value if self.operator == 'gte' else
            actual <= self.value if self.operator == 'lte' else
            abs(actual - self.value) < 1e-6 if self.operator == 'eq' else True
        )
        if ok:
            return True, ''
        return False, self.message or _(
            'Crew %(measure)s for %(attribute)s is %(actual).1f, needs '
            '%(op)s %(target)g.',
            measure=dict(self._fields['aggregate'].selection).get(self.aggregate, ''),
            attribute=self.attribute_id.name,
            actual=actual,
            op=OPERATOR_LABELS.get(self.operator, ''),
            target=self.value,
        )

    def _actual_text(self, value_record):
        self.ensure_one()
        if not value_record:
            return _('not recorded')
        return value_record.display_value

    # ── Entry point ──────────────────────────────────────────

    @api.model
    def _evaluate(self, requirements, members, on_date, values=None):
        """Evaluate a set of requirements against the people on one shift.

        ``members`` is an iterable of ``(employee, template, role)`` — one
        entry per person working the shift. Per-person rules are checked
        against each member using that member's own template and role; crew
        rules are checked once over everyone.

        This is the single matching routine. The live warning on the shift
        form, the coverage gap report and (in phase 2) the generator all come
        through here, so they cannot disagree about who is suitable.

        Returns ``(state, failures)`` where state is one of
        ``na | ok | warning | violation`` and each failure is
        ``(requirement, employee_or_empty, message)``.
        """
        Employee = self.env['hr.employee']
        members = [m for m in members if m[0]]
        if not members or not requirements:
            return 'na', []

        crew = Employee.browse()
        for employee, _template, _role in members:
            crew |= employee
        if values is None:
            values = crew._shift_attribute_map(on_date)

        failures = []
        for employee, template, role in members:
            for requirement in requirements:
                if requirement.scope != 'each':
                    continue
                # A requirement pinned to a template only judges the people
                # working that template; an unpinned one judges everyone.
                if requirement.template_id and requirement.template_id != template:
                    continue
                if not requirement._applies_on(on_date, role):
                    continue
                ok, message = requirement._evaluate_each(employee, values)
                if not ok:
                    failures.append((requirement, employee, message))

        for requirement in requirements:
            if requirement.scope != 'team':
                continue
            if not requirement._applies_on(on_date):
                continue
            ok, message = requirement._evaluate_team(crew, values)
            if not ok:
                failures.append((requirement, Employee, message))

        if any(r.enforcement == 'hard' for r, _e, _m in failures):
            return 'violation', failures
        return ('warning' if failures else 'ok'), failures

    @api.model
    def _for_templates(self, templates):
        """Requirements in force for these shift templates, plus global ones.

        A requirement with no template applies everywhere — that is how a
        house rule ("everyone hygiene-certified") gets written once.
        """
        return self.search([
            '|', ('template_id', '=', False), ('template_id', 'in', templates.ids),
        ])

    @api.model
    def _candidates(self, requirements, employees, on_date, role=None,
                    values=None):
        """Employees who pass every hard per-person requirement.

        Team requirements cannot be judged one person at a time, so they are
        not applied here — this answers "who could work this shift at all",
        which is what the gap report needs.
        """
        requirements = requirements.filtered(
            lambda r: r.scope == 'each' and r.enforcement == 'hard'
            and r._applies_on(on_date, role)
        )
        if not requirements:
            return employees
        if values is None:
            values = employees._shift_attribute_map(on_date)
        return employees.filtered(lambda e: all(
            r._evaluate_each(e, values)[0] for r in requirements
        ))
