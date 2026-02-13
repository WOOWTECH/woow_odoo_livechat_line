# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    """Extend Discuss channel to add LINE user association."""
    _inherit = ['discuss.channel', 'line.api.mixin']
    _name = 'discuss.channel'

    line_user_id = fields.Char(
        string='LINE User ID',
        index=True,
        help='LINE User ID associated with this conversation.',
    )
    line_display_name = fields.Char(
        string='LINE Display Name',
        help='Display name from LINE profile.',
    )
    line_picture_url = fields.Char(
        string='LINE Picture URL',
        help='Profile picture URL from LINE.',
    )

    def _notify_line_user(self, message):
        """Send message to LINE user.

        Args:
            message: mail.message record.
        """
        self.ensure_one()
        if not self.line_user_id or not self.livechat_channel_id:
            return

        livechat_channel = self.livechat_channel_id
        if not livechat_channel.line_enabled:
            return

        # Get access token
        access_token = self._line_get_access_token(
            livechat_channel.line_channel_id,
            livechat_channel.line_channel_secret,
        )
        if not access_token:
            _logger.error('LINE: Failed to get access token for channel %s', livechat_channel.id)
            return

        # Build messages
        messages = []

        # Process text content
        body = message.body or ''
        # Strip HTML tags for LINE
        text = re.sub(r'<[^>]+>', '', body).strip()
        if text:
            messages.append(self._line_build_text_message(text))

        # Process attachments
        for attachment in message.attachment_ids:
            mimetype = attachment.mimetype or ''
            if mimetype.startswith('image/'):
                # Get public URL for image using access token
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                # Use access_token for public access without authentication
                image_url = f'{base_url}/web/image/{attachment.id}?access_token={attachment.access_token}'
                messages.append(self._line_build_image_message(image_url))

        # Send messages to LINE
        if messages:
            self._line_push_message(access_token, self.line_user_id, messages)
