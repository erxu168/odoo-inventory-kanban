# -*- coding: utf-8 -*-
from datetime import date, datetime

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

# 2026-09-14 is a Monday, 2026-09-19 a Saturday.
MONDAY = date(2026, 9, 14)
SATURDAY = date(2026, 9, 19)


@tagged('post_install', '-at_install')
class TestLunchDiscount(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dish_categ = cls.env['product.category'].create({'name': 'Dishes'})
        cls.drink_categ = cls.env['product.category'].create({'name': 'Drinks'})
        cls.dish = cls.env['product.product'].create({
            'name': 'Jerk Chicken Plate',
            'list_price': 15.0,
            'categ_id': cls.dish_categ.id,
        })
        cls.drink = cls.env['product.product'].create({
            'name': 'Ginger Beer',
            'list_price': 4.0,
            'categ_id': cls.drink_categ.id,
        })
        cls.pricelist = cls.env['product.pricelist'].create({'name': 'Restaurant'})
        cls.lunch_rule = cls.env['product.pricelist.item'].create({
            'pricelist_id': cls.pricelist.id,
            'applied_on': '2_product_category',
            'categ_id': cls.dish_categ.id,
            'compute_price': 'percentage',
            'percent_price': 20.0,
            'waj_time_restricted': True,
            'waj_hour_from': 12.0,
            'waj_hour_to': 16.0,
            'waj_tz': 'UTC',
            # weekday defaults: Mon-Fri
        })

    def _price(self, product, when):
        return self.pricelist._get_product_price(product, 1.0, date=when)

    def test_discount_during_lunch_on_weekday(self):
        self.assertEqual(self._price(self.dish, datetime.combine(MONDAY, datetime.min.time().replace(hour=13))), 12.0)
        # window boundaries: start inclusive, end exclusive
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 12, 0, 0)), 12.0)
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 15, 59, 59)), 12.0)

    def test_no_discount_outside_hours(self):
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 11, 59, 59)), 15.0)
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 16, 0, 0)), 15.0)
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 19, 0, 0)), 15.0)

    def test_no_discount_on_weekend(self):
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 19, 13, 0, 0)), 15.0)
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 20, 13, 0, 0)), 15.0)

    def test_weekend_can_be_enabled(self):
        self.lunch_rule.waj_weekday_sat = True
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 19, 13, 0, 0)), 12.0)

    def test_other_categories_untouched(self):
        self.assertEqual(self._price(self.drink, datetime(2026, 9, 14, 13, 0, 0)), 4.0)

    def test_timezone_is_respected(self):
        # Berlin is UTC+2 in September: 10:30 UTC is 12:30 local (lunch),
        # 14:30 UTC is 16:30 local (after lunch).
        self.lunch_rule.waj_tz = 'Europe/Berlin'
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 10, 30, 0)), 12.0)
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 14, 30, 0)), 15.0)
        # Sunday 23:00 UTC is already Monday 01:00 in Berlin: right weekday, wrong hour.
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 20, 23, 0, 0)), 15.0)

    def test_plain_date_checks_weekday_only(self):
        self.assertTrue(self.lunch_rule._waj_is_active_at(MONDAY))
        self.assertFalse(self.lunch_rule._waj_is_active_at(SATURDAY))

    def test_unrestricted_rule_ignores_window_fields(self):
        self.lunch_rule.waj_time_restricted = False
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 19, 3, 0, 0)), 12.0)

    def test_lunch_rule_wins_over_everyday_rule_of_same_level(self):
        everyday = self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'applied_on': '2_product_category',
            'categ_id': self.dish_categ.id,
            'compute_price': 'percentage',
            'percent_price': 5.0,
        })
        self.assertTrue(everyday.id > self.lunch_rule.id)  # newer rule, sorted first by default
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 13, 0, 0)), 12.0)
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 18, 0, 0)), 14.25)

    def test_product_rule_still_beats_category_lunch_rule(self):
        self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'applied_on': '1_product',
            'product_tmpl_id': self.dish.product_tmpl_id.id,
            'compute_price': 'fixed',
            'fixed_price': 9.0,
        })
        self.assertEqual(self._price(self.dish, datetime(2026, 9, 14, 13, 0, 0)), 9.0)

    def test_rule_name_shows_window(self):
        self.assertIn('Mon-Fri 12:00-16:00', self.lunch_rule.name)
        self.lunch_rule.write({'waj_weekday_sat': True, 'waj_hour_to': 15.5})
        self.assertIn('Mon, Tue, Wed, Thu, Fri, Sat 12:00-15:30', self.lunch_rule.name)

    def test_constraints(self):
        with self.assertRaises(ValidationError):
            self.lunch_rule.write({'waj_hour_from': 16.0, 'waj_hour_to': 12.0})
        with self.assertRaises(ValidationError):
            self.lunch_rule.write({'waj_hour_to': 25.0})
        with self.assertRaises(ValidationError):
            self.lunch_rule.write({
                'waj_weekday_mon': False, 'waj_weekday_tue': False, 'waj_weekday_wed': False,
                'waj_weekday_thu': False, 'waj_weekday_fri': False,
            })

    def test_pos_loads_window_fields(self):
        fields_loaded = self.env['product.pricelist.item']._load_pos_data_fields(self.env['pos.config'])
        for name in ('waj_time_restricted', 'waj_hour_from', 'waj_hour_to', 'waj_tz', 'waj_weekday_mon', 'waj_weekday_sun'):
            self.assertIn(name, fields_loaded)
