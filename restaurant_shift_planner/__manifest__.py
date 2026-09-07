{
    'name': 'Restaurant Shift Planner — Attributes & Requirements',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Match the right staff to the right shifts using staff '
               'attributes and per-shift requirements',
    'description': """
Phase 1 of the automated shift planning design (docs/planning-automation-design.md).

Staff carry attribute values (skills, certifications, authorisations, traits).
Shift templates declare requirements over those attributes, either per person
("everyone needs a valid hygiene certificate") or per crew ("at least one
keyholder on shift"). One evaluation routine serves three surfaces:

* a live warning on the Planning shift form when someone unsuitable is assigned
* a coverage gap report over any date range, run before the roster is published
* (later phases) the automatic roster generator

This phase does not schedule anything by itself — it makes manual planning
safe and tells the manager where the gaps are.
""",
    'author': 'Krawings',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr', 'planning'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/attribute_data.xml',
        'data/cron_jobs.xml',
        'views/staff_attribute_views.xml',
        'views/staff_attribute_value_views.xml',
        'views/shift_requirement_views.xml',
        'views/hr_employee_views.xml',
        'views/planning_slot_views.xml',
        'views/shift_gap_report_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
}
