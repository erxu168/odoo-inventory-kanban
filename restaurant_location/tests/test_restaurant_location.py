# -*- coding: utf-8 -*-
from datetime import date

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRestaurantLocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Location = cls.env['restaurant.location']
        cls.Contract = cls.env['restaurant.location.contract']
        cls.Meter = cls.env['restaurant.location.meter']
        cls.Reading = cls.env['restaurant.location.meter.reading']
        cls.Stream = cls.env['restaurant.location.waste.stream']
        cls.Pickup = cls.env['restaurant.location.waste.pickup']
        cls.Compliance = cls.env['restaurant.location.compliance']

        cls.gasag = cls.env['res.partner'].create({'name': 'GASAG', 'is_company': True})
        cls.landlord = cls.env['res.partner'].create({'name': 'Hausbesitz GmbH', 'is_company': True})
        cls.site = cls.Location.create({
            'name': 'Test Site', 'code': 'TST',
            'street': 'Landsberger Allee 1', 'zip': '10249', 'city': 'Berlin',
        })

    # ── Contracts ──

    @freeze_time('2026-09-15')
    def test_termination_deadline_and_status(self):
        c = self.Contract.create({
            'name': 'Gas', 'contract_type': 'gas', 'location_id': self.site.id,
            'provider_id': self.gasag.id,
            'start_date': date(2025, 12, 1), 'end_date': date(2026, 11, 30),
            'notice_value': 2, 'notice_unit': 'months',
        })
        self.assertEqual(c.termination_deadline, date(2026, 9, 30))
        # Deadline is inside 90 days of today (2026-09-15) -> cancellation window.
        self.assertEqual(c.status, 'expiring')
        # Once the deadline has passed the window is closed: nothing to do.
        c.notice_value = 3
        self.assertEqual(c.termination_deadline, date(2026, 8, 30))
        self.assertEqual(c.status, 'active')
        self.assertEqual(c.unit_label, 'kWh')

        far = self.Contract.create({
            'name': 'Strom', 'contract_type': 'electricity', 'location_id': self.site.id,
            'start_date': date(2026, 1, 1), 'end_date': date(2027, 12, 31),
            'notice_value': 6, 'notice_unit': 'weeks',
        })
        self.assertEqual(far.termination_deadline, date(2027, 11, 19))
        self.assertEqual(far.status, 'active')

        open_ended = self.Contract.create({
            'name': 'Wasser', 'contract_type': 'water', 'location_id': self.site.id,
            'start_date': date(2020, 1, 1),
        })
        self.assertFalse(open_ended.termination_deadline)
        self.assertEqual(open_ended.status, 'active')
        self.assertEqual(open_ended.unit_label, 'm³')

    @freeze_time('2026-09-15')
    def test_annual_cost_by_type(self):
        lease = self.Contract.create({
            'name': 'Miete', 'contract_type': 'lease', 'location_id': self.site.id,
            'provider_id': self.landlord.id, 'start_date': date(2024, 1, 1),
            'end_date': date(2029, 12, 31), 'notice_value': 6,
            'rent_net': 3000, 'rent_charges': 500, 'rent_vat': 665,
        })
        self.assertAlmostEqual(lease.rent_total, 4165)
        self.assertAlmostEqual(lease.annual_cost, 4165 * 12)
        # Location summary follows the active lease.
        self.assertEqual(self.site.lease_contract_id, lease)
        self.assertEqual(self.site.landlord_id, self.landlord)
        self.assertAlmostEqual(self.site.monthly_rent_total, 4165)
        self.assertEqual(self.site.lease_termination_deadline, date(2029, 6, 30))

        gas = self.Contract.create({
            'name': 'Gas', 'contract_type': 'gas', 'location_id': self.site.id,
            'start_date': date(2026, 1, 1), 'base_fee': 12.5, 'monthly_installment': 480,
        })
        self.assertAlmostEqual(gas.annual_cost, 480 * 12)
        gas.monthly_installment = 0
        self.assertAlmostEqual(gas.annual_cost, 12.5 * 12)

        ins = self.Contract.create({
            'name': 'Haftpflicht', 'contract_type': 'insurance', 'location_id': self.site.id,
            'start_date': date(2026, 1, 1), 'amount': 350, 'frequency': 'quarterly',
        })
        self.assertAlmostEqual(ins.annual_cost, 1400)
        self.assertAlmostEqual(self.site.annual_fixed_cost, 4165 * 12 + 12.5 * 12 + 1400)

    @freeze_time('2026-09-15')
    def test_cron_reminders_and_auto_renewal(self):
        c = self.Contract.create({
            'name': 'Telekom', 'contract_type': 'telecom', 'location_id': self.site.id,
            'start_date': date(2024, 11, 1), 'end_date': date(2026, 10, 31),
            'notice_value': 1, 'notice_unit': 'months',
            'auto_renewal': True, 'renewal_months': 12,
        })
        # Deadline 2026-09-30 -> 15 days away: the 30-day reminder fires once.
        self.Contract._cron_check_termination_alerts()
        self.assertTrue(c.alert_30_sent)
        todo = c.activity_ids.filtered(lambda a: 'Cancel' in a.summary)
        self.assertEqual(len(todo), 1)
        self.Contract._cron_check_termination_alerts()
        self.assertEqual(len(c.activity_ids), 1, "reminder must not repeat")

        # Editing the term resets the reminder flags.
        c.end_date = date(2027, 10, 31)
        self.assertFalse(c.alert_30_sent)

        # A term that ended without cancellation rolls forward by the renewal period.
        old = self.Contract.create({
            'name': 'Old', 'contract_type': 'service', 'location_id': self.site.id,
            'start_date': date(2024, 1, 1), 'end_date': date(2026, 6, 30),
            'notice_value': 3, 'auto_renewal': True, 'renewal_months': 12,
        })
        self.Contract._cron_check_termination_alerts()
        self.assertEqual(old.end_date, date(2027, 6, 30))
        self.assertEqual(old.status, 'active')

        # A missed deadline with the term still running extends it once, now.
        missed = self.Contract.create({
            'name': 'Missed', 'contract_type': 'insurance', 'location_id': self.site.id,
            'start_date': date(2024, 12, 1), 'end_date': date(2026, 11, 30),
            'notice_value': 3, 'auto_renewal': True, 'renewal_months': 12,
        })
        self.assertEqual(missed.termination_deadline, date(2026, 8, 30))
        self.Contract._cron_check_termination_alerts()
        self.assertEqual(missed.end_date, date(2027, 11, 30))
        self.assertEqual(missed.termination_deadline, date(2027, 8, 30))
        self.assertEqual(missed.status, 'active')
        self.Contract._cron_check_termination_alerts()
        self.assertEqual(missed.end_date, date(2027, 11, 30), "rolls once, not every day")

        # Open-ended auto-renewal with no notice period rolls once the term ends.
        no_notice = self.Contract.create({
            'name': 'No notice', 'contract_type': 'telecom', 'location_id': self.site.id,
            'start_date': date(2024, 1, 1), 'end_date': date(2026, 8, 31),
            'notice_value': 0, 'auto_renewal': True, 'renewal_months': 6,
        })
        self.Contract._cron_check_termination_alerts()
        self.assertEqual(no_notice.end_date, date(2027, 2, 28))

        # A cancelled one stays where it is.
        gone = self.Contract.create({
            'name': 'Gone', 'contract_type': 'service', 'location_id': self.site.id,
            'start_date': date(2024, 1, 1), 'end_date': date(2026, 6, 30),
            'auto_renewal': True, 'renewal_months': 12,
        })
        gone.action_cancel()
        self.Contract._cron_check_termination_alerts()
        self.assertEqual(gone.end_date, date(2026, 6, 30))
        self.assertEqual(gone.status, 'cancelled')

    def test_contract_date_check(self):
        with self.assertRaises(ValidationError):
            self.Contract.create({
                'name': 'Bad', 'contract_type': 'gas', 'location_id': self.site.id,
                'start_date': date(2026, 1, 1), 'end_date': date(2025, 1, 1),
            })

    # ── Meters ──

    @freeze_time('2026-09-15')
    def test_meter_readings(self):
        contract = self.Contract.create({
            'name': 'Gas', 'contract_type': 'gas', 'location_id': self.site.id,
            'provider_id': self.gasag.id, 'start_date': date(2026, 1, 1),
            'unit_price': 0.1189,
        })
        meter = self.Meter.create({
            'name': 'G-123', 'meter_type': 'gas', 'location_id': self.site.id,
            'contract_id': contract.id, 'conversion_factor': 10.0,
            'reading_interval_days': 30,
        })
        self.assertEqual(meter.unit, 'm³')
        self.assertTrue(meter.reading_overdue, "no reading yet -> overdue")

        r1 = self.Reading.create({'meter_id': meter.id, 'date': date(2026, 8, 1), 'value': 1000})
        r2 = self.Reading.create({'meter_id': meter.id, 'date': date(2026, 9, 1), 'value': 1031})
        self.assertEqual(r1.consumption, 0)
        self.assertAlmostEqual(r2.consumption, 31)
        self.assertEqual(r2.days_elapsed, 31)
        self.assertAlmostEqual(r2.daily_average, 1.0)
        self.assertAlmostEqual(r2.billed_units, 310)
        self.assertEqual(r2.contract_id, contract)
        self.assertAlmostEqual(r2.estimated_cost, 310 * 0.1189, places=2)
        self.assertAlmostEqual(meter.last_reading_value, 1031)
        self.assertEqual(meter.last_reading_date, date(2026, 9, 1))
        self.assertFalse(meter.reading_overdue)

        # Inserting an older reading re-chains the newer one.
        self.Reading.create({'meter_id': meter.id, 'date': date(2026, 8, 15), 'value': 1010})
        self.assertAlmostEqual(r2.consumption, 21)

        with self.assertRaises(ValidationError):
            self.Reading.create({'meter_id': meter.id, 'date': date(2026, 9, 10), 'value': 900})

        # Interpolated consumption between dates.
        self.assertAlmostEqual(meter._consumption_between(date(2026, 8, 1), date(2026, 9, 1)), 310)

    @freeze_time('2026-09-15')
    def test_meter_reading_reminder_once(self):
        meter = self.Meter.create({
            'name': 'E-1', 'meter_type': 'electricity', 'location_id': self.site.id,
            'reading_interval_days': 30,
        })
        self.site.manager_user_ids = self.env.user
        self.Meter._cron_reading_reminders()
        self.Meter._cron_reading_reminders()
        self.assertEqual(len(meter.activity_ids), 1)

    # ── Waste ──

    def test_pickup_rules(self):
        glass = self.env.ref('restaurant_location.waste_type_glas')
        # 2026-09-14 is a Monday in ISO week 38 (even).
        with freeze_time('2026-09-14'):
            even = self.Stream.create({
                'location_id': self.site.id, 'waste_type_id': glass.id,
                'schedule': 'biweekly_even', 'weekday': '3', 'generate_horizon_weeks': 6,
            })
            dates = even.pickup_ids.mapped('date')
            self.assertEqual(dates, [date(2026, 9, 17), date(2026, 10, 1), date(2026, 10, 15)])
            for d in dates:
                self.assertEqual(d.weekday(), 3)
                self.assertEqual(d.isocalendar()[1] % 2, 0)
            self.assertEqual(even.next_pickup_date, date(2026, 9, 17))

            odd = self.Stream.create({
                'location_id': self.site.id,
                'waste_type_id': self.env.ref('restaurant_location.waste_type_papier').id,
                'schedule': 'biweekly_odd', 'weekday': '3', 'generate_horizon_weeks': 6,
            })
            self.assertEqual(odd.pickup_ids.mapped('date'),
                             [date(2026, 9, 24), date(2026, 10, 8), date(2026, 10, 22)])

            twice = self.Stream.create({
                'location_id': self.site.id,
                'waste_type_id': self.env.ref('restaurant_location.waste_type_restmuell').id,
                'schedule': 'weekly', 'weekday': '0', 'weekday_2': '3', 'generate_horizon_weeks': 1,
            })
            self.assertEqual(twice.pickup_ids.mapped('date'),
                             [date(2026, 9, 14), date(2026, 9, 17), date(2026, 9, 21)])

            monthly_last = self.Stream.create({
                'location_id': self.site.id,
                'waste_type_id': self.env.ref('restaurant_location.waste_type_altfett').id,
                'schedule': 'monthly', 'weekday': '4', 'nth_weekday': '-1',
                'generate_horizon_weeks': 8,
            })
            self.assertEqual(monthly_last.pickup_ids.mapped('date'),
                             [date(2026, 9, 25), date(2026, 10, 30)])

            monthly_first = self.Stream.create({
                'location_id': self.site.id,
                'waste_type_id': self.env.ref('restaurant_location.waste_type_bio').id,
                'schedule': 'monthly', 'weekday': '1', 'nth_weekday': '1',
                'generate_horizon_weeks': 8,
            })
            self.assertEqual(monthly_first.pickup_ids.mapped('date'),
                             [date(2026, 10, 6), date(2026, 11, 3)])

            on_call = self.Stream.create({
                'location_id': self.site.id,
                'waste_type_id': self.env.ref('restaurant_location.waste_type_sperrmuell').id,
                'schedule': 'on_call',
            })
            self.assertFalse(on_call.pickup_ids)

            # Generation is idempotent.
            before = len(even.pickup_ids)
            even.action_generate_pickups()
            self.assertEqual(len(even.pickup_ids), before)

            # Changing the rule re-plans untouched future pickups only.
            first = even.pickup_ids.sorted('date')[0]
            first.action_done()
            even.write({'weekday': '4'})
            self.assertIn(first, even.pickup_ids)
            planned = even.pickup_ids.filtered(lambda p: p.state == 'planned')
            self.assertTrue(all(p.date.weekday() == 4 for p in planned))

            self.assertAlmostEqual(
                self.Stream.create({
                    'location_id': self.site.id, 'waste_type_id': glass.id,
                    'schedule': 'biweekly_odd', 'weekday': '0',
                    'container_count': 2, 'cost_per_pickup': 15, 'monthly_fee': 10,
                }).annual_cost, 2 * 15 * 26 + 120)

    def test_pickup_missed_marking(self):
        glass = self.env.ref('restaurant_location.waste_type_glas')
        with freeze_time('2026-09-14'):
            stream = self.Stream.create({
                'location_id': self.site.id, 'waste_type_id': glass.id,
                'schedule': 'weekly', 'weekday': '0', 'generate_horizon_weeks': 1,
            })
            first = stream.pickup_ids.sorted('date')[0]
            self.assertEqual(first.date, date(2026, 9, 14))
        with freeze_time('2026-09-20'):
            self.Pickup._mark_missed()
            self.assertEqual(first.state, 'missed')
            self.assertFalse(stream.next_pickup_date == first.date)

    # ── Compliance ──

    @freeze_time('2026-09-15')
    def test_compliance(self):
        self.site.action_add_standard_checks()
        standard = self.env['restaurant.location.compliance.type'].search([('is_standard', '=', True)])
        self.assertEqual(len(self.site.compliance_ids), len(standard))
        self.site.action_add_standard_checks()
        self.assertEqual(len(self.site.compliance_ids), len(standard), "no duplicates")

        trap = self.site.compliance_ids.filtered(
            lambda c: c.type_id == self.env.ref('restaurant_location.compliance_type_fettabscheider_emptying'))
        self.assertEqual(trap.interval_months, 1)
        self.assertEqual(trap.state, 'none')
        trap.last_done = date(2026, 8, 20)
        self.assertEqual(trap.due_date, date(2026, 9, 20))
        self.assertEqual(trap.state, 'due')
        self.assertEqual(self.site.attention_count, 1)

        self.Compliance._cron_check_due()
        self.Compliance._cron_check_due()
        self.assertEqual(len(trap.activity_ids), 1)

        trap.action_mark_done()
        self.assertEqual(trap.last_done, date(2026, 9, 15))
        self.assertEqual(trap.due_date, date(2026, 10, 15))
        self.assertEqual(trap.state, 'ok')

        licence = self.Compliance.create({
            'name': 'Old permit', 'location_id': self.site.id, 'category': 'permit',
            'interval_months': 0, 'due_date': date(2026, 1, 1),
        })
        self.assertEqual(licence.state, 'overdue')

    # ── Security ──

    def test_record_rules(self):
        Users = self.env['res.users']
        manager = Users.create({
            'name': 'Site Manager', 'login': 'site.manager',
            'group_ids': [(6, 0, [self.env.ref('restaurant_location.group_location_manager').id])],
        })
        other = self.Location.create({'name': 'Other Site', 'code': 'OS'})
        self.site.manager_user_ids = manager
        self.Contract.create({
            'name': 'Mine', 'contract_type': 'gas', 'location_id': self.site.id,
            'start_date': date(2026, 1, 1),
        })
        self.Contract.create({
            'name': 'Not mine', 'contract_type': 'gas', 'location_id': other.id,
            'start_date': date(2026, 1, 1),
        })
        seen = self.Location.with_user(manager).search([])
        self.assertEqual(seen, self.site)
        contracts = self.Contract.with_user(manager).search([])
        self.assertEqual(contracts.mapped('name'), ['Mine'])

        admin = Users.create({
            'name': 'Owner', 'login': 'owner',
            'group_ids': [(6, 0, [self.env.ref('restaurant_location.group_location_admin').id])],
        })
        self.assertTrue((self.site | other) <= self.Location.with_user(admin).search([]))
