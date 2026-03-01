# -*- coding: utf-8 -*-
from odoo import models, fields, api


class TaskListTemplate(models.Model):
    """A named collection of task templates assigned to shifts via planning roles.
    Examples: 'Opening Shift Tasks', 'Closing Shift Tasks', 'Kitchen Prep'."""
    _name = 'restaurant.task.list.template'
    _description = 'Task List Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Template Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    task_template_ids = fields.One2many(
        'restaurant.task.template',
        'task_list_template_id',
        string='Tasks',
    )
    task_count = fields.Integer(compute='_compute_task_count')
    role_ids = fields.Many2many(
        'planning.role',
        string='Planning Roles',
        help='Shifts with these roles will auto-receive this task list.',
    )
    location_id = fields.Many2one(
        'hr.work.location',
        string='Work Location',
        help='Restrict this template to a specific location. Leave empty for all.',
    )
    checkout_policy = fields.Selection([
        ('warn', 'Show Warning (allow checkout)'),
        ('block', 'Block Checkout'),
    ], string='Checkout Policy', default='warn',
        help='What happens when an employee tries to check out with incomplete tasks.',
    )
    active = fields.Boolean(default=True)
    color = fields.Integer()

    @api.depends('task_template_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_template_ids)


class TaskTemplate(models.Model):
    """Individual task definition within a template. Supports multiple
    completion types and nested sub-task checklists."""
    _name = 'restaurant.task.template'
    _description = 'Task Template'
    _order = 'sequence, id'

    name = fields.Char(string='Task Name', required=True)
    description = fields.Html(string='Description / Instructions')
    sequence = fields.Integer(default=10)
    task_list_template_id = fields.Many2one(
        'restaurant.task.list.template',
        string='Task List Template',
        ondelete='cascade',
        required=True,
    )
    # Deadline
    has_deadline = fields.Boolean(string='Has Deadline', default=False)
    relative_deadline_minutes = fields.Integer(
        string='Deadline (min after shift start)',
        default=60,
        help='Minutes after shift start by which this task must be completed.',
    )
    # Pre-deadline reminder
    reminder_minutes_before = fields.Integer(
        string='Reminder (min before deadline)',
        default=0,
        help='Send a reminder this many minutes before the deadline. 0 = no reminder.',
    )
    # Completion type
    completion_type = fields.Selection([
        ('checkbox', 'Simple Checkbox'),
        ('photo', 'Photo (Camera)'),
        ('numeric', 'Numeric Value'),
        ('text', 'Text Note'),
        ('signature', 'Digital Signature'),
    ], string='Completion Type', default='checkbox', required=True,
        help='What type of proof is required to mark this task complete.',
    )
    numeric_label = fields.Char(
        string='Value Label',
        help='Label for numeric field, e.g. "Temperature (°C)", "Count".',
    )
    numeric_min = fields.Float(string='Min Value')
    numeric_max = fields.Float(string='Max Value')
    require_proof_photo = fields.Boolean(
        string='Also Require Photo',
        help='Require a photo in addition to the primary completion type.',
    )
    # PDF instructions
    instruction_file = fields.Binary(string='Instructions (PDF)', attachment=True)
    instruction_filename = fields.Char()
    # Sub-tasks
    subtask_template_ids = fields.One2many(
        'restaurant.subtask.template',
        'task_template_id',
        string='Checklist Items',
    )
    subtask_count = fields.Integer(compute='_compute_subtask_count')
    active = fields.Boolean(default=True)

    @api.depends('subtask_template_ids')
    def _compute_subtask_count(self):
        for rec in self:
            rec.subtask_count = len(rec.subtask_template_ids)


class SubtaskTemplate(models.Model):
    """Checklist item within a task template. For example, 'Clean Kitchen'
    might have sub-items: wipe counters, mop floors, empty grease trap."""
    _name = 'restaurant.subtask.template'
    _description = 'Sub-Task Template'
    _order = 'sequence, id'

    name = fields.Char(string='Checklist Item', required=True)
    sequence = fields.Integer(default=10)
    task_template_id = fields.Many2one(
        'restaurant.task.template',
        string='Parent Task',
        ondelete='cascade',
        required=True,
    )
