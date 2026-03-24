# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    """Extend res.partner to add LINE user ID."""
    _inherit = 'res.partner'

    line_user_id = fields.Char(
        string='LINE User ID',
        index=True,
        copy=False,
        help='Unique LINE User ID linked to this contact.',
    )

    _sql_constraints = [
        ('line_user_id_unique', 'unique(line_user_id)',
         'A contact with this LINE User ID already exists.'),
    ]
