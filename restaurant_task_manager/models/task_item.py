# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TaskItem(models.Model):
    """Individual task within a shift task list. Supports multiple
    completion types, sub-task checklists, and proof-of-work."""
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
    is_overdue = fields.Boolean(compute='_compute_is_overdue', search='_search_is_overdue')
    time_remaining = fields.Char(compute='_compute_time_remaining')

    # ── Completion Type ──────────────────────────────────────
    completion_type = fields.Selection([
        ('checkbox', 'Simple Checkbox'),
        ('photo', 'Photo (Camera)'),
        ('numeric', 'Numeric Value'),
        ('text', 'Text Note'),
        ('signature', 'Digital Signature'),
    ], default='checkbox', required=True)
    numeric_label = fields.Char(string='Value Label')
    numeric_min = fields.Float()
    numeric_max = fields.Float()
    require_proof_photo = fields.Boolean(string='Also Require Photo')

    # ── Proof / Completion Data ──────────────────────────────
    proof_photo = fields.Binary(string='Proof Photo', attachment=True)
    proof_photo_filename = fields.Char()
    proof_numeric_value = fields.Float(string='Recorded Value')
    proof_text_note = fields.Text(string='Completion Note')
    proof_signature = fields.Binary(string='Digital Signature')
    staff_comment = fields.Text(
        string='Staff Comment',
        help='Staff can leave comments visible to managers.',
    )

    # ── Pre-deadline Reminder ─────────────────────────────────
    reminder_minutes_before = fields.Integer(
        string='Reminder (min before)',
        default=0,
        help='Minutes before deadline to send a reminder. 0 = no reminder.',
    )
    pre_reminder_sent = fields.Boolean(default=False)

    # ── PDF Instructions ─────────────────────────────────────
    instruction_file = fields.Binary(string='Instructions (PDF)', attachment=True)
    instruction_filename = fields.Char()

    # ── Sub-tasks ────────────────────────────────────────────
    subtask_ids = fields.One2many(
        'restaurant.task.subtask', 'task_item_id', string='Checklist',
    )
    subtask_count = fields.Integer(compute='_compute_subtask_progress')
    subtask_done_count = fields.Integer(compute='_compute_subtask_progress')
    subtask_progress = fields.Float(
        string='Checklist %', compute='_compute_subtask_progress',
    )

    # ── Status ───────────────────────────────────────────────
    state = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], default='todo', tracking=True)
    completed_at = fields.Datetime(readonly=True)
    completed_on_time = fields.Boolean(compute='_compute_completed_on_time', store=True)
    reminder_sent = fields.Boolean(default=False)

    # ── Escalation Tracking ──────────────────────────────────
    escalation_level_1_sent = fields.Boolean(default=False)
    escalation_level_2_sent = fields.Boolean(default=False)
    escalation_level_3_sent = fields.Boolean(default=False)

    # ── Handoff Tracking ─────────────────────────────────────
    is_handoff = fields.Boolean(
        string='Handed Off',
        compute='_compute_is_handoff',
        search='_search_is_handoff',
    )

    # ── Computed Fields ──────────────────────────────────────

    def _compute_is_handoff(self):
        for rec in self:
            rec.is_handoff = rec.name.startswith('[HANDOFF]') if rec.name else False

    def _search_is_handoff(self, operator, value):
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('name', '=like', '[HANDOFF]%')]
        return [('name', 'not like', '[HANDOFF]%')]

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
                rec.has_deadline
                and rec.state != 'done'
                and rec.deadline
                and rec.deadline < now
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
                rec.completed_on_time = True  # No deadline = always on time
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
                rec.time_remaining = _('Overdue by %dh %02dm') % (h, m)
            else:
                diff = rec.deadline - now
                h, rem = divmod(int(diff.total_seconds()), 3600)
                m = rem // 60
                rec.time_remaining = _('%dh %02dm left') % (h, m)

    # ── Actions ──────────────────────────────────────────────

    def action_start(self):
        self.filtered(lambda r: r.state == 'todo').write({'state': 'in_progress'})

    def action_complete(self):
        """Mark task as done with validation based on completion type."""
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
            'proof_numeric_value': 0,
            'proof_text_note': False,
            'proof_signature': False,
            'reminder_sent': False,
            'pre_reminder_sent': False,
        })
        self.subtask_ids.write({'is_done': False})

    def _validate_completion(self):
        """Ensure required proof is provided based on completion type."""
        self.ensure_one()
        if self.completion_type == 'photo' and not self.proof_photo:
            raise ValidationError(_(
                'Task "%s" requires a photo. Please upload a proof photo.', self.name
            ))
        if self.completion_type == 'numeric':
            # Validate value is within configured range.
            # numeric_min defaults to 0.0 — always enforced (rejects negatives).
            # numeric_max defaults to 0.0 — only enforced when explicitly set > 0.
            if self.proof_numeric_value < self.numeric_min:
                raise ValidationError(_(
                    'Value %.1f is below minimum %.1f for task "%s".',
                    self.proof_numeric_value, self.numeric_min, self.name,
                ))
            if self.numeric_max and self.proof_numeric_value > self.numeric_max:
                raise ValidationError(_(
                    'Value %.1f is above maximum %.1f for task "%s".',
                    self.proof_numeric_value, self.numeric_max, self.name,
                ))
        if self.completion_type == 'text' and not self.proof_text_note:
            raise ValidationError(_(
                'Task "%s" requires a text note.', self.name
            ))
        if self.completion_type == 'signature' and not self.proof_signature:
            raise ValidationError(_(
                'Task "%s" requires a digital signature.', self.name
            ))
        if self.require_proof_photo and not self.proof_photo:
            raise ValidationError(_(
                'Task "%s" also requires a photo.', self.name
            ))
        # Validate all sub-tasks are checked
        if self.subtask_ids and not all(s.is_done for s in self.subtask_ids):
            raise ValidationError(_(
                'All checklist items must be completed for task "%s".', self.name
            ))
