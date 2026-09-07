# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestShiftRequirement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = date(2026, 9, 4)          # a Friday
        cls.tuesday = date(2026, 9, 8)

        Attribute = cls.env['restaurant.staff.attribute']
        cls.grill = Attribute.create({
            'name': 'Grill', 'code': 'test_grill', 'value_type': 'level',
            'scale_min': 0, 'scale_max': 3,
        })
        cls.keyholder = Attribute.create({
            'name': 'Keyholder', 'code': 'test_keyholder', 'value_type': 'flag',
        })
        cls.hygiene = Attribute.create({
            'name': 'Hygiene', 'code': 'test_hygiene',
            'value_type': 'certification',
        })

        Employee = cls.env['hr.employee']
        cls.senior = Employee.create({'name': 'Senior'})
        cls.junior = Employee.create({'name': 'Junior'})
        cls.newbie = Employee.create({'name': 'Newbie'})
        cls.crew = cls.senior | cls.junior | cls.newbie
        cls.no_template = cls.env['planning.slot.template']
        cls.no_role = cls.env['planning.role']

        cls._value(cls.senior, cls.grill, number=3)
        cls._value(cls.junior, cls.grill, number=1)
        # Newbie has no grill value at all — a missing value must read as 0,
        # not as "unknown, allow it".

        cls._value(cls.senior, cls.keyholder, flag=True)
        cls._value(cls.junior, cls.keyholder, flag=False)

        cls._value(cls.senior, cls.hygiene, flag=True)
        # Junior's certificate lapsed before the shift date.
        cls._value(cls.junior, cls.hygiene, flag=True,
                   valid_from=date(2026, 1, 1), valid_until=date(2026, 8, 1))

    @classmethod
    def _value(cls, employee, attribute, number=0.0, flag=False,
               valid_from=None, valid_until=None):
        return cls.env['restaurant.staff.attribute.value'].create({
            'employee_id': employee.id,
            'attribute_id': attribute.id,
            'value_number': number,
            'value_bool': flag,
            'valid_from': valid_from or date(2026, 1, 1),
            'valid_until': valid_until,
        })

    def _requirement(self, vals):
        return self.env['restaurant.shift.requirement'].create(vals)

    # ── Per-person scope ─────────────────────────────────────

    def test_each_level_threshold(self):
        requirement = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'each',
            'operator': 'gte', 'value': 2,
        })
        values = self.crew._shift_attribute_map(self.today)
        self.assertTrue(requirement._evaluate_each(self.senior, values)[0])
        self.assertFalse(requirement._evaluate_each(self.junior, values)[0])

    def test_missing_value_fails_a_minimum(self):
        """No recorded value must not silently pass a 'at least' test."""
        requirement = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'each',
            'operator': 'gte', 'value': 1,
        })
        values = self.crew._shift_attribute_map(self.today)
        ok, message = requirement._evaluate_each(self.newbie, values)
        self.assertFalse(ok)
        self.assertIn('not recorded', message)

    def test_expired_certification_fails(self):
        """Expiry needs no special case: the value is simply out of window."""
        requirement = self._requirement({
            'attribute_id': self.hygiene.id, 'scope': 'each',
            'operator': 'is_valid',
        })
        values = self.crew._shift_attribute_map(self.today)
        self.assertTrue(requirement._evaluate_each(self.senior, values)[0])
        self.assertFalse(requirement._evaluate_each(self.junior, values)[0])

        # ...and it passed while it was still in date.
        old = self.crew._shift_attribute_map(date(2026, 7, 1))
        self.assertTrue(requirement._evaluate_each(self.junior, old)[0])

    # ── Crew scope ───────────────────────────────────────────

    def test_team_count_minimum(self):
        requirement = self._requirement({
            'attribute_id': self.keyholder.id, 'scope': 'team',
            'aggregate': 'count', 'operator': 'is_true', 'min_count': 1,
        })
        values = self.crew._shift_attribute_map(self.today)
        self.assertTrue(requirement._evaluate_team(self.crew, values)[0])
        self.assertFalse(
            requirement._evaluate_team(self.junior | self.newbie, values)[0]
        )

    def test_team_count_maximum(self):
        """'At most one person below level 1' — the trainee cap."""
        requirement = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'team',
            'aggregate': 'count', 'operator': 'lte', 'value': 0,
            'min_count': 0, 'use_max_count': True, 'max_count': 1,
        })
        values = self.crew._shift_attribute_map(self.today)
        self.assertTrue(requirement._evaluate_team(self.crew, values)[0])

        another = self.env['hr.employee'].create({'name': 'Newbie 2'})
        ok, message = requirement._evaluate_team(self.crew | another, values)
        self.assertFalse(ok)
        self.assertIn('at most', message)

    def test_team_average(self):
        requirement = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'team',
            'aggregate': 'avg', 'operator': 'gte', 'value': 2,
        })
        values = self.crew._shift_attribute_map(self.today)
        # (3 + 1 + 0) / 3 = 1.33
        self.assertFalse(requirement._evaluate_team(self.crew, values)[0])
        self.assertTrue(
            requirement._evaluate_team(self.senior | self.junior, values)[0]
        )

    # ── Applicability ────────────────────────────────────────

    def test_weekday_filter(self):
        """Friday can be stricter than Tuesday on the same template."""
        requirement = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'each',
            'operator': 'gte', 'value': 2, 'day_fri': True, 'day_sat': True,
        })
        self.assertTrue(requirement._applies_on(self.today))
        self.assertFalse(requirement._applies_on(self.tuesday))

    def test_no_weekday_ticked_means_every_day(self):
        requirement = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'each',
            'operator': 'gte', 'value': 2,
        })
        self.assertTrue(requirement._applies_on(self.today))
        self.assertTrue(requirement._applies_on(self.tuesday))

    def test_date_range(self):
        requirement = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'each',
            'operator': 'gte', 'value': 2,
            'date_from': date(2026, 12, 1), 'date_to': date(2026, 12, 31),
        })
        self.assertFalse(requirement._applies_on(self.today))
        self.assertTrue(requirement._applies_on(date(2026, 12, 24)))

    # ── Candidate filtering ──────────────────────────────────

    def test_candidates_applies_hard_per_person_rules_only(self):
        hard = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'each',
            'operator': 'gte', 'value': 2, 'enforcement': 'hard',
        })
        soft = self._requirement({
            'attribute_id': self.keyholder.id, 'scope': 'each',
            'operator': 'is_true', 'enforcement': 'soft',
        })
        team = self._requirement({
            'attribute_id': self.keyholder.id, 'scope': 'team',
            'aggregate': 'count', 'operator': 'is_true', 'min_count': 1,
        })
        Requirement = self.env['restaurant.shift.requirement']
        candidates = Requirement._candidates(
            hard | soft | team, self.crew, self.today,
        )
        # Only the hard per-person rule narrows the pool: a preferred rule is
        # not a bar to entry, and a crew rule cannot be judged one at a time.
        self.assertEqual(candidates, self.senior)

    # ── The shared evaluation routine ────────────────────────

    def test_evaluate_mixes_person_and_crew_rules(self):
        per_person = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'each',
            'operator': 'gte', 'value': 1,
        })
        crew_rule = self._requirement({
            'attribute_id': self.keyholder.id, 'scope': 'team',
            'aggregate': 'count', 'operator': 'is_true', 'min_count': 2,
        })
        Requirement = self.env['restaurant.shift.requirement']
        members = [(e, self.no_template, self.no_role) for e in self.crew]
        state, failures = Requirement._evaluate(
            per_person | crew_rule, members, self.today,
        )
        self.assertEqual(state, 'violation')
        # Newbie fails the per-person rule; the crew has one keyholder, not two.
        by_requirement = {r: (e, m) for r, e, m in failures}
        self.assertEqual(by_requirement[per_person][0], self.newbie)
        self.assertIn(crew_rule, by_requirement)

    def test_soft_failure_is_a_warning_not_a_violation(self):
        self._requirement({
            'attribute_id': self.grill.id, 'scope': 'each',
            'operator': 'gte', 'value': 3, 'enforcement': 'soft',
        })
        Requirement = self.env['restaurant.shift.requirement']
        requirements = Requirement.search([('enforcement', '=', 'soft')])
        members = [(self.junior, self.no_template, self.no_role)]
        state, failures = Requirement._evaluate(
            requirements, members, self.today,
        )
        self.assertEqual(state, 'warning')
        self.assertTrue(failures)

    def test_no_members_means_no_check(self):
        requirement = self._requirement({
            'attribute_id': self.grill.id, 'scope': 'each',
            'operator': 'gte', 'value': 2,
        })
        Requirement = self.env['restaurant.shift.requirement']
        state, failures = Requirement._evaluate(requirement, [], self.today)
        self.assertEqual(state, 'na')
        self.assertFalse(failures)

    # ── Effective dating ─────────────────────────────────────

    def test_overlapping_values_are_rejected(self):
        with self.assertRaises(ValidationError):
            self._value(self.senior, self.grill, number=2,
                        valid_from=date(2026, 6, 1))

    def test_superseding_a_value(self):
        current = self.env['restaurant.staff.attribute.value'].search([
            ('employee_id', '=', self.junior.id),
            ('attribute_id', '=', self.grill.id),
        ], limit=1)
        current.valid_until = date(2026, 8, 31)
        self._value(self.junior, self.grill, number=3,
                    valid_from=date(2026, 9, 1))

        after = self.crew._shift_attribute_map(self.today)
        before = self.crew._shift_attribute_map(date(2026, 8, 15))
        self.assertEqual(after[self.junior.id][self.grill.id].value_number, 3)
        self.assertEqual(before[self.junior.id][self.grill.id].value_number, 1)


