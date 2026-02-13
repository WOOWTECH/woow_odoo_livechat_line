# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ImLivechatChannel(models.Model):
    """Extend LiveChat channel to add LINE configuration."""
    _inherit = 'im_livechat.channel'

    line_enabled = fields.Boolean(
        string='Enable LINE Integration',
        default=False,
        help='Enable LINE Messaging API integration for this channel.',
    )
    line_channel_id = fields.Char(
        string='LINE Channel ID',
        help='Channel ID from LINE Developers Console.',
    )
    line_channel_secret = fields.Char(
        string='LINE Channel Secret',
        help='Channel Secret from LINE Developers Console.',
    )
    line_webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_line_webhook_url',
        help='Configure this URL in LINE Developers Console.',
    )

    def _compute_line_webhook_url(self):
        """Compute the webhook URL for LINE integration."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.id:
                record.line_webhook_url = f'{base_url}/line/webhook/{record.id}'
            else:
                record.line_webhook_url = False
