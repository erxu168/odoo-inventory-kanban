# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    task_completion_score = fields.Float(
        compute='_compute_task_completion', string='Task Completion %',
    )
    task_list_ids = fields.Many2many(
        'restaurant.task.list', string='Task Lists',
        compute='_compute_task_completion',
    )
    checkout_blocked = fields.Boolean(compute='_compute_checkout_blocked')

    @api.depends('employee_id', 'check_in', 'check_out')
    def _compute_task_completion(self):
        TaskList = self.env['restaurant.task.list']
        for att in self:
            if not att.employee_id or not att.check_in:
                att.task_completion_score = 0
                att.task_list_ids = False
                continue
            domain = [
                ('employee_id', '=', att.employee_id.id),
                ('shift_start', '>=', att.check_in),
            ]
            if att.check_out:
                domain.append(('shift_start', '<=', att.check_out))
            lists = TaskList.search(domain)
            att.task_list_ids = lists
            if lists:
                att.task_completion_score = sum(
                    l.completion_score for l in lists
                ) / len(lists)
            else:
                att.task_completion_score = 0

    @api.depends('employee_id', 'check_in', 'check_out')
    def _compute_checkout_blocked(self):
        for att in self:
            # Recompute from task lists matching this attendance window
            att.checkout_blocked = any(
                tl.checkout_policy == 'block' and tl.completion_score < 100
                for tl in att.task_list_ids
            )

    @api.constrains('check_out')
    def _check_task_completion_on_checkout(self):
        for att in self:
            if att.check_out and att.checkout_blocked:
                raise ValidationError(_(
                    'Cannot check out: incomplete tasks with "Block Checkout" policy. '
                    'Complete all required tasks first.'
                ))


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    task_list_ids = fields.One2many(
        'restaurant.task.list', 'employee_id', string='Task Lists',
    )
    avg_task_completion = fields.Float(
        compute='_compute_avg_task_completion', string='Avg Completion %',
    )

    @api.depends('task_list_ids.completion_score')
    def _compute_avg_task_completion(self):
        for emp in self:
            done_lists = emp.task_list_ids.filtered(
                lambda l: l.state in ('done', 'expired')
            )
            if done_lists:
                emp.avg_task_completion = sum(
                    l.completion_score for l in done_lists
                ) / len(done_lists)
            else:
                emp.avg_task_completion = 0
