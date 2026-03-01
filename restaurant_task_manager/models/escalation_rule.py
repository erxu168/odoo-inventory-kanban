# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class EscalationRule(models.Model):
    """Defines a level in the escalation chain.
    e.g. Level 1 = employee (0 min), Level 2 = shift lead (+15 min),
         Level 3 = area manager (+30 min)."""
    _name = 'restaurant.escalation.rule'
    _description = 'Task Escalation Rule'
    _order = 'level asc'

    name = fields.Char(compute='_compute_name', store=True)
    level = fields.Integer(
        string='Escalation Level', required=True, default=1,
        help='1 = first contact, 2 = second, 3 = third.',
    )
    delay_minutes = fields.Integer(
        string='Delay After Overdue (min)', required=True, default=0,
        help='Minutes after task becomes overdue to trigger this escalation.',
    )
    recipient_type = fields.Selection([
        ('employee', 'Assigned Employee'),
        ('department_manager', 'Department Manager'),
        ('parent_manager', "Employee's Manager"),
        ('specific_employee', 'Specific Employee'),
    ], string='Notify', required=True, default='employee')
    specific_employee_id = fields.Many2one(
        'hr.employee',
        string='Specific Employee',
        help='Only used when recipient type is "Specific Employee".',
    )
    location_id = fields.Many2one(
        'hr.work.location',
        string='Location',
        help='Limit this rule to a specific location. Leave empty for all.',
    )
    send_email = fields.Boolean(string='Send Email', default=True)
    send_sms = fields.Boolean(string='Send SMS', default=False)
    active = fields.Boolean(default=True)

    @api.depends('level', 'delay_minutes', 'recipient_type')
    def _compute_name(self):
        labels = dict(self._fields['recipient_type'].selection)
        for rec in self:
            rec.name = _('Level %d — %s (+%d min)') % (
                rec.level,
                labels.get(rec.recipient_type, ''),
                rec.delay_minutes,
            )

    def _get_recipient(self, task_item):
        """Return the hr.employee record to notify for the given task item."""
        self.ensure_one()
        employee = task_item.task_list_id.employee_id
        if self.recipient_type == 'employee':
            return employee
        elif self.recipient_type == 'department_manager':
            return employee.department_id.manager_id if employee.department_id else False
        elif self.recipient_type == 'parent_manager':
            return employee.parent_id or False
        elif self.recipient_type == 'specific_employee':
            return self.specific_employee_id
        return False
