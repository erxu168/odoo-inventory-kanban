# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

import pytz

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


def _tz_get(self):
    """Timezone selection, mirroring the one used on res.partner / res.users."""
    return [(tz, tz) for tz in sorted(
        pytz.all_timezones,
        key=lambda tz: tz if not tz.startswith('Etc/') else '_',
    )]


class PosConfig(models.Model):
    """Per-outlet settings driving the daily sales close-out."""
    _inherit = 'pos.config'

    sales_entry_required = fields.Boolean(
        string='Daily Sales Entry',
        default=True,
        help="Generate a draft daily sales entry for this outlet every night.",
    )
    sales_tz = fields.Selection(
        _tz_get, string='Sales Timezone',
        default=lambda self: self.env.user.tz or 'UTC',
        help="Timezone used to decide which business day an order belongs to. "
             "The scheduled actions run as a system user, so this cannot be "
             "taken from the person opening the entry.",
    )
    sales_day_cutoff_hour = fields.Float(
        string='Business Day Cutoff',
        default=4.0,
        help="Local hour at which the business day rolls over. With the "
             "default of 4:00, the business day of the 25th runs from "
             "25/04:00 to 26/04:00, so late-night orders stay on the shift "
             "that rang them up.",
    )
    sales_cash_tolerance = fields.Float(
        string='Cash Variance Tolerance',
        default=5.0,
        help="Cash difference (in absolute value) that can be submitted "
             "without a written explanation.",
    )
    sales_staff_ids = fields.Many2many(
        'res.users', 'pos_config_sales_staff_rel', 'config_id', 'user_id',
        string='Close-out Staff',
        help="Users allowed to count and submit this outlet's daily sales. "
             "Nightly entries are opened by a scheduled action with nobody "
             "assigned, so this list is what makes them visible.",
    )
    sales_manager_ids = fields.Many2many(
        'res.users', 'pos_config_sales_manager_rel', 'config_id', 'user_id',
        string='Outlet Managers',
        help="Users who review and approve this outlet's daily sales. They "
             "also see its entries even when they manage no other outlet.",
    )

    @api.constrains('sales_day_cutoff_hour')
    def _check_sales_day_cutoff_hour(self):
        for config in self:
            if not 0.0 <= config.sales_day_cutoff_hour < 24.0:
                raise ValidationError(_(
                    "The business day cutoff of %(outlet)s must be between "
                    "0:00 and 23:59.", outlet=config.display_name,
                ))

    @api.constrains('sales_cash_tolerance')
    def _check_sales_cash_tolerance(self):
        for config in self:
            if config.sales_cash_tolerance < 0.0:
                raise ValidationError(
                    _("The cash variance tolerance cannot be negative.")
                )

    # ── Business day helpers ──────────────────────────────────

    def _sales_timezone(self):
        """Return the pytz timezone this outlet books its sales days in."""
        self.ensure_one()
        try:
            return pytz.timezone(self.sales_tz or 'UTC')
        except pytz.UnknownTimeZoneError:
            return pytz.UTC

    def _sales_cutoff_time(self):
        """Business day cutoff as a (hour, minute) pair."""
        self.ensure_one()
        cutoff = min(max(self.sales_day_cutoff_hour or 0.0, 0.0), 23.99)
        hour = int(cutoff)
        minute = min(int(round((cutoff - hour) * 60)), 59)
        return hour, minute

    def _sales_current_business_date(self, now=None):
        """The business date this outlet is currently ringing sales into."""
        self.ensure_one()
        tz = self._sales_timezone()
        local_now = pytz.UTC.localize(now or fields.Datetime.now()).astimezone(tz)
        hour, minute = self._sales_cutoff_time()
        business_date = local_now.date()
        if (local_now.hour, local_now.minute) < (hour, minute):
            business_date -= timedelta(days=1)
        return business_date

    def _sales_day_window(self, business_date):
        """UTC (start, end) datetimes covering ``business_date`` for this outlet.

        The window is half-open: ``start <= date_order < end``.
        """
        self.ensure_one()
        tz = self._sales_timezone()
        hour, minute = self._sales_cutoff_time()

        def _to_utc(day):
            # Localize the wall-clock time of each boundary separately so a
            # DST switch inside the window keeps both ends at the cutoff hour.
            local = tz.localize(datetime.combine(day, time(hour, minute)))
            return local.astimezone(pytz.UTC).replace(tzinfo=None)

        return _to_utc(business_date), _to_utc(business_date + timedelta(days=1))
