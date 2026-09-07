# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _


class ShiftGapReport(models.TransientModel):
    """Which shifts in a date range cannot be staffed to their requirements.

    Run before the roster goes out. Turning "nobody qualified is free on
    Saturday" into a Tuesday phone call is most of the value of writing
    requirements down in the first place — it does not need the scheduler.
    """
    _name = 'restaurant.shift.gap.report'
    _description = 'Shift Coverage Gap Report'

    date_from = fields.Date(
        required=True, default=lambda self: fields.Date.context_today(self),
    )
    date_to = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=28),
    )
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
    )
    thin_threshold = fields.Integer(
        default=1, string='Flag When Candidates ≤',
        help='An open shift with this many qualified, available people is '
             'reported as fragile even though it can technically be filled.',
    )
    include_soft = fields.Boolean(
        default=True, string='Include Preferred Requirements',
    )
    line_ids = fields.One2many('restaurant.shift.gap.line', 'report_id')

    # ── Helpers ──────────────────────────────────────────────

    def _leave_windows(self, employees):
        """[(employee_id, start_date, end_date)] for approved time off."""
        if 'hr.leave' not in self.env or not employees:
            return []
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', fields.Datetime.to_datetime(self.date_to)),
            ('date_to', '>=', fields.Datetime.to_datetime(self.date_from)),
        ])
        return [
            (leave.employee_id.id, leave.date_from.date(), leave.date_to.date())
            for leave in leaves if leave.date_from and leave.date_to
        ]

    @staticmethod
    def _available_on(leave_windows, employee_id, on_date):
        return not any(
            emp == employee_id and start <= on_date <= end
            for emp, start, end in leave_windows
        )

    def _role_pool(self, employees, role):
        """Employees who hold ``role``, if Planning tracks roles on employees."""
        if not role or 'planning_role_ids' not in self.env['hr.employee']._fields:
            return employees
        return employees.filtered(lambda e: role in e.planning_role_ids)

    # ── Run ──────────────────────────────────────────────────

    def action_run(self):
        self.ensure_one()
        self.line_ids.unlink()

        Slot = self.env['planning.slot']
        slots = Slot.search([
            ('company_id', '=', self.company_id.id),
            ('start_datetime', '>=', fields.Datetime.to_datetime(self.date_from)),
            ('start_datetime', '<=', fields.Datetime.to_datetime(self.date_to)
                                     + timedelta(days=1)),
        ], order='start_datetime')

        employees = self.env['hr.employee'].search([
            ('company_id', '=', self.company_id.id),
        ])
        leave_windows = self._leave_windows(employees)

        lines = []
        seen_crews = set()
        # One attribute lookup per distinct shift date, not per slot.
        values_by_date = {}

        for slot in slots:
            on_date = slot._planner_local_date()
            values = self._values_on(values_by_date, employees, on_date)

            if slot.resource_id:
                crew_slots = slot._planner_crew_slots()
                key = tuple(sorted(crew_slots.ids))
                if not key or key in seen_crews:
                    continue
                seen_crews.add(key)
                lines += self._check_shift(crew_slots, on_date, values)
            else:
                lines += self._check_open(
                    slot, on_date, employees, leave_windows, values,
                )

        self.env['restaurant.shift.gap.line'].create([
            dict(line, report_id=self.id) for line in lines
        ])
        return self._reopen()

    def _values_on(self, cache, employees, on_date):
        if on_date not in cache:
            cache[on_date] = employees._shift_attribute_map(on_date)
        return cache[on_date]

    def _check_shift(self, crew_slots, on_date, values):
        """Everyone already rostered on one shift, per-person and per-crew."""
        Requirement = self.env['restaurant.shift.requirement']
        requirements = Requirement._for_templates(crew_slots.template_id)
        if not self.include_soft:
            requirements = requirements.filtered(
                lambda r: r.enforcement == 'hard'
            )
        members = [
            (slot._planner_employee(), slot.template_id, slot.role_id)
            for slot in crew_slots
        ]
        _state, failures = Requirement._evaluate(
            requirements, members, on_date, values=values,
        )
        anchor = crew_slots[0]
        return [{
            'slot_id': anchor.id,
            'shift_date': on_date,
            'issue': ('assigned_unqualified' if requirement.scope == 'each'
                      else 'crew_shortfall'),
            'severity': requirement.enforcement,
            'requirement_id': requirement.id,
            'employee_id': employee.id if employee else False,
            'message': message,
        } for requirement, employee, message in failures]

    def _check_open(self, slot, on_date, employees, leave_windows, values):
        """An unfilled slot: is there anyone who could actually take it?"""
        Requirement = self.env['restaurant.shift.requirement']
        requirements = Requirement._for_templates(slot.template_id)
        pool = self._role_pool(employees, slot.role_id)
        pool = pool.filtered(
            lambda e: self._available_on(leave_windows, e.id, on_date)
        )
        candidates = Requirement._candidates(
            requirements, pool, on_date, role=slot.role_id, values=values,
        )
        if len(candidates) > self.thin_threshold:
            return []
        if not candidates:
            message = _(
                'Nobody qualifies: %(pool)d in the role, none meet the '
                'requirements for this shift.', pool=len(pool),
            )
            issue = 'open_no_candidate'
        else:
            message = _(
                'Only %(count)d qualified and free: %(names)s.',
                count=len(candidates),
                names=', '.join(candidates.mapped('name')),
            )
            issue = 'open_thin'
        return [{
            'slot_id': slot.id,
            'shift_date': on_date,
            'issue': issue,
            'severity': 'hard' if issue == 'open_no_candidate' else 'soft',
            'candidate_count': len(candidates),
            'message': message,
        }]

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Coverage Gaps'),
            'res_model': 'restaurant.shift.gap.report',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ShiftGapLine(models.TransientModel):
    _name = 'restaurant.shift.gap.line'
    _description = 'Shift Coverage Gap'
    _order = 'shift_date, severity, id'

    report_id = fields.Many2one(
        'restaurant.shift.gap.report', ondelete='cascade', required=True,
    )
    slot_id = fields.Many2one('planning.slot', string='Shift')
    shift_date = fields.Date()
    role_id = fields.Many2one(related='slot_id.role_id', string='Role')
    issue = fields.Selection([
        ('open_no_candidate', 'Nobody qualifies'),
        ('open_thin', 'Only just coverable'),
        ('assigned_unqualified', 'Assigned person falls short'),
        ('crew_shortfall', 'Crew rule not met'),
    ], required=True)
    severity = fields.Selection([
        ('hard', 'Blocking'),
        ('soft', 'Preferred'),
    ], default='hard')
    requirement_id = fields.Many2one('restaurant.shift.requirement')
    employee_id = fields.Many2one('hr.employee')
    candidate_count = fields.Integer()
    message = fields.Char()

    def action_open_slot(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'planning.slot',
            'res_id': self.slot_id.id,
            'view_mode': 'form',
        }
