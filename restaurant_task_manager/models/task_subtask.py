# -*- coding: utf-8 -*-
from odoo import models, fields


class TaskSubtask(models.Model):
    """Checklist item within a concrete task."""
    _name = 'restaurant.task.subtask'
    _description = 'Task Subtask'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    is_done = fields.Boolean(default=False)
    task_item_id = fields.Many2one(
        'restaurant.task.item', required=True, ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee', related='task_item_id.employee_id',
        store=True, readonly=True,
    )
