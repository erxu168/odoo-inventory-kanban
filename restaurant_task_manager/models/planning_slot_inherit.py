# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    task_list_ids = fields.One2many(
        'restaurant.task.list', 'slot_id', string='Task Lists',
    )
    task_list_count = fields.Integer(compute='_compute_task_list_count')
    task_completion_score = fields.Float(compute='_compute_task_completion_score')

    @api.depends('task_list_ids')
    def _compute_task_list_count(self):
        for slot in self:
            slot.task_list_count = len(slot.task_list_ids)

    @api.depends('task_list_ids.completion_score')
    def _compute_task_completion_score(self):
        for slot in self:
            lists = slot.task_list_ids
            slot.task_completion_score = (
                sum(l.completion_score for l in lists) / len(lists)
                if lists else 0.0
            )

    def action_view_task_lists(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Shift Tasks'),
            'res_model': 'restaurant.task.list',
            'view_mode': 'list,form',
            'domain': [('slot_id', '=', self.id)],
            'context': {'default_slot_id': self.id},
        }

    def write(self, vals):
        result = super().write(vals)
        if vals.get('state') == 'published':
            self._auto_generate_task_lists()
        return result

    def _auto_generate_task_lists(self):
        TaskList = self.env['restaurant.task.list']
        templates = self.env['restaurant.task.list.template'].search([
            ('role_ids', '!=', False),
            ('active', '=', True),
        ])
        for slot in self:
            if not slot.employee_id:
                continue
            if TaskList.search_count([('slot_id', '=', slot.id)]):
                continue
            matching = templates.filtered(
                lambda t: slot.role_id in t.role_ids and (
                    not t.location_id or t.location_id == slot.work_location_id
                )
            )
            for tmpl in matching:
                tl = TaskList.create({
                    'template_id': tmpl.id,
                    'slot_id': slot.id,
                })
                tl.action_generate_tasks()
                _logger.info('Auto-generated task list "%s" for slot %s', tl.name, slot.id)
