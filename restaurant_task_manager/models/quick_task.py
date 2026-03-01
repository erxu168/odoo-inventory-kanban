# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class QuickTask(models.Model):
    """Ad-hoc task created by a manager during a live shift.
    Not template-based — one-off instructions for specific employees."""
    _name = 'restaurant.quick.task'
    _description = 'Quick Task (Ad-hoc)'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(string='Task', required=True, tracking=True)
    description = fields.Text(string='Details')
    employee_id = fields.Many2one(
        'hr.employee', string='Assigned To', required=True, tracking=True,
    )
    assigned_by_id = fields.Many2one(
        'hr.employee', string='Assigned By',
        default=lambda self: self.env.user.employee_id,
        readonly=True,
    )
    location_id = fields.Many2one('hr.work.location', string='Location')
    deadline = fields.Datetime(string='Due By')
    completion_type = fields.Selection([
        ('checkbox', 'Simple Checkbox'),
        ('photo', 'Photo (Camera)'),
        ('text', 'Text Note'),
    ], default='checkbox', required=True)

    # Proof
    proof_photo = fields.Binary(string='Proof Photo', attachment=True)
    proof_photo_filename = fields.Char()
    proof_text_note = fields.Text(string='Completion Note')
    staff_comment = fields.Text(string='Staff Comment')

    # Status
    state = fields.Selection([
        ('assigned', 'Assigned'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='assigned', tracking=True)
    completed_at = fields.Datetime(readonly=True)
    is_overdue = fields.Boolean(compute='_compute_is_overdue')

    @api.depends('deadline', 'state')
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_overdue = (
                rec.deadline and rec.state == 'assigned' and rec.deadline < now
            )

    def action_complete(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.completion_type == 'photo' and not rec.proof_photo:
                raise ValidationError(_(
                    'Quick task "%s" requires a photo.', rec.name
                ))
            if rec.completion_type == 'text' and not rec.proof_text_note:
                raise ValidationError(_(
                    'Quick task "%s" requires a text note.', rec.name
                ))
            rec.write({'state': 'done', 'completed_at': now})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reopen(self):
        self.write({
            'state': 'assigned',
            'completed_at': False,
            'proof_photo': False,
            'proof_photo_filename': False,
            'proof_text_note': False,
        })
