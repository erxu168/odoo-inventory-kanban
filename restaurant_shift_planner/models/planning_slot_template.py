# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PlanningSlotTemplate(models.Model):
    _inherit = 'planning.slot.template'

    requirement_ids = fields.One2many(
        'restaurant.shift.requirement', 'template_id', string='Requirements',
    )
    requirement_count = fields.Integer(compute='_compute_requirement_count')

    @api.depends('requirement_ids')
    def _compute_requirement_count(self):
        for template in self:
            template.requirement_count = len(template.requirement_ids)

    def _shift_requirements(self):
        """Requirements in force for these templates, plus the global ones."""
        return self.env['restaurant.shift.requirement']._for_templates(self)

    def action_view_requirements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Requirements — %s') % self.display_name,
            'res_model': 'restaurant.shift.requirement',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
        }
