# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    shift_attribute_value_ids = fields.One2many(
        'restaurant.staff.attribute.value', 'employee_id',
        string='Shift Attributes',
    )
    shift_attribute_count = fields.Integer(compute='_compute_shift_attribute_info')
    shift_attribute_summary = fields.Char(
        compute='_compute_shift_attribute_info', string='Attributes',
    )
    shift_attribute_alert = fields.Char(
        compute='_compute_shift_attribute_info', string='Attribute Alerts',
    )

    @api.depends('shift_attribute_value_ids.status',
                 'shift_attribute_value_ids.display_value')
    def _compute_shift_attribute_info(self):
        for employee in self:
            current = employee.shift_attribute_value_ids.filtered(
                lambda v: v.status in ('current', 'expiring')
            )
            employee.shift_attribute_count = len(current)
            employee.shift_attribute_summary = ', '.join(
                '%s %s' % (v.attribute_id.name, v.display_value)
                for v in current[:6]
            )
            problems = []
            expiring = current.filtered(lambda v: v.status == 'expiring')
            expired = employee.shift_attribute_value_ids.filtered(
                lambda v: v.status == 'expired'
            )
            if expiring:
                problems.append(_('%d expiring soon') % len(expiring))
            if expired:
                problems.append(_('%d expired') % len(expired))
            due = current.filtered('review_due')
            if due:
                problems.append(_('%d due for review') % len(due))
            employee.shift_attribute_alert = ' · '.join(problems)

    def _shift_attribute_map(self, on_date):
        """{employee_id: {attribute_id: value_record}} in force on ``on_date``.

        One query for the whole recordset — the gap report evaluates hundreds
        of (slot, candidate) pairs and cannot afford a lookup each time.

        Because the query filters on the validity window, an expired
        certification is simply absent from the map. Callers never have to
        check expiry themselves.
        """
        result = {employee.id: {} for employee in self}
        if not self:
            return result
        values = self.env['restaurant.staff.attribute.value'].search(
            [
                ('employee_id', 'in', self.ids),
                ('valid_from', '<=', on_date),
                '|', ('valid_until', '=', False), ('valid_until', '>=', on_date),
            ],
            order='valid_from asc',
        )
        for value in values:
            # Ascending order means a later start date wins, which is what
            # supersedes an older value that was left open-ended.
            result[value.employee_id.id][value.attribute_id.id] = value
        return result

    def get_shift_attribute(self, code, on_date=None):
        """Convenience reader for one attribute by code. Returns a float."""
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        attribute = self.env['restaurant.staff.attribute'].search(
            [('code', '=', code)], limit=1,
        )
        if not attribute:
            return 0.0
        value = self._shift_attribute_map(on_date)[self.id].get(attribute.id)
        if not value:
            return 0.0
        if attribute.value_type in ('flag', 'certification'):
            return 1.0 if value.value_bool else 0.0
        return value.value_number

    def action_view_shift_attributes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s — shift attributes') % self.name,
            'res_model': 'restaurant.staff.attribute.value',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
