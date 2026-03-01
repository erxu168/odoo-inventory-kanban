# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class TaskList(models.Model):
    """A concrete task list linked to a specific planning slot (shift).
    Each employee on a shift gets their own individual task list."""
    _name = 'restaurant.task.list'
    _description = 'Shift Task List'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'shift_start desc'

    name = fields.Char(compute='_compute_name', store=True)
    template_id = fields.Many2one(
        'restaurant.task.list.template',
        string='Template',
        required=True,
        tracking=True,
    )
    slot_id = fields.Many2one(
        'planning.slot',
        string='Planning Shift',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Assigned Employee',
        related='slot_id.employee_id',
        store=True,
        readonly=True,
    )
    employee_work_email = fields.Char(related='employee_id.work_email', readonly=True)
    employee_work_phone = fields.Char(related='employee_id.work_phone', readonly=True)
    location_id = fields.Many2one(
        'hr.work.location',
        string='Location',
        related='slot_id.work_location_id',
        store=True,
        readonly=True,
    )
    shift_start = fields.Datetime(
        related='slot_id.start_datetime', store=True, readonly=True,
    )
    shift_end = fields.Datetime(
        related='slot_id.end_datetime', store=True, readonly=True,
    )
    checkout_policy = fields.Selection(
        related='template_id.checkout_policy', readonly=True, store=True,
    )
    # Task items
    task_item_ids = fields.One2many('restaurant.task.item', 'task_list_id', string='Tasks')
    # Scoring
    total_tasks = fields.Integer(compute='_compute_completion', store=True)
    completed_tasks = fields.Integer(compute='_compute_completion', store=True)
    completion_score = fields.Float(
        string='Completion %',
        compute='_compute_completion',
        store=True,
        group_operator='avg',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('done', 'Completed'),
        ('expired', 'Expired'),
    ], default='draft', tracking=True)
    warning_sent = fields.Boolean(default=False)
    color = fields.Integer(compute='_compute_color')

    @api.depends('template_id.name', 'employee_id.name', 'shift_start')
    def _compute_name(self):
        for rec in self:
            parts = filter(None, [
                rec.template_id.name if rec.template_id else '',
                rec.employee_id.name if rec.employee_id else '',
                fields.Datetime.context_timestamp(
                    rec, rec.shift_start
                ).strftime('%Y-%m-%d %H:%M') if rec.shift_start else '',
            ])
            rec.name = ' — '.join(parts) or _('New Task List')

    @api.depends('task_item_ids.state')
    def _compute_completion(self):
        for rec in self:
            items = rec.task_item_ids
            rec.total_tasks = len(items)
            rec.completed_tasks = len(items.filtered(lambda t: t.state == 'done'))
            rec.completion_score = (
                (rec.completed_tasks / rec.total_tasks * 100)
                if rec.total_tasks else 0.0
            )

    @api.depends('completion_score', 'state')
    def _compute_color(self):
        for rec in self:
            if rec.state == 'done':
                rec.color = 10  # green
            elif rec.completion_score >= 75:
                rec.color = 4
            elif rec.completion_score >= 50:
                rec.color = 3
            elif rec.completion_score > 0:
                rec.color = 2
            else:
                rec.color = 1

    # ── Actions ──────────────────────────────────────────────

    def action_generate_tasks(self):
        """Create task items (and sub-items) from the linked template."""
        TaskItem = self.env['restaurant.task.item']
        Subtask = self.env['restaurant.task.subtask']
        for rec in self:
            if rec.task_item_ids:
                raise UserError(_(
                    'Tasks already exist for this list. Delete them first.'
                ))
            if not rec.template_id.task_template_ids:
                raise UserError(_(
                    'Template "%s" has no tasks defined.', rec.template_id.name
                ))
            for tmpl in rec.template_id.task_template_ids:
                # Compute deadline
                deadline = False
                if tmpl.has_deadline and tmpl.relative_deadline_minutes and rec.shift_start:
                    deadline = rec.shift_start + timedelta(
                        minutes=tmpl.relative_deadline_minutes
                    )
                    if rec.shift_end and deadline > rec.shift_end:
                        deadline = rec.shift_end

                item = TaskItem.create({
                    'task_list_id': rec.id,
                    'name': tmpl.name,
                    'description': tmpl.description,
                    'sequence': tmpl.sequence,
                    'has_deadline': tmpl.has_deadline,
                    'deadline': deadline,
                    'completion_type': tmpl.completion_type,
                    'numeric_label': tmpl.numeric_label,
                    'numeric_min': tmpl.numeric_min,
                    'numeric_max': tmpl.numeric_max,
                    'require_proof_photo': tmpl.require_proof_photo,
                    'instruction_file': tmpl.instruction_file,
                    'instruction_filename': tmpl.instruction_filename,
                    'reminder_minutes_before': tmpl.reminder_minutes_before,
                })
                # Create sub-tasks
                for st in tmpl.subtask_template_ids:
                    Subtask.create({
                        'task_item_id': item.id,
                        'name': st.name,
                        'sequence': st.sequence,
                    })
            rec.state = 'active'

    def action_mark_done(self):
        self.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    # ── Cron Jobs ────────────────────────────────────────────

    @api.model
    def _cron_check_overdue_tasks(self):
        """Notify employees and managers about overdue tasks."""
        now = fields.Datetime.now()
        overdue_items = self.env['restaurant.task.item'].search([
            ('has_deadline', '=', True),
            ('state', '!=', 'done'),
            ('deadline', '<', now),
            ('reminder_sent', '=', False),
            ('task_list_id.state', '=', 'active'),
        ])
        for item in overdue_items:
            item.reminder_sent = True
            user = item.task_list_id.employee_id.user_id
            if user:
                item.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary=_('OVERDUE: %s') % item.name,
                    note=_(
                        'Task "%s" was due at %s and is not completed.',
                        item.name,
                        fields.Datetime.context_timestamp(
                            item, item.deadline
                        ).strftime('%H:%M'),
                    ),
                )
        _logger.info('Checked %d overdue task items.', len(overdue_items))

    @api.model
    def _cron_send_warning_emails(self):
        """Send warning emails after shift ends with incomplete tasks."""
        now = fields.Datetime.now()
        incomplete = self.search([
            ('state', '=', 'active'),
            ('shift_end', '<', now),
            ('completion_score', '<', 100),
            ('warning_sent', '=', False),
        ])
        template = self.env.ref(
            'restaurant_task_manager.mail_template_task_warning',
            raise_if_not_found=False,
        )
        for tl in incomplete:
            if template and tl.employee_id.work_email:
                template.send_mail(tl.id, force_send=True)
                tl.write({'warning_sent': True})
            tl.write({'state': 'expired'})
        _logger.info('Processed %d incomplete task lists.', len(incomplete))

    @api.model
    def _cron_auto_generate_from_slots(self):
        """Auto-generate task lists for published slots in the next 7 days."""
        now = fields.Datetime.now()
        future = now + timedelta(days=7)
        slots = self.env['planning.slot'].search([
            ('start_datetime', '>=', now),
            ('start_datetime', '<=', future),
            ('employee_id', '!=', False),
            ('state', '=', 'published'),
        ])
        templates = self.env['restaurant.task.list.template'].search([
            ('role_ids', '!=', False),
            ('active', '=', True),
        ])
        created = 0
        for slot in slots:
            if self.search_count([('slot_id', '=', slot.id)]):
                continue
            matching = templates.filtered(
                lambda t: slot.role_id in t.role_ids and (
                    not t.location_id or t.location_id == slot.work_location_id
                )
            )
            for tmpl in matching:
                tl = self.create({
                    'template_id': tmpl.id,
                    'slot_id': slot.id,
                })
                tl.action_generate_tasks()
                created += 1
        _logger.info('Auto-generated %d task lists from published slots.', created)

    @api.model
    def _cron_pre_deadline_reminders(self):
        """Send pre-deadline reminders (X min before) via activity + email + SMS."""
        now = fields.Datetime.now()
        # Find items with reminder configured, deadline approaching, not yet reminded
        items = self.env['restaurant.task.item'].search([
            ('has_deadline', '=', True),
            ('state', '!=', 'done'),
            ('deadline', '!=', False),
            ('reminder_minutes_before', '>', 0),
            ('pre_reminder_sent', '=', False),
            ('task_list_id.state', '=', 'active'),
        ])
        reminded = 0
        for item in items:
            trigger_time = item.deadline - timedelta(minutes=item.reminder_minutes_before)
            if now >= trigger_time:
                item.pre_reminder_sent = True
                reminded += 1
                employee = item.task_list_id.employee_id
                user = employee.user_id
                mins = item.reminder_minutes_before
                # Odoo activity notification
                if user:
                    item.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=user.id,
                        summary=_('⏰ REMINDER: %s — due in %d min') % (item.name, mins),
                        note=_(
                            'Task "%s" is due at %s. You have %d minutes remaining.',
                            item.name,
                            fields.Datetime.context_timestamp(
                                item, item.deadline
                            ).strftime('%H:%M'),
                            mins,
                        ),
                    )
                # Email notification
                if employee.work_email:
                    template = self.env.ref(
                        'restaurant_task_manager.mail_template_task_pre_reminder',
                        raise_if_not_found=False,
                    )
                    if template:
                        template.with_context(
                            reminder_minutes=mins,
                        ).send_mail(item.id, force_send=True)
                # SMS notification
                if employee.work_phone:
                    try:
                        body = _(
                            '⏰ REMINDER: "%s" due in %d min. Complete before %s.',
                            item.name, mins,
                            fields.Datetime.context_timestamp(
                                item, item.deadline
                            ).strftime('%H:%M'),
                        )
                        item._message_sms(body, partner_ids=employee.user_id.partner_id.ids)
                    except Exception:
                        _logger.warning('SMS sending failed for task %s', item.name)
        _logger.info('Sent %d pre-deadline reminders.', reminded)

    @api.model
    def _cron_shift_handoff(self):
        """Auto-carry incomplete tasks to next shift's person in same role."""
        now = fields.Datetime.now()
        buffer = timedelta(minutes=15)
        # Find expired task lists (shift ended, still active)
        expired = self.search([
            ('state', '=', 'active'),
            ('shift_end', '<', now),
            ('shift_end', '>', now - timedelta(hours=2)),  # Only recent shifts
            ('completion_score', '<', 100),
        ])
        handed_off = 0
        for tl in expired:
            incomplete_items = tl.task_item_ids.filtered(lambda i: i.state != 'done')
            if not incomplete_items:
                continue
            # Find next shift in same role at same location
            next_slot = self.env['planning.slot'].search([
                ('role_id', '=', tl.slot_id.role_id.id),
                ('work_location_id', '=', tl.location_id.id),
                ('employee_id', '!=', False),
                ('start_datetime', '>=', tl.shift_end - buffer),
                ('start_datetime', '<=', tl.shift_end + timedelta(hours=4)),
                ('state', '=', 'published'),
            ], order='start_datetime asc', limit=1)
            if not next_slot:
                continue
            # Find or create task list for next slot
            next_list = self.search([
                ('slot_id', '=', next_slot.id),
                ('template_id', '=', tl.template_id.id),
            ], limit=1)
            if not next_list:
                next_list = self.create({
                    'template_id': tl.template_id.id,
                    'slot_id': next_slot.id,
                    'state': 'active',
                })
            # Copy incomplete tasks to next shift
            Subtask = self.env['restaurant.task.subtask']
            for item in incomplete_items:
                new_item = self.env['restaurant.task.item'].create({
                    'task_list_id': next_list.id,
                    'name': _('[HANDOFF] %s') % item.name,
                    'description': item.description,
                    'sequence': item.sequence,
                    'has_deadline': False,  # Reset deadline for handoff
                    'completion_type': item.completion_type,
                    'numeric_label': item.numeric_label,
                    'numeric_min': item.numeric_min,
                    'numeric_max': item.numeric_max,
                    'require_proof_photo': item.require_proof_photo,
                    'instruction_file': item.instruction_file,
                    'instruction_filename': item.instruction_filename,
                    'staff_comment': _(
                        'Handed off from %s (%s shift).',
                        tl.employee_id.name or 'previous shift',
                        fields.Datetime.context_timestamp(
                            tl, tl.shift_start
                        ).strftime('%H:%M') if tl.shift_start else '',
                    ),
                })
                for st in item.subtask_ids:
                    Subtask.create({
                        'task_item_id': new_item.id,
                        'name': st.name,
                        'sequence': st.sequence,
                        'is_done': st.is_done,  # Preserve partial progress
                    })
                handed_off += 1
            # Mark original list as expired
            tl.state = 'expired'
        _logger.info('Handed off %d incomplete tasks to next shifts.', handed_off)

    @api.model
    def _cron_escalation(self):
        """Multi-level escalation: employee → shift lead → manager at timed intervals."""
        now = fields.Datetime.now()
        if 'restaurant.escalation.rule' not in self.env.registry:
            return
        EscRule = self.env['restaurant.escalation.rule']
        rules = EscRule.search([('active', '=', True)], order='delay_minutes asc')
        if not rules:
            return
        overdue_items = self.env['restaurant.task.item'].search([
            ('has_deadline', '=', True),
            ('state', '!=', 'done'),
            ('deadline', '<', now),
            ('task_list_id.state', '=', 'active'),
        ])
        escalated = 0
        for item in overdue_items:
            minutes_overdue = (now - item.deadline).total_seconds() / 60
            for rule in rules:
                if minutes_overdue >= rule.delay_minutes:
                    # Check if this escalation level was already sent
                    field_name = 'escalation_level_%d_sent' % rule.level
                    if field_name not in item._fields:
                        continue
                    if item[field_name]:
                        continue
                    # Determine recipient
                    recipient = rule._get_recipient(item)
                    if recipient and recipient.user_id:
                        item.activity_schedule(
                            'mail.mail_activity_data_todo',
                            user_id=recipient.user_id.id,
                            summary=_('🔴 ESCALATION L%d: %s') % (rule.level, item.name),
                            note=_(
                                'Task "%s" assigned to %s is %d min overdue. '
                                'Escalation level %d triggered.',
                                item.name,
                                item.employee_id.name or 'Unknown',
                                int(minutes_overdue),
                                rule.level,
                            ),
                        )
                        # Send email to escalation recipient
                        if recipient.work_email:
                            template = self.env.ref(
                                'restaurant_task_manager.mail_template_escalation',
                                raise_if_not_found=False,
                            )
                            if template:
                                template.with_context(
                                    escalation_level=rule.level,
                                    escalation_recipient=recipient.name,
                                    escalation_recipient_email=recipient.work_email,
                                    minutes_overdue=int(minutes_overdue),
                                ).send_mail(item.id, force_send=True)
                        # SMS
                        if recipient.work_phone:
                            try:
                                body = _(
                                    '🔴 ESCALATION L%d: "%s" is %dmin overdue '
                                    '(assigned to %s). Please intervene.',
                                    rule.level, item.name,
                                    int(minutes_overdue),
                                    item.employee_id.name or 'Unknown',
                                )
                                item._message_sms(
                                    body, partner_ids=recipient.user_id.partner_id.ids,
                                )
                            except Exception:
                                _logger.warning(
                                    'SMS escalation failed for task %s level %d',
                                    item.name, rule.level,
                                )
                        # Mark this level as sent (must use write() to persist)
                        if field_name in item._fields:
                            item.write({field_name: True})
                        escalated += 1
        _logger.info('Processed %d escalation notifications.', escalated)
