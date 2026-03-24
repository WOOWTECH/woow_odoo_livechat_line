# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class LineGuestLinkPartnerWizard(models.TransientModel):
    """Wizard to link LINE guest to a partner."""
    _name = 'line.guest.link.partner.wizard'
    _description = 'Link LINE Guest to Partner'

    guest_id = fields.Many2one(
        'mail.guest',
        string='Guest',
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
    )

    def action_link(self):
        """Link the guest to the selected partner.

        Also syncs the LINE User ID to the partner for future use
        (e.g. sending LINE messages from Odoo contact).
        """
        self.ensure_one()
        self.guest_id.write({
            'line_partner_id': self.partner_id.id,
            'name': self.partner_id.name,
        })
        # Sync LINE User ID to the partner
        if self.guest_id.line_user_id and not self.partner_id.line_user_id:
            self.partner_id.write({
                'line_user_id': self.guest_id.line_user_id,
            })
        return {'type': 'ir.actions.act_window_close'}
