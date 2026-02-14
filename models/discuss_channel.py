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

        # Get base URL for attachments
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # Process attachments
        for attachment in message.attachment_ids:
            mimetype = attachment.mimetype or ''

            _logger.info('LINE: Processing attachment id=%s, name=%s, mimetype=%s, access_token=%s',
                        attachment.id, attachment.name, mimetype, attachment.access_token[:10] if attachment.access_token else 'None')

            if mimetype.startswith('image/'):
                # Image message - use /web/image/ endpoint for better compatibility
                image_url = f'{base_url}/web/image/{attachment.id}?access_token={attachment.access_token}'
                image_url = self._ensure_https_url(image_url)
                if image_url:
                    _logger.info('LINE: Sending image URL=%s', image_url)
                    messages.append(self._line_build_image_message(image_url))
                else:
                    _logger.warning('LINE: Cannot send image - URL must be HTTPS')
                    # Fallback: send as text link
                    messages.append(self._line_build_text_message(
                        f'🖼️ Image: {attachment.name}\n{base_url}/web/image/{attachment.id}'
                    ))

            elif mimetype.startswith('video/'):
                # Video message - needs preview image
                video_url = f'{base_url}/web/content/{attachment.id}?access_token={attachment.access_token}'
                video_url = self._ensure_https_url(video_url)
                if video_url:
                    # Use a default preview
                    preview_url = f'{base_url}/woow_odoo_livechat_line/static/img/video_preview.svg'
                    preview_url = self._ensure_https_url(preview_url) or video_url
                    _logger.info('LINE: Sending video URL=%s, preview=%s', video_url, preview_url)
                    messages.append(self._line_build_video_message(video_url, preview_url))
                else:
                    _logger.warning('LINE: Cannot send video - URL must be HTTPS')
                    messages.append(self._line_build_text_message(
                        f'🎬 Video: {attachment.name}\n{base_url}/web/content/{attachment.id}'
                    ))

            elif mimetype.startswith('audio/'):
                # Audio message - estimate duration (LINE requires it)
                audio_url = f'{base_url}/web/content/{attachment.id}?access_token={attachment.access_token}'
                audio_url = self._ensure_https_url(audio_url)
                if audio_url:
                    duration_ms = 60000  # Default 60 seconds
                    _logger.info('LINE: Sending audio URL=%s', audio_url)
                    messages.append(self._line_build_audio_message(audio_url, duration_ms))
                else:
                    _logger.warning('LINE: Cannot send audio - URL must be HTTPS')
                    messages.append(self._line_build_text_message(
                        f'🎵 Audio: {attachment.name}\n{base_url}/web/content/{attachment.id}'
                    ))

            else:
                # Other files - send as text link with download URL
                # Flex Message may have compatibility issues, use simple text instead
                file_url = f'{base_url}/web/content/{attachment.id}?access_token={attachment.access_token}&download=true'
                file_url = self._ensure_https_url(file_url)

                # Format file size
                size_text = ''
                if attachment.file_size:
                    if attachment.file_size < 1024:
                        size_text = f' ({attachment.file_size} B)'
                    elif attachment.file_size < 1024 * 1024:
                        size_text = f' ({attachment.file_size // 1024} KB)'
                    else:
                        size_text = f' ({attachment.file_size // (1024 * 1024)} MB)'

                _logger.info('LINE: Sending file as text link, name=%s, url=%s', attachment.name, file_url)
                messages.append(self._line_build_text_message(
                    f'📎 {attachment.name}{size_text}\n{file_url}'
                ))

        # Send messages to LINE (max 5 messages per push)
        if messages:
            # LINE allows max 5 messages per push request
            for i in range(0, len(messages), 5):
                batch = messages[i:i + 5]
                success = self._line_push_message(access_token, self.line_user_id, batch)
                if success:
                    _logger.info('LINE: Sent %s messages to user %s', len(batch), self.line_user_id)
                else:
                    _logger.error('LINE: Failed to send messages to user %s', self.line_user_id)

    def _ensure_https_url(self, url):
        """Ensure URL uses HTTPS protocol.

        LINE Messaging API requires HTTPS URLs for media content.

        Args:
            url: URL to check.

        Returns:
            str: HTTPS URL or None if conversion not possible.
        """
        if not url:
            return None
        if url.startswith('https://'):
            return url
        if url.startswith('http://'):
            # Try to convert to HTTPS
            return 'https://' + url[7:]
        return None
