# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    task_completion_score = fields.Float(
        string='Task Completion %',
        compute='_compute_task_completion',
        store=True,
    )
    task_list_ids = fields.Many2many(
        'restaurant.task.list',
        compute='_compute_task_completion',
        store=True,
    )
    task_summary = fields.Char(compute='_compute_task_summary')
    checkout_blocked = fields.Boolean(
        compute='_compute_checkout_blocked',
        help='True if any task list with block policy has incomplete tasks.',
    )

    @api.depends('employee_id', 'check_in', 'check_out')
    def _compute_task_completion(self):
        TaskList = self.env['restaurant.task.list']
        for att in self:
            if not att.check_in or not att.employee_id:
                att.task_completion_score = 0.0
                att.task_list_ids = False
                continue
            check_out = att.check_out or fields.Datetime.now()
            buffer = timedelta(minutes=30)
            lists = TaskList.search([
                ('employee_id', '=', att.employee_id.id),
                ('shift_start', '<=', check_out + buffer),
                ('shift_end', '>=', att.check_in - buffer),
            ])
            att.task_list_ids = lists
            att.task_completion_score = (
                sum(tl.completion_score for tl in lists) / len(lists)
                if lists else 0.0
            )

    @api.depends('task_completion_score', 'task_list_ids')
    def _compute_task_summary(self):
        for att in self:
            if att.task_list_ids:
                att.task_summary = _('%.0f%% tasks completed') % att.task_completion_score
            else:
                att.task_summary = _('No tasks assigned')

    @api.depends('task_list_ids.completion_score', 'task_list_ids.checkout_policy')
    def _compute_checkout_blocked(self):
        for att in self:
            blocked_lists = att.task_list_ids.filtered(
                lambda tl: tl.checkout_policy == 'block' and tl.completion_score < 100
            )
            att.checkout_blocked = bool(blocked_lists)

    @api.constrains('check_out')
    def _check_task_completion_on_checkout(self):
        """Enforce task completion policy when clocking out."""
        for att in self:
            if not att.check_out or not att.employee_id:
                continue
            buffer = timedelta(minutes=30)
            task_lists = self.env['restaurant.task.list'].search([
                ('employee_id', '=', att.employee_id.id),
                ('shift_start', '<=', att.check_out + buffer),
                ('shift_end', '>=', att.check_in - buffer),
                ('state', '=', 'active'),
            ])
            # Hard-block checkout for lists with 'block' policy
            blocked = task_lists.filtered(
                lambda tl: tl.checkout_policy == 'block' and tl.completion_score < 100
            )
            if blocked:
                incomplete_names = []
                for tl in blocked:
                    pending = tl.task_item_ids.filtered(lambda i: i.state != 'done')
                    incomplete_names.extend(pending.mapped('name'))
                raise UserError(_(
                    'Cannot clock out — the following mandatory tasks are incomplete:\n\n'
                    '• %s\n\n'
                    'Please complete all required tasks before checking out.'
                ) % '\n• '.join(incomplete_names[:10]))

            # Warn for lists with 'warn' policy (log message, allow checkout)
            warned = task_lists.filtered(
                lambda tl: tl.checkout_policy == 'warn' and tl.completion_score < 100
            )
            if warned:
                for tl in warned:
                    pending = tl.task_item_ids.filtered(lambda i: i.state != 'done')
                    _logger.warning(
                        'Employee %s clocked out with %d incomplete tasks (warn policy): %s',
                        att.employee_id.name,
                        len(pending),
                        ', '.join(pending.mapped('name')[:5]),
                    )


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    task_list_ids = fields.One2many(
        'restaurant.task.list', 'employee_id', string='Task Lists',
    )
    avg_task_completion = fields.Float(
        string='Avg Completion %',
        compute='_compute_avg_task_completion',
    )
    total_task_lists = fields.Integer(compute='_compute_avg_task_completion')
    team_avg_task_completion = fields.Float(
        string='Team Average %',
        compute='_compute_team_avg',
        help='Anonymous team average for comparison.',
    )

    @api.depends('task_list_ids.completion_score', 'task_list_ids.state')
    def _compute_avg_task_completion(self):
        for emp in self:
            lists = emp.task_list_ids.filtered(
                lambda l: l.state in ('active', 'done', 'expired')
            )
            emp.total_task_lists = len(lists)
            emp.avg_task_completion = (
                sum(l.completion_score for l in lists) / len(lists)
                if lists else 0.0
            )

    def _compute_team_avg(self):
        """Compute anonymous team average across all employees at same location."""
        for emp in self:
            location = emp.work_location_id
            if location:
                all_lists = self.env['restaurant.task.list'].search([
                    ('location_id', '=', location.id),
                    ('state', 'in', ('active', 'done', 'expired')),
                ])
            else:
                all_lists = self.env['restaurant.task.list'].search([
                    ('state', 'in', ('active', 'done', 'expired')),
                ])
            emp.team_avg_task_completion = (
                sum(l.completion_score for l in all_lists) / len(all_lists)
                if all_lists else 0.0
            )


class HrEmployeePublic(models.Model):
    """Extend public employee model so staff can see their own score + team avg."""
    _inherit = 'hr.employee.public'

    avg_task_completion = fields.Float(
        string='Avg Completion %',
        compute='_compute_avg_task_completion',
    )
    team_avg_task_completion = fields.Float(
        string='Team Average %',
        compute='_compute_team_avg',
    )

    def _compute_avg_task_completion(self):
        for emp in self:
            lists = self.env['restaurant.task.list'].search([
                ('employee_id', '=', emp.id),
                ('state', 'in', ('active', 'done', 'expired')),
            ])
            emp.avg_task_completion = (
                sum(l.completion_score for l in lists) / len(lists)
                if lists else 0.0
            )

    def _compute_team_avg(self):
        for emp in self:
            all_lists = self.env['restaurant.task.list'].search([
                ('state', 'in', ('active', 'done', 'expired')),
            ])
            emp.team_avg_task_completion = (
                sum(l.completion_score for l in all_lists) / len(all_lists)
                if all_lists else 0.0
            )
