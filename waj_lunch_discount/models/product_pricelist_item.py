# -*- coding: utf-8 -*-
from datetime import date as date_type, datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.base.models.res_partner import _tz_get

# Field name for each weekday, indexed by ``datetime.weekday()`` (0 = Monday).
WEEKDAY_FIELDS = (
    'waj_weekday_mon',
    'waj_weekday_tue',
    'waj_weekday_wed',
    'waj_weekday_thu',
    'waj_weekday_fri',
    'waj_weekday_sat',
    'waj_weekday_sun',
)
WEEKDAY_LABELS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def _format_hour(value):
    """Turn a float hour (13.5) into a clock string (13:30)."""
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes == 60:
        hours, minutes = hours + 1, 0
    return '%02d:%02d' % (hours, minutes)


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    waj_time_restricted = fields.Boolean(
        string='Limit to Days & Hours',
        help='Only apply this rule on the selected weekdays, between the '
             'given hours (e.g. a lunch deal Mon-Fri 12:00-16:00).',
    )
    waj_weekday_mon = fields.Boolean(string='Monday', default=True)
    waj_weekday_tue = fields.Boolean(string='Tuesday', default=True)
    waj_weekday_wed = fields.Boolean(string='Wednesday', default=True)
    waj_weekday_thu = fields.Boolean(string='Thursday', default=True)
    waj_weekday_fri = fields.Boolean(string='Friday', default=True)
    waj_weekday_sat = fields.Boolean(string='Saturday', default=False)
    waj_weekday_sun = fields.Boolean(string='Sunday', default=False)
    waj_hour_from = fields.Float(
        string='From Hour', default=12.0,
        help='Start of the daily window (inclusive), in the rule timezone.',
    )
    waj_hour_to = fields.Float(
        string='To Hour', default=16.0,
        help='End of the daily window (exclusive), in the rule timezone.',
    )
    waj_tz = fields.Selection(
        _tz_get, string='Timezone',
        default=lambda self: self.env.user.tz or self.env.company.partner_id.tz or 'UTC',
        help='Timezone in which the weekdays and hours are evaluated. '
             'Use the timezone of the restaurant.',
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('waj_time_restricted', 'waj_hour_from', 'waj_hour_to', *WEEKDAY_FIELDS)
    def _check_waj_time_window(self):
        for item in self.filtered('waj_time_restricted'):
            if not (0.0 <= item.waj_hour_from < 24.0) or not (0.0 < item.waj_hour_to <= 24.0):
                raise ValidationError(_('The hours of a time-limited pricelist rule must be between 00:00 and 24:00.'))
            if item.waj_hour_from >= item.waj_hour_to:
                raise ValidationError(_(
                    'The start hour (%(start)s) of a time-limited pricelist rule must be before its end hour (%(end)s).',
                    start=_format_hour(item.waj_hour_from),
                    end=_format_hour(item.waj_hour_to),
                ))
            if not any(item[field] for field in WEEKDAY_FIELDS):
                raise ValidationError(_('Select at least one weekday for a time-limited pricelist rule.'))

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _waj_window_label(self):
        """Short human readable description of the window, e.g. 'Mon-Fri 12:00-16:00'."""
        self.ensure_one()
        if not self.waj_time_restricted:
            return ''
        days = [WEEKDAY_LABELS[i] for i, field in enumerate(WEEKDAY_FIELDS) if self[field]]
        if len(days) == 7:
            days_label = _('Every day')
        elif days == list(WEEKDAY_LABELS[:5]):
            days_label = 'Mon-Fri'
        else:
            days_label = ', '.join(days)
        return '%s %s-%s' % (days_label, _format_hour(self.waj_hour_from), _format_hour(self.waj_hour_to))

    @api.depends('waj_time_restricted', 'waj_hour_from', 'waj_hour_to', *WEEKDAY_FIELDS)
    def _compute_name(self):
        super()._compute_name()
        for item in self.filtered('waj_time_restricted'):
            item.name = '%s (%s)' % (item.name, item._waj_window_label())

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------

    def _waj_is_active_at(self, date=None):
        """Whether the rule's day/hour window contains ``date``.

        :param date: naive UTC datetime (Odoo convention), tz-aware datetime,
                     or a plain date. Defaults to now. For a plain date only
                     the weekday is checked because there is no time of day.
        :rtype: bool
        """
        self.ensure_one()
        if not self.waj_time_restricted:
            return True

        if not date:
            date = fields.Datetime.now()

        tz = pytz.timezone(self.waj_tz or 'UTC')
        if isinstance(date, datetime):
            if date.tzinfo is None:
                date = pytz.utc.localize(date)
            local = date.astimezone(tz)
            check_hours = True
        elif isinstance(date, date_type):
            local = date
            check_hours = False
        else:
            return True

        if not self[WEEKDAY_FIELDS[local.weekday()]]:
            return False
        if not check_hours:
            return True

        hour = local.hour + local.minute / 60.0 + local.second / 3600.0
        return self.waj_hour_from <= hour < self.waj_hour_to

    # ------------------------------------------------------------------
    # Point of Sale
    # ------------------------------------------------------------------

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + [
            'waj_time_restricted', 'waj_hour_from', 'waj_hour_to', 'waj_tz', *WEEKDAY_FIELDS,
        ]
