# -*- coding: utf-8 -*-
{
    'name': 'Restaurant Locations',
    'version': '19.0.1.0.0',
    'category': 'Operations',
    'summary': 'Per-site facility record: lease, utilities, meters, waste pickups, insurance, permits',
    'description': """
Restaurant Locations
====================

One record per restaurant site, holding everything that is bound to the
building rather than to the business day:

* **Contracts** – lease (landlord, rent, deposit), electricity, gas, water,
  district heating, telecom, waste disposal, insurance policies and service
  agreements, each with its notice period. The cancellation deadline is
  computed and reminded at 90/60/30 days; auto-renewing terms roll forward
  when the deadline passes.
* **Meters and readings** – readings stay with the meter, not the supplier.
  Consumption, daily average and an indicative cost from the contract in
  force on the reading date are worked out per reading.
* **Waste & recycling** – one stream per container (residual, packaging,
  glass, paper, organic, food waste, cooking oil, grease trap…), each with
  its own hauler and pickup rhythm (weekday, odd/even calendar week,
  monthly). Pickups are laid out on a calendar and ticked off, which gives
  the disposal record the commercial-waste ordinance asks for.
* **Permits & inspections** – licences and recurring checks (grease trap,
  DGUV V3, extinguishers, hood cleaning…) with due dates and reminders.
* **Key contacts** – who to call for the building.

Independent of any rental / property module: a restaurant is operated,
not let.
""",
    'author': 'Krawings',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/waste_type_data.xml',
        'data/compliance_type_data.xml',
        'data/cron_jobs.xml',
        'views/contract_views.xml',
        'views/meter_views.xml',
        'views/waste_views.xml',
        'views/compliance_views.xml',
        'views/location_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
}
