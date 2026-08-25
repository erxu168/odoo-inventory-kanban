# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import timedelta
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

_logger = logging.getLogger(__name__)

# POS states that represent money actually taken.
SETTLED_POS_STATES = ('paid', 'done', 'invoiced')


class SalesEntry(models.Model):
    """The close-out record for one outlet on one business day.

    Figures on the left come from Point of Sale and are never typed in; the
    figures on the right are what the closing staff counted. The gap between
    the two is the whole point of the record.
    """
    _name = 'restaurant.sales.entry'
    _description = 'Daily Sales Entry'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    date = fields.Date(
        string='Business Day', required=True, index=True, tracking=True,
        default=fields.Date.context_today,
    )
    pos_config_id = fields.Many2one(
        'pos.config', string='Outlet', required=True, tracking=True,
        index=True, domain="[('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related='company_id.currency_id')
    user_id = fields.Many2one(
        'res.users', string='Closed By', tracking=True,
        default=lambda self: self.env.user,
        help="Person responsible for counting and submitting this day.",
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', required=True, tracking=True, index=True)
    color = fields.Integer(compute='_compute_color')

    # ── POS snapshot (written by the sync, read-only for humans) ──
    pos_synced_on = fields.Datetime(string='Last POS Sync', readonly=True)
    session_ids = fields.Many2many(
        'pos.session', string='POS Sessions', readonly=True,
    )
    session_count = fields.Integer(compute='_compute_session_count')
    pos_order_count = fields.Integer(string='Orders', readonly=True)
    pos_refund_count = fields.Integer(string='Refunds', readonly=True)
    pos_sales_total = fields.Monetary(
        string='POS Net Sales', readonly=True, tracking=True,
        help="Sum of settled POS orders for the business day, refunds "
             "included as negatives.",
    )
    pos_untaxed_total = fields.Monetary(string='POS Untaxed', readonly=True)
    pos_tax_total = fields.Monetary(string='POS Taxes', readonly=True)
    pos_refund_total = fields.Monetary(string='Refunded', readonly=True)
    pos_opening_float = fields.Monetary(string='Opening Float', readonly=True)
    pos_average_ticket = fields.Monetary(
        string='Average Ticket', compute='_compute_average_ticket', store=True,
    )

    # ── Declared figures ──────────────────────────────────────
    payment_line_ids = fields.One2many(
        'restaurant.sales.payment.line', 'entry_id', string='Payment Methods',
    )
    channel_line_ids = fields.One2many(
        'restaurant.sales.channel.line', 'entry_id', string='Other Channels',
    )

    pos_payment_total = fields.Monetary(
        string='Expected Takings', compute='_compute_payment_totals', store=True,
    )
    counted_total = fields.Monetary(
        string='Counted Takings', compute='_compute_payment_totals', store=True,
    )
    variance_total = fields.Monetary(
        string='Variance', compute='_compute_payment_totals', store=True,
        tracking=True,
    )
    cash_expected = fields.Monetary(
        compute='_compute_payment_totals', store=True,
    )
    cash_counted = fields.Monetary(
        compute='_compute_payment_totals', store=True,
    )
    cash_difference = fields.Monetary(
        string='Cash Variance', compute='_compute_payment_totals', store=True,
        tracking=True,
    )
    over_tolerance = fields.Boolean(
        string='Above Tolerance', compute='_compute_over_tolerance', store=True,
    )

    channel_gross_total = fields.Monetary(
        string='Channel Gross', compute='_compute_channel_totals', store=True,
    )
    channel_net_total = fields.Monetary(
        string='Channel Net', compute='_compute_channel_totals', store=True,
    )
    channel_order_count = fields.Integer(
        string='Channel Orders', compute='_compute_channel_totals', store=True,
    )
    total_revenue = fields.Monetary(
        string='Total Revenue', compute='_compute_total_revenue', store=True,
        tracking=True, help="POS net sales plus off-POS channel gross.",
    )

    variance_note = fields.Text(
        string='Variance Explanation',
        help="Required when the cash variance exceeds the outlet's tolerance.",
    )
    note = fields.Text(string='Shift Notes')

    approved_by_id = fields.Many2one('res.users', readonly=True, tracking=True)
    approved_on = fields.Datetime(readonly=True)
    rejection_reason = fields.Text(tracking=True)

    # ── Computes ──────────────────────────────────────────────

    @api.depends('pos_config_id', 'date')
    def _compute_name(self):
        for entry in self:
            if entry.pos_config_id and entry.date:
                entry.name = '%s — %s' % (
                    entry.pos_config_id.name,
                    fields.Date.to_string(entry.date),
                )
            else:
                entry.name = _('New Sales Entry')

    @api.depends('session_ids')
    def _compute_session_count(self):
        for entry in self:
            entry.session_count = len(entry.session_ids)

    @api.depends('pos_sales_total', 'pos_order_count', 'pos_refund_count')
    def _compute_average_ticket(self):
        for entry in self:
            tickets = entry.pos_order_count - entry.pos_refund_count
            entry.pos_average_ticket = (
                entry.pos_sales_total / tickets if tickets > 0 else 0.0
            )

    @api.depends(
        'payment_line_ids.pos_amount',
        'payment_line_ids.counted_amount',
        'payment_line_ids.is_cash',
    )
    def _compute_payment_totals(self):
        for entry in self:
            lines = entry.payment_line_ids
            cash_lines = lines.filtered('is_cash')
            entry.pos_payment_total = sum(lines.mapped('pos_amount'))
            entry.counted_total = sum(lines.mapped('counted_amount'))
            entry.variance_total = entry.counted_total - entry.pos_payment_total
            entry.cash_expected = sum(cash_lines.mapped('pos_amount'))
            entry.cash_counted = sum(cash_lines.mapped('counted_amount'))
            entry.cash_difference = entry.cash_counted - entry.cash_expected

    @api.depends('cash_difference', 'pos_config_id.sales_cash_tolerance')
    def _compute_over_tolerance(self):
        for entry in self:
            entry.over_tolerance = entry._is_over_tolerance()

    @api.depends(
        'channel_line_ids.gross_amount',
        'channel_line_ids.net_amount',
        'channel_line_ids.order_count',
    )
    def _compute_channel_totals(self):
        for entry in self:
            lines = entry.channel_line_ids
            entry.channel_gross_total = sum(lines.mapped('gross_amount'))
            entry.channel_net_total = sum(lines.mapped('net_amount'))
            entry.channel_order_count = sum(lines.mapped('order_count'))

    @api.depends('pos_sales_total', 'channel_gross_total')
    def _compute_total_revenue(self):
        for entry in self:
            entry.total_revenue = entry.pos_sales_total + entry.channel_gross_total

    @api.depends('state', 'over_tolerance')
    def _compute_color(self):
        for entry in self:
            if entry.state == 'rejected':
                entry.color = 1        # red
            elif entry.over_tolerance:
                entry.color = 2        # orange
            elif entry.state == 'approved':
                entry.color = 10       # green
            elif entry.state == 'submitted':
                entry.color = 4        # blue
            else:
                entry.color = 0

    # ── Constraints ───────────────────────────────────────────

    @api.constrains('date', 'pos_config_id')
    def _check_unique_day(self):
        for entry in self:
            if not entry.pos_config_id or not entry.date:
                continue
            duplicate = self.search_count([
                ('date', '=', entry.date),
                ('pos_config_id', '=', entry.pos_config_id.id),
                ('id', '!=', entry.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "%(outlet)s already has a sales entry for %(date)s.",
                    outlet=entry.pos_config_id.display_name,
                    date=fields.Date.to_string(entry.date),
                ))

    @api.constrains('date', 'pos_config_id', 'company_id')
    def _check_company(self):
        for entry in self:
            config_company = entry.pos_config_id.company_id
            if config_company and config_company != entry.company_id:
                raise ValidationError(_(
                    "%(outlet)s belongs to another company than this entry.",
                    outlet=entry.pos_config_id.display_name,
                ))

    @api.constrains('date')
    def _check_not_in_future(self):
        for entry in self:
            if entry.date and entry.date > entry._today():
                raise ValidationError(
                    _("A sales entry cannot be opened for a future day.")
                )

    # ── Helpers ───────────────────────────────────────────────

    def _today(self):
        """Today in the outlet's own business-day terms."""
        self.ensure_one()
        if self.pos_config_id:
            return self.pos_config_id._sales_current_business_date()
        return fields.Date.context_today(self)

    def _is_over_tolerance(self):
        self.ensure_one()
        tolerance = self.pos_config_id.sales_cash_tolerance or 0.0
        rounding = self.currency_id.rounding or 0.01
        return float_compare(
            abs(self.cash_difference), tolerance, precision_rounding=rounding,
        ) > 0

    def _editable_states(self):
        return ('draft', 'rejected')

    def _ensure_editable(self, action):
        for entry in self:
            if entry.state not in entry._editable_states():
                raise UserError(_(
                    "%(entry)s is %(state)s — %(action)s is no longer "
                    "possible. Reset it to draft first.",
                    entry=entry.display_name,
                    state=dict(self._fields['state'].selection)[entry.state],
                    action=action,
                ))

    # ── POS synchronisation ───────────────────────────────────

    def _collect_pos_data(self):
        """Read the outlet's POS activity for this business day.

        Returns a dict of totals plus ``payment_totals``, a mapping of
        ``pos.payment.method`` record -> amount taken.
        """
        self.ensure_one()
        config = self.pos_config_id
        start, end = config._sales_day_window(self.date)

        # sudo: staff closing a till are not granted POS back-office access,
        # but the figures they reconcile against must still be the real ones.
        Order = self.env['pos.order'].sudo()
        orders = Order.search([
            ('session_id.config_id', '=', config.id),
            ('date_order', '>=', start),
            ('date_order', '<', end),
            ('state', 'in', SETTLED_POS_STATES),
        ])
        sessions = self.env['pos.session'].sudo().search([
            ('config_id', '=', config.id),
            ('start_at', '>=', start),
            ('start_at', '<', end),
        ])
        sessions |= orders.mapped('session_id')

        refunds = orders.filtered(lambda o: o.amount_total < 0.0)
        payment_totals = defaultdict(float)
        for payment in self.env['pos.payment'].sudo().search(
            [('pos_order_id', 'in', orders.ids)]
        ):
            payment_totals[payment.payment_method_id] += payment.amount

        return {
            'session_ids': [(6, 0, sessions.ids)],
            'pos_order_count': len(orders),
            'pos_refund_count': len(refunds),
            'pos_sales_total': sum(orders.mapped('amount_total')),
            'pos_untaxed_total': sum(
                order.amount_total - order.amount_tax for order in orders
            ),
            'pos_tax_total': sum(orders.mapped('amount_tax')),
            'pos_refund_total': sum(refunds.mapped('amount_total')),
            'pos_opening_float': sum(
                sessions.mapped('cash_register_balance_start')
            ),
            'pos_synced_on': fields.Datetime.now(),
            'payment_totals': payment_totals,
        }

    def _payment_line_commands(self, payment_totals):
        """Reconcile payment lines with POS, keeping what staff already typed.

        Every method configured on the outlet gets a line, so a method that
        took nothing is visibly zero rather than quietly absent.
        """
        self.ensure_one()
        PaymentMethod = self.env['pos.payment.method']
        # Methods configured on the outlet plus any that actually took money,
        # so a method retired mid-day still shows up.
        methods = self.pos_config_id.payment_method_ids | PaymentMethod.browse(
            [method.id for method in payment_totals]
        )

        commands = []
        existing = {}
        for line in self.payment_line_ids:
            if line.payment_method_id in existing:
                # A duplicate should not exist, but never let one survive a sync.
                commands.append((2, line.id))
                continue
            existing[line.payment_method_id] = line

        kept = PaymentMethod.browse()
        for method, line in existing.items():
            if method not in methods and float_is_zero(
                line.counted_amount, precision_digits=2
            ):
                commands.append((2, line.id))
                continue
            # A method dropped from the outlet but carrying a declared amount
            # keeps its line, so the money does not vanish from the entry.
            kept |= method
            commands.append((1, line.id, {
                'pos_amount': payment_totals.get(method, 0.0),
            }))

        for method in methods - kept:
            commands.append((0, 0, {
                'payment_method_id': method.id,
                'pos_amount': payment_totals.get(method, 0.0),
            }))
        return commands

    def action_sync_pos(self):
        """Refresh the POS side of the entry. Counted amounts are untouched."""
        for entry in self:
            entry._ensure_editable(_("refreshing from Point of Sale"))
            data = entry._collect_pos_data()
            payment_totals = data.pop('payment_totals')
            data['payment_line_ids'] = entry._payment_line_commands(payment_totals)
            entry.write(data)
        return True

    # ── Workflow ──────────────────────────────────────────────

    def action_submit(self):
        for entry in self:
            entry._ensure_editable(_("submitting"))
            if not entry.payment_line_ids:
                raise UserError(_(
                    "Refresh %s from Point of Sale before submitting it — "
                    "there is nothing to reconcile yet.", entry.display_name,
                ))
            if entry.over_tolerance and not (entry.variance_note or '').strip():
                raise UserError(_(
                    "The cash variance of %(variance)s on %(entry)s is above "
                    "the outlet's tolerance of %(tolerance)s. Explain it "
                    "before submitting.",
                    variance=entry.cash_difference,
                    entry=entry.display_name,
                    tolerance=entry.pos_config_id.sales_cash_tolerance,
                ))
            entry.write({'state': 'submitted', 'rejection_reason': False})
            entry._notify_managers()
        return True

    def action_approve(self):
        for entry in self:
            if entry.state != 'submitted':
                raise UserError(_(
                    "Only a submitted entry can be approved; %(entry)s is "
                    "%(state)s.",
                    entry=entry.display_name,
                    state=dict(self._fields['state'].selection)[entry.state],
                ))
            entry.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_on': fields.Datetime.now(),
            })
            entry.activity_feedback(
                ['mail.mail_activity_data_todo'],
                feedback=_("Approved by %s", self.env.user.display_name),
            )
        return True

    def action_reject(self):
        for entry in self:
            if entry.state != 'submitted':
                raise UserError(_(
                    "Only a submitted entry can be sent back."
                ))
            if not (entry.rejection_reason or '').strip():
                raise UserError(_(
                    "Say what needs correcting in the rejection reason before "
                    "sending %s back.", entry.display_name,
                ))
            entry.state = 'rejected'
            entry.activity_feedback(
                ['mail.mail_activity_data_todo'],
                feedback=_("Sent back: %s", entry.rejection_reason),
            )
            if entry.user_id:
                entry.message_post(
                    body=_("Sent back for correction: %s", entry.rejection_reason),
                    partner_ids=entry.user_id.partner_id.ids,
                )
        return True

    def action_reset_draft(self):
        for entry in self:
            entry.write({
                'state': 'draft',
                'approved_by_id': False,
                'approved_on': False,
            })
        return True

    def action_view_sessions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('POS Sessions'),
            'res_model': 'pos.session',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.session_ids.ids)],
        }

    def _notify_managers(self):
        """Put the submitted entry on the outlet managers' to-do list."""
        self.ensure_one()
        managers = self.pos_config_id.sales_manager_ids
        if not managers:
            return
        summary = _('Approve daily sales — %s', self.display_name)
        for manager in managers:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=manager.id,
                summary=summary,
            )

    # ── Lifecycle ─────────────────────────────────────────────

    @api.onchange('pos_config_id')
    def _onchange_pos_config_id(self):
        for entry in self:
            if entry.pos_config_id.company_id:
                entry.company_id = entry.pos_config_id.company_id

    @api.model_create_multi
    def create(self, vals_list):
        entries = super().create(vals_list)
        for entry in entries:
            # A fresh entry with no POS figures is useless to the person
            # closing the till, so fill it in immediately.
            if not entry.pos_synced_on and entry.state in entry._editable_states():
                entry.action_sync_pos()
        return entries

    def write(self, vals):
        res = super().write(vals)
        # Moving an entry to another outlet or day makes its POS snapshot a
        # lie; refresh it rather than leaving stale figures on screen.
        if {'pos_config_id', 'date'} & vals.keys():
            editable = self.filtered(
                lambda e: e.state in e._editable_states()
            )
            if editable:
                editable.action_sync_pos()
        return res

    def unlink(self):
        for entry in self:
            if entry.state == 'approved':
                raise UserError(_(
                    "%s has been approved and is part of the books. Reset it "
                    "to draft first if it really must go.", entry.display_name,
                ))
        return super().unlink()

    # ── Scheduled actions ─────────────────────────────────────

    @api.model
    def _cron_generate_daily_entries(self):
        """Open yesterday's draft entry for every outlet that wants one."""
        configs = self.env['pos.config'].search([('sales_entry_required', '=', True)])
        for config in configs:
            business_date = config._sales_current_business_date() - timedelta(days=1)
            if self.search_count([
                ('pos_config_id', '=', config.id),
                ('date', '=', business_date),
            ]):
                continue
            try:
                self.with_company(config.company_id or self.env.company).create({
                    'date': business_date,
                    'pos_config_id': config.id,
                    'company_id': (config.company_id or self.env.company).id,
                    'user_id': False,
                })
            except Exception:
                # One misconfigured outlet must not stop the others.
                _logger.exception(
                    "Could not open the daily sales entry for %s on %s",
                    config.display_name, business_date,
                )
        return True

    @api.model
    def _cron_remind_pending(self, grace_days=1):
        """Chase entries still sitting in draft a day after the fact."""
        deadline = fields.Date.context_today(self) - timedelta(days=grace_days)
        pending = self.search([
            ('state', 'in', ('draft', 'rejected')),
            ('date', '<=', deadline),
        ])
        for entry in pending:
            recipients = entry.user_id or entry.pos_config_id.sales_manager_ids
            if not recipients:
                continue
            entry.message_post(
                body=_(
                    "The sales entry for %(date)s is still not submitted.",
                    date=fields.Date.to_string(entry.date),
                ),
                partner_ids=recipients.partner_id.ids,
            )
        return True
