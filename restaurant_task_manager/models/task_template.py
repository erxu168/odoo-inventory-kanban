# -*- coding: utf-8 -*-
from odoo import models, fields, api


class TaskListTemplate(models.Model):
    """Reusable checklist template assigned to shifts."""
    _name = 'restaurant.task.list.template'
    _description = 'Task List Template'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    description = fields.Text()
    task_template_ids = fields.One2many(
        'restaurant.task.template', 'list_template_id', string='Tasks',
    )
    task_count = fields.Integer(compute='_compute_task_count')
    location_id = fields.Many2one(
        'hr.work.location', string='Location',
        help='Restrict to a specific location. Leave empty for all.',
    )
    checkout_policy = fields.Selection([
        ('warn', 'Show Warning'),
        ('block', 'Block Checkout'),
    ], default='warn', string='Checkout Policy')
    active = fields.Boolean(default=True)
    color = fields.Integer()

    @api.depends('task_template_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_template_ids)


class TaskTemplate(models.Model):
    """Individual task definition within a template."""
    _name = 'restaurant.task.template'
    _description = 'Task Template'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    description = fields.Html(string='Instructions')
    sequence = fields.Integer(default=10)
    list_template_id = fields.Many2one(
        'restaurant.task.list.template', required=True, ondelete='cascade',
    )
    has_deadline = fields.Boolean(default=False)
    relative_deadline_minutes = fields.Integer(
        string='Deadline (min after shift start)', default=60,
    )
    completion_type = fields.Selection([
        ('checkbox', 'Checkbox'),
        ('photo', 'Photo Required'),
    ], default='checkbox', required=True)
    subtask_template_ids = fields.One2many(
        'restaurant.subtask.template', 'task_template_id', string='Checklist',
    )
    subtask_count = fields.Integer(compute='_compute_subtask_count')
    active = fields.Boolean(default=True)

    @api.depends('subtask_template_ids')
    def _compute_subtask_count(self):
        for rec in self:
            rec.subtask_count = len(rec.subtask_template_ids)


class SubtaskTemplate(models.Model):
    """Checklist item within a task template."""
    _name = 'restaurant.subtask.template'
    _description = 'Subtask Template'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    task_template_id = fields.Many2one(
        'restaurant.task.template', required=True, ondelete='cascade',
    )
