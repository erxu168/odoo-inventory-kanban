# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TaskItem(models.Model):
    """Individual task within a shift task list.
    Supports checkbox or photo completion, plus subtask checklists."""
    _name = 'restaurant.task.item'
    _description = 'Task Item'
    _order = 'sequence, deadline, id'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    description = fields.Html(string='Instructions')
    sequence = fields.Integer(default=10)
    task_list_id = fields.Many2one(
        'restaurant.task.list', required=True, ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee', related='task_list_id.employee_id',
        store=True, readonly=True,
    )
    location_id = fields.Many2one(
        'hr.work.location', related='task_list_id.location_id',
        store=True, readonly=True,
    )

    # ── Deadline ─────────────────────────────────────────────
    has_deadline = fields.Boolean(default=False)
    deadline = fields.Datetime(tracking=True)
    is_overdue = fields.Boolean(
        compute='_compute_is_overdue', search='_search_is_overdue',
    )
    time_remaining = fields.Char(compute='_compute_time_remaining')

    # ── Completion ────────────────────────────────────────────
    completion_type = fields.Selection([
        ('checkbox', 'Checkbox'),
        ('photo', 'Photo Required'),
    ], default='checkbox', required=True)

    proof_photo = fields.Binary(string='Proof Photo', attachment=True)
    proof_photo_filename = fields.Char()
    staff_comment = fields.Text(string='Staff Comment')

    # ── Sub-tasks ─────────────────────────────────────────────
    subtask_ids = fields.One2many(
        'restaurant.task.subtask', 'task_item_id', string='Checklist',
    )
    subtask_count = fields.Integer(compute='_compute_subtask_progress')
    subtask_done_count = fields.Integer(compute='_compute_subtask_progress')
    subtask_progress = fields.Float(
        string='Checklist %', compute='_compute_subtask_progress',
    )

    # ── Status ────────────────────────────────────────────────
    state = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], default='todo', tracking=True)
    completed_at = fields.Datetime(readonly=True)
    completed_on_time = fields.Boolean(
        compute='_compute_completed_on_time', store=True,
    )

    # ── Escalation Tracking ──────────────────────────────────
    escalation_level_1_sent = fields.Boolean(default=False)
    escalation_level_2_sent = fields.Boolean(default=False)
    escalation_level_3_sent = fields.Boolean(default=False)

    # ── Computed Fields ──────────────────────────────────────

    @api.depends('subtask_ids.is_done')
    def _compute_subtask_progress(self):
        for rec in self:
            subs = rec.subtask_ids
            rec.subtask_count = len(subs)
            rec.subtask_done_count = len(subs.filtered('is_done'))
            rec.subtask_progress = (
                (rec.subtask_done_count / rec.subtask_count * 100)
                if rec.subtask_count else 0.0
            )

    @api.depends('deadline', 'has_deadline', 'state')
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_overdue = (
                rec.has_deadline and rec.state != 'done'
                and rec.deadline and rec.deadline < now
            )

    def _search_is_overdue(self, operator, value):
        now = fields.Datetime.now()
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [
                ('has_deadline', '=', True),
                ('state', '!=', 'done'),
                ('deadline', '<', now),
            ]
        return ['|', ('has_deadline', '=', False), '|',
                ('state', '=', 'done'), ('deadline', '>=', now)]

    @api.depends('completed_at', 'deadline', 'has_deadline')
    def _compute_completed_on_time(self):
        for rec in self:
            if rec.completed_at and rec.has_deadline and rec.deadline:
                rec.completed_on_time = rec.completed_at <= rec.deadline
            elif rec.completed_at and not rec.has_deadline:
                rec.completed_on_time = True
            else:
                rec.completed_on_time = False

    @api.depends('deadline', 'state', 'has_deadline')
    def _compute_time_remaining(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state == 'done':
                rec.time_remaining = _('Completed')
            elif not rec.has_deadline or not rec.deadline:
                rec.time_remaining = _('No deadline')
            elif rec.deadline < now:
                diff = now - rec.deadline
                h, rem = divmod(int(diff.total_seconds()), 3600)
                m = rem // 60
                rec.time_remaining = _('Overdue %dh %02dm') % (h, m)
            else:
                diff = rec.deadline - now
                h, rem = divmod(int(diff.total_seconds()), 3600)
                m = rem // 60
                rec.time_remaining = _('%dh %02dm left') % (h, m)

    # ── Actions ──────────────────────────────────────────────

    def action_start(self):
        self.filtered(lambda r: r.state == 'todo').write({'state': 'in_progress'})

    def action_complete(self):
        now = fields.Datetime.now()
        for rec in self:
            rec._validate_completion()
            rec.write({'state': 'done', 'completed_at': now})
            # Auto-complete parent list if all tasks done
            tl = rec.task_list_id
            if all(i.state == 'done' for i in tl.task_item_ids):
                tl.state = 'done'

    def action_reset(self):
        self.write({
            'state': 'todo',
            'completed_at': False,
            'proof_photo': False,
            'proof_photo_filename': False,
        })
        self.subtask_ids.write({'is_done': False})

    def _validate_completion(self):
        """Ensure required proof is provided."""
        self.ensure_one()
        if self.completion_type == 'photo' and not self.proof_photo:
            raise ValidationError(_(
                'Task "%s" requires a photo.', self.name
            ))
        if self.subtask_ids and not all(s.is_done for s in self.subtask_ids):
            raise ValidationError(_(
                'All checklist items must be completed for task "%s".', self.name
            ))
