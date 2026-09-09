# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
        groups='im_livechat.im_livechat_group_manager',
        help='Channel ID from LINE Developers Console.',
    )
    line_channel_secret = fields.Char(
        string='LINE Channel Secret',
        groups='im_livechat.im_livechat_group_manager',
        help='Channel Secret from LINE Developers Console.',
    )
    line_webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_line_webhook_url',
        help='Configure this URL in LINE Developers Console.',
    )

    @api.constrains('line_enabled', 'line_channel_id', 'line_channel_secret')
    def _check_line_config(self):
        """Validate LINE configuration when enabled."""
        for record in self:
            # sudo(): line_channel_id/line_channel_secret are restricted to
            # im_livechat.im_livechat_group_manager (see B-1). Any Live Chat
            # / User with write access to this record (not just managers)
            # can trigger this constrain, so reading the restricted fields
            # without sudo() would raise AccessError instead of the
            # intended ValidationError.
            record_sudo = record.sudo()
            if record_sudo.line_enabled:
                if not record_sudo.line_channel_id:
                    raise ValidationError(
                        "LINE Channel ID is required when LINE integration is enabled."
                    )
                if not record_sudo.line_channel_secret:
                    raise ValidationError(
                        "LINE Channel Secret is required when LINE integration is enabled."
                    )

    def _compute_line_webhook_url(self):
        """Compute the webhook URL for LINE integration."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.id:
                record.line_webhook_url = f'{base_url}/line/webhook/{record.id}'
            else:
                record.line_webhook_url = False
