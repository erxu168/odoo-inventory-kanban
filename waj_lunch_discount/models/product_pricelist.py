# -*- coding: utf-8 -*-
from odoo import models


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    def _get_applicable_rules(self, products, date, **kwargs):
        """Drop rules whose day/hour window does not contain ``date``.

        When a time-limited rule is active it takes precedence over a regular
        rule of the same level (product / category / global), so that a lunch
        deal wins over the everyday price without the user having to worry
        about rule ordering.
        """
        rules = super()._get_applicable_rules(products, date, **kwargs)
        if not rules:
            return rules

        active_rules = rules.filtered(lambda rule: rule._waj_is_active_at(date))
        if not any(active_rules.mapped('waj_time_restricted')):
            return active_rules

        # ``sorted`` is stable: the default ordering (min_quantity desc, ...)
        # is preserved inside each (applied_on, restricted) bucket.
        return active_rules.sorted(
            key=lambda rule: (rule.applied_on, not rule.waj_time_restricted)
        )
