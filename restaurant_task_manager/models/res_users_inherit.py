# -*- coding: utf-8 -*-
from odoo import models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        """Set apps_home as default home action for new users."""
        apps_home = self.env.ref(
            'restaurant_task_manager.action_apps_home',
            raise_if_not_found=False,
        )
        if apps_home:
            for vals in vals_list:
                if 'action_id' not in vals:
                    vals['action_id'] = apps_home.id
        return super().create(vals_list)
