# -*- coding: utf-8 -*-
{
    'name': 'Restaurant Task Manager',
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Planning',
    'summary': 'Shift-based task management for restaurant staff with attendance integration',
    'description': """
Restaurant Task Manager — Phase 1 + Phase 2
=============================================
Shift-linked task management for multi-location restaurant operations.

Core Features (Phase 1):
- Task templates with sub-task checklists
- Multiple completion types: checkbox, photo, numeric, text note
- Optional deadlines per task
- PDF instruction attachments
- Auto-generation from planning roles on shift publish
- Individual task lists per employee per shift
- Simple completion scoring (completed/total %)
- Attendance integration (completion shown at checkout)
- Warning emails for incomplete tasks
- 3-tier access: Owner/Admin → Manager → Staff
- Multi-location data isolation
- Staff comments on tasks
- Manager dashboard with real-time today view

Advanced Features (Phase 2):
- Digital signature completion type
- Pre-deadline configurable reminders (per task, with SMS)
- Clock-out enforcement: hard-block or warn (configurable per template)
- Multi-level escalation chain (employee → lead → manager)
- Shift handoff: auto-carry incomplete tasks to next shift
- Ad-hoc quick tasks for managers during live shifts
- Staff score + anonymous team average comparison
- Weekly/monthly trend analysis dashboards
- Cross-location completion comparison
- Excel/PDF export via standard Odoo export
    """,
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'hr',
        'hr_attendance',
        'planning',
        'sms',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/mail_templates.xml',
        'data/cron_jobs.xml',
        'views/task_template_views.xml',
        'views/task_list_views.xml',
        'views/task_item_views.xml',
        'views/escalation_views.xml',
        'views/quick_task_views.xml',
        'views/dashboard_views.xml',
        'views/planning_slot_views.xml',
        'views/attendance_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'restaurant_task_manager/static/src/css/task_manager.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
