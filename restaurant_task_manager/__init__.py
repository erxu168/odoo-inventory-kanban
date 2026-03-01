# -*- coding: utf-8 -*-
from . import models


def _set_apps_home_action(env):
    """Post-init hook: set apps_home as home action for all existing users."""
    action = env.ref(
        'restaurant_task_manager.action_apps_home',
        raise_if_not_found=False,
    )
    if action:
        # Set for all internal users who don't have a home action yet
        users = env['res.users'].search([
            ('action_id', '=', False),
            ('share', '=', False),
        ])
        if users:
            users.write({'action_id': action.id})

