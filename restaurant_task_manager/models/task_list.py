# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class TaskList(models.Model):
    """A shift task list assigned to one employee.
    Contains task items generated from a template."""
    _name = 'restaurant.task.list'
    _description = 'Shift Task List'
    _inherit = ['mail.thread']
    _order = 'shift_start desc'

    name = fields.Char(compute='_compute_name', store=True)
    template_id = fields.Many2one(
        'restaurant.task.list.template', required=True, tracking=True,
    )
    slot_id = fields.Many2one(
        'planning.slot', string='Planning Shift', ondelete='set null',
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, tracking=True,
    )
    location_id = fields.Many2one(
        'hr.work.location', string='Location', tracking=True,
    )
    shift_start = fields.Datetime(string='Shift Start')
    shift_end = fields.Datetime(string='Shift End')
    checkout_policy = fields.Selection(
        related='template_id.checkout_policy', readonly=True,
    )

    # ── Tasks ─────────────────────────────────────────────────
    task_item_ids = fields.One2many(
        'restaurant.task.item', 'task_list_id', string='Tasks',
    )
    total_tasks = fields.Integer(compute='_compute_completion', store=True)
    completed_tasks = fields.Integer(compute='_compute_completion', store=True)
    completion_score = fields.Float(
        string='Completion %', compute='_compute_completion',
        store=True, aggregator='avg',
    )

    # ── Sign-off ──────────────────────────────────────────────
    signature = fields.Binary(string='Employee Signature')

    # ── Status ────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('done', 'Completed'),
        ('expired', 'Expired'),
    ], default='draft', tracking=True)
    warning_sent = fields.Boolean(default=False)
    color = fields.Integer(compute='_compute_color')

    # ── Computed ──────────────────────────────────────────────

    @api.depends('employee_id', 'template_id', 'shift_start')
    def _compute_name(self):
        for rec in self:
            parts = []
            if rec.employee_id:
                parts.append(rec.employee_id.name)
            if rec.template_id:
                parts.append(rec.template_id.name)
            if rec.shift_start:
                parts.append(rec.shift_start.strftime('%Y-%m-%d'))
            rec.name = ' — '.join(parts) if parts else _('New Task List')

    @api.depends('task_item_ids.state')
    def _compute_completion(self):
        for rec in self:
            items = rec.task_item_ids
            rec.total_tasks = len(items)
            rec.completed_tasks = len(items.filtered(lambda i: i.state == 'done'))
            rec.completion_score = (
                (rec.completed_tasks / rec.total_tasks * 100)
                if rec.total_tasks else 0.0
            )

    def _compute_color(self):
        for rec in self:
            if rec.state == 'done':
                rec.color = 10  # green
            elif rec.state == 'expired':
                rec.color = 1   # red
            elif rec.state == 'active':
                rec.color = 2   # orange
            else:
                rec.color = 0   # grey

    # ── Actions ──────────────────────────────────────────────

    def action_generate_tasks(self):
        """Generate task items from the linked template."""
        for rec in self:
            if rec.task_item_ids:
                raise UserError(_('Tasks already generated. Reset first.'))
            for tt in rec.template_id.task_template_ids:
                deadline = False
                if tt.has_deadline and rec.shift_start:
                    deadline = rec.shift_start + timedelta(
                        minutes=tt.relative_deadline_minutes
                    )
                item = self.env['restaurant.task.item'].create({
                    'name': tt.name,
                    'description': tt.description,
                    'sequence': tt.sequence,
                    'task_list_id': rec.id,
                    'completion_type': tt.completion_type,
                    'has_deadline': tt.has_deadline,
                    'deadline': deadline,
                })
                for st in tt.subtask_template_ids:
                    self.env['restaurant.task.subtask'].create({
                        'name': st.name,
                        'sequence': st.sequence,
                        'task_item_id': item.id,
                    })
            rec.state = 'active'

    def action_sign_off(self):
        """Mark list as done — requires digital signature."""
        for rec in self:
            if not rec.signature:
                raise ValidationError(_(
                    'Please provide your digital signature before signing off.'
                ))
            incomplete = rec.task_item_ids.filtered(lambda i: i.state != 'done')
            if incomplete:
                raise ValidationError(_(
                    '%d task(s) still incomplete. Complete all tasks before signing off.',
                    len(incomplete),
                ))
            rec.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft', 'signature': False, 'warning_sent': False})
        self.task_item_ids.unlink()

    # ── Crons ─────────────────────────────────────────────────

    @api.model
    def _cron_check_overdue_tasks(self):
        """Check for overdue task items and log activities."""
        now = fields.Datetime.now()
        overdue_items = self.env['restaurant.task.item'].search([
            ('has_deadline', '=', True),
            ('state', '!=', 'done'),
            ('deadline', '<', now),
        ])
        for item in overdue_items:
            tl = item.task_list_id
            if tl.employee_id.user_id:
                tl.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=tl.employee_id.user_id.id,
                    note=_('Task "%s" is overdue!', item.name),
                )

    @api.model
    def _cron_escalation(self):
        """Run escalation chain for overdue tasks."""
        now = fields.Datetime.now()
        if 'restaurant.escalation.rule' not in self.env.registry:
            return

        rules = self.env['restaurant.escalation.rule'].search(
            [('active', '=', True)], order='level asc',
        )
        overdue_items = self.env['restaurant.task.item'].search([
            ('has_deadline', '=', True),
            ('state', '!=', 'done'),
            ('deadline', '<', now),
        ])

        template = self.env.ref(
            'restaurant_task_manager.mail_template_escalation',
            raise_if_not_found=False,
        )

        for item in overdue_items:
            minutes_overdue = (now - item.deadline).total_seconds() / 60
            for rule in rules:
                field_name = f'escalation_level_{rule.level}_sent'
                if field_name not in item._fields:
                    continue
                if item[field_name]:
                    continue
                if minutes_overdue < rule.delay_minutes:
                    continue

                recipient = rule._get_recipient(item)
                if not recipient:
                    continue

                if rule.send_email and template and recipient.work_email:
                    template.with_context(
                        escalation_level=rule.level,
                        escalation_recipient_email=recipient.work_email,
                        minutes_overdue=int(minutes_overdue),
                    ).send_mail(item.task_list_id.id, force_send=True,
                                email_values={'email_to': recipient.work_email})

                item.write({field_name: True})

                if recipient.user_id:
                    item.task_list_id.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=recipient.user_id.id,
                        note=_('ESCALATION Level %d: Task "%s" is overdue by %d minutes.',
                               rule.level, item.name, int(minutes_overdue)),
                    )
