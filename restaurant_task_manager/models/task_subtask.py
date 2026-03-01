# -*- coding: utf-8 -*-
from odoo import models, fields


class TaskSubtask(models.Model):
    """A checklist item within a task. E.g. 'Clean Kitchen' → wipe counters,
    mop floors, empty grease trap. All must be checked before task completion."""
    _name = 'restaurant.task.subtask'
    _description = 'Task Checklist Item'
    _order = 'sequence, id'

    name = fields.Char(string='Checklist Item', required=True)
    sequence = fields.Integer(default=10)
    is_done = fields.Boolean(string='Done', default=False)
    task_item_id = fields.Many2one(
        'restaurant.task.item',
        string='Parent Task',
        ondelete='cascade',
        required=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        related='task_item_id.employee_id',
        store=True,
        readonly=True,
    )