@tagged('post_install', '-at_install')
class TestPlanningSlotCheck(TransactionCase):
    """The manual-override warning path, end to end through planning.slot."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = cls.env.ref(
            'restaurant_shift_planner.group_shift_planner_manager'
        )
        # res.users.groups_id was renamed to group_ids in Odoo 19.
        field = ('group_ids' if 'group_ids' in cls.env['res.users']._fields
                 else 'groups_id')
        cls.env.user.write({field: [(4, group.id)]})
        cls.keyholder = cls.env['restaurant.staff.attribute'].create({
            'name': 'Keyholder', 'code': 'slot_keyholder', 'value_type': 'flag',
        })
        cls.with_key = cls.env['hr.employee'].create({'name': 'Has Key'})
        cls.without_key = cls.env['hr.employee'].create({'name': 'No Key'})
        cls.env['restaurant.staff.attribute.value'].create({
            'employee_id': cls.with_key.id,
            'attribute_id': cls.keyholder.id,
            'value_bool': True,
            'valid_from': date(2026, 1, 1),
        })
        cls.start = datetime(2026, 9, 4, 16, 0)
        cls.stop = datetime(2026, 9, 4, 23, 0)

    def _slot(self, employee):
        return self.env['planning.slot'].create({
            'resource_id': employee.resource_id.id,
            'start_datetime': self.start,
            'end_datetime': self.stop,
        })

    def test_crew_rule_flags_a_shift_with_no_keyholder(self):
        self.env['restaurant.shift.requirement'].create({
            'attribute_id': self.keyholder.id, 'scope': 'team',
            'aggregate': 'count', 'operator': 'is_true', 'min_count': 1,
        })
        slot = self._slot(self.without_key)
        self.assertEqual(slot.planner_requirement_state, 'violation')
        self.assertIn('Keyholder', slot.planner_requirement_message)

    def test_overlapping_slot_satisfies_the_crew_rule(self):
        """A keyholder behind the bar covers the shift, not just their own slot."""
        self.env['restaurant.shift.requirement'].create({
            'attribute_id': self.keyholder.id, 'scope': 'team',
            'aggregate': 'count', 'operator': 'is_true', 'min_count': 1,
        })
        slot = self._slot(self.without_key)
        self._slot(self.with_key)
        slot.invalidate_recordset()
        self.assertEqual(slot.planner_requirement_state, 'ok')

    def test_no_requirements_means_no_check(self):
        slot = self._slot(self.without_key)
        self.assertEqual(slot.planner_requirement_state, 'na')

    def test_non_overlapping_slot_does_not_count(self):
        self.env['restaurant.shift.requirement'].create({
            'attribute_id': self.keyholder.id, 'scope': 'team',
            'aggregate': 'count', 'operator': 'is_true', 'min_count': 1,
        })
        slot = self._slot(self.without_key)
        self.env['planning.slot'].create({
            'resource_id': self.with_key.resource_id.id,
            'start_datetime': self.start + timedelta(days=1),
            'end_datetime': self.stop + timedelta(days=1),
        })
        slot.invalidate_recordset()
        self.assertEqual(slot.planner_requirement_state, 'violation')
