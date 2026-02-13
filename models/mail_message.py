# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    """Extend mail.message to send replies to LINE."""
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to send message to LINE when operator replies."""
        messages = super().create(vals_list)

        for message in messages:
            # Only process messages from operators (not from guests)
            if not message.author_guest_id and message.author_id:
                self._send_to_line_if_applicable(message)

        return messages

    def _send_to_line_if_applicable(self, message):
        """Send message to LINE if applicable.

        Args:
            message: mail.message record.
        """
        # Check if message is in a discuss.channel
        if message.model != 'discuss.channel' or not message.res_id:
            return

        discuss_channel = self.env['discuss.channel'].sudo().browse(message.res_id)
        if not discuss_channel.exists():
            return

        # Check if this is a LINE conversation
        if not discuss_channel.line_user_id:
            return

        # Send to LINE
        try:
            discuss_channel._notify_line_user(message)
        except Exception as e:
            _logger.error('LINE: Error sending message to LINE: %s', e)
