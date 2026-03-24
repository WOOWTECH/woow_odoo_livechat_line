# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MailGuest(models.Model):
    """Extend mail guest to add LINE user ID."""
    _inherit = 'mail.guest'

    line_user_id = fields.Char(
        string='LINE User ID',
        index=True,
        help='LINE User ID for this guest.',
    )
    line_partner_id = fields.Many2one(
        'res.partner',
        string='Linked Contact',
        help='Contact linked to this LINE user.',
    )

    _sql_constraints = [
        ('line_user_id_unique', 'unique(line_user_id)',
         'A guest with this LINE User ID already exists.'),
    ]

    def action_link_to_partner(self):
        """Open wizard to link guest to a partner."""
        self.ensure_one()
        return {
            'name': 'Link to Contact',
            'type': 'ir.actions.act_window',
            'res_model': 'line.guest.link.partner.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_guest_id': self.id,
            },
        }
