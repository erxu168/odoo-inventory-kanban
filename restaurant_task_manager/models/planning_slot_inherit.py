# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    task_list_ids = fields.One2many(
        'restaurant.task.list', 'slot_id', string='Task Lists',
    )
    task_list_count = fields.Integer(compute='_compute_task_list_count')
    task_completion_score = fields.Float(
        compute='_compute_task_completion_score', string='Task Completion %',
    )

    @api.depends('task_list_ids')
    def _compute_task_list_count(self):
        for slot in self:
            slot.task_list_count = len(slot.task_list_ids)

    @api.depends('task_list_ids.completion_score')
    def _compute_task_completion_score(self):
        for slot in self:
            lists = slot.task_list_ids
            if lists:
                slot.task_completion_score = sum(
                    l.completion_score for l in lists
                ) / len(lists)
            else:
                slot.task_completion_score = 0

    def action_view_task_lists(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Task Lists',
            'res_model': 'restaurant.task.list',
            'view_mode': 'list,form',
            'domain': [('slot_id', '=', self.id)],
        }
