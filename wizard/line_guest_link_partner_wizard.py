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

        Also creates/binds a line.user record in woow_line_base to maintain
        the LINE identity linked to the partner.
        """
        self.ensure_one()
        self.guest_id.write({
            'line_partner_id': self.partner_id.id,
            'name': self.partner_id.name,
        })
        # Create or bind line.user record for this partner
        if self.guest_id.line_user_id:
            LineUser = self.env['line.user'].sudo()
            line_user = LineUser.search(
                [('line_user_id', '=', self.guest_id.line_user_id)], limit=1,
            )
            if line_user:
                # Update existing line.user to point to this partner
                if line_user.partner_id != self.partner_id:
                    line_user.bind_partner(self.partner_id.id)
            else:
                # Create new line.user record — skip auto-bind since we
                # already know the target partner
                LineUser.with_context(
                    skip_auto_bind=True,
                ).create_or_update_from_webhook(
                    self.guest_id.line_user_id,
                    {'displayName': self.partner_id.name},
                )
                line_user = LineUser.search(
                    [('line_user_id', '=', self.guest_id.line_user_id)], limit=1,
                )
                if line_user:
                    line_user.bind_partner(self.partner_id.id)

        return {'type': 'ir.actions.act_window_close'}
