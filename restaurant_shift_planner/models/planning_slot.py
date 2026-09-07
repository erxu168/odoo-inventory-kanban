# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    planner_requirement_state = fields.Selection([
        ('na', 'No requirements'),
        ('ok', 'Requirements met'),
        ('warning', 'Preferred not met'),
        ('violation', 'Requirement not met'),
    ], compute='_compute_planner_requirements', string='Requirement Check')
    planner_requirement_message = fields.Text(
        compute='_compute_planner_requirements', string='Requirement Notes',
    )

    # ── Shift shape ──────────────────────────────────────────
    #
    # Odoo Planning stores one slot per person, so "the crew" is every slot
    # whose time window overlaps this one. Team requirements ("one keyholder
    # on shift") span roles and templates, which is why the crew is built
    # from overlap rather than from a shared template.

    def _planner_employee(self):
        """The person on this slot, or an empty recordset.

        Planning exposes ``employee_id`` on the slot; the search is a fallback
        so a rename upstream degrades to a slower path instead of a traceback.
        """
        self.ensure_one()
        if 'employee_id' in self._fields:
            return self.employee_id
        if not self.resource_id:
            return self.env['hr.employee']
        return self.env['hr.employee'].search(
            [('resource_id', '=', self.resource_id.id)], limit=1,
        )

    def _planner_local_date(self):
        self.ensure_one()
        if not self.start_datetime:
            return fields.Date.context_today(self)
        return fields.Datetime.context_timestamp(self, self.start_datetime).date()

    @api.model
    def _planner_overlapping(self, slots):
        """Every staffed slot overlapping any slot in ``slots``, in one query."""
        dated = slots.filtered(lambda s: s.start_datetime and s.end_datetime)
        if not dated:
            return self.browse()
        return self.search([
            ('company_id', 'in', dated.company_id.ids or [False]),
            ('resource_id', '!=', False),
            ('start_datetime', '<', max(dated.mapped('end_datetime'))),
            ('end_datetime', '>', min(dated.mapped('start_datetime'))),
        ])

    def _planner_crew_slots(self, pool=None):
        """The slots making up this shift, including this one."""
        self.ensure_one()
        if not (self.start_datetime and self.end_datetime):
            return self.browse()
        pool = pool if pool is not None else self._planner_overlapping(self)
        crew = pool.filtered(
            lambda s: s.company_id == self.company_id
            and s.start_datetime < self.end_datetime
            and s.end_datetime > self.start_datetime
        )
        return crew | self.filtered(lambda s: s.resource_id)

    # ── Evaluation ───────────────────────────────────────────

    def _planner_evaluate(self, pool=None):
        """Check this slot's whole shift via the shared matching routine."""
        self.ensure_one()
        Requirement = self.env['restaurant.shift.requirement']
        crew_slots = self._planner_crew_slots(pool=pool)
        if not crew_slots:
            return 'na', []
        requirements = Requirement._for_templates(crew_slots.template_id)
        members = [
            (slot._planner_employee(), slot.template_id, slot.role_id)
            for slot in crew_slots
        ]
        return Requirement._evaluate(
            requirements, members, self._planner_local_date(),
        )

    @api.depends('resource_id', 'template_id', 'role_id',
                 'start_datetime', 'end_datetime')
    def _compute_planner_requirements(self):
        # Requirement messages name other people's certificates and levels,
        # so only shift planners see them; everyone else gets a plain slot.
        if not self.env.user.has_group(
                'restaurant_shift_planner.group_shift_planner_manager'):
            for slot in self:
                slot.planner_requirement_state = 'na'
                slot.planner_requirement_message = False
            return

        # A mismatch against a future Planning release must not take the
        # Planning app down with it, so this degrades to "no check" and logs.
        try:
            pool = self._planner_overlapping(self.sudo())
        except Exception:
            _logger.warning('Shift requirement check skipped', exc_info=True)
            for slot in self:
                slot.planner_requirement_state = 'na'
                slot.planner_requirement_message = False
            return

        for slot in self:
            try:
                state, failures = slot.sudo()._planner_evaluate(pool=pool)
            except Exception:
                _logger.warning(
                    'Shift requirement check failed for slot %s', slot.id,
                    exc_info=True,
                )
                state, failures = 'na', []
            slot.planner_requirement_state = state
            slot.planner_requirement_message = '\n'.join(
                ('%s %s' % ('✖' if r.enforcement == 'hard' else '⚠', m))
                for r, _employee, m in failures
            ) or False

    def action_planner_explain(self):
        """Show the full requirement picture for this shift."""
        self.ensure_one()
        state, failures = self.sudo()._planner_evaluate()
        if state == 'na':
            body = _('No requirements apply to this shift.')
        elif not failures:
            body = _('Every requirement for this shift is met.')
        else:
            body = '\n'.join('• %s' % m for _r, _e, m in failures)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shift requirements'),
                'message': body,
                'type': 'success' if state in ('na', 'ok') else 'warning',
                'sticky': state == 'violation',
            },
        }
