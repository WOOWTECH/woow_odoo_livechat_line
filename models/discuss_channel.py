# Part of Odoo. See LICENSE file for full copyright and licensing details.

import html
import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Block-level closing tags that should become a line break instead of just
# vanishing, so multi-line templates (e.g. appointment reminders) don't get
# smashed into one run-on line when converted to LINE plain text.
_BLOCK_CLOSE_RE = re.compile(r'</(?:p|div|li|ul|ol|h[1-6]|tr|table|blockquote|section|article)\s*>',
                              re.IGNORECASE)
_LI_OPEN_RE = re.compile(r'<li[^>]*>', re.IGNORECASE)
_BR_RE = re.compile(r'<br\s*/?>', re.IGNORECASE)
_TAG_RE = re.compile(r'<[^>]+>')
_MULTI_BLANK_RE = re.compile(r'\n{3,}')


class DiscussChannel(models.Model):
    """Extend Discuss channel to add LINE user association."""
    _inherit = 'discuss.channel'

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

    def _post_line_delivery_failure(self, reason):
        """Post a visible warning in the channel when a reply failed to reach LINE.

        Without this, the operator sees their message posted normally in
        Discuss and assumes it reached the customer, with no signal that it
        didn't (access token failure, blocked/unfollowed user, LINE API
        error, ...). Uses from_line_webhook=True so this system notice
        doesn't itself get treated as an operator reply and relayed back
        out to LINE (see mail_message.py's create() override).

        Args:
            reason: str, human-readable failure reason to show operators.
        """
        self.ensure_one()
        try:
            self.with_context(from_line_webhook=True).message_post(
                body=f'⚠️ 這則訊息未能送達 LINE：{reason}',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        except Exception:
            _logger.exception('LINE: Failed to post delivery-failure notice to channel %s', self.id)

    def _notify_line_user(self, message):
        """Send message to LINE user.

        Args:
            message: mail.message record.
        """
        self.ensure_one()
        if not self.line_user_id or not self.livechat_channel_id:
            return

        # sudo(): line_channel_id/line_channel_secret are restricted to
        # im_livechat.im_livechat_group_manager (see B-1). This method runs
        # for any operator replying in Discuss (typically Live Chat / User,
        # not a manager), so without sudo() here get_access_token() below
        # would always receive empty credentials and every reply would
        # silently fail to reach LINE.
        livechat_channel = self.livechat_channel_id.sudo()
        if not livechat_channel.line_enabled:
            return

        line_api = self.env['line.api.service']

        # Get access token
        access_token = line_api.get_access_token(
            channel_id=livechat_channel.line_channel_id,
            channel_secret=livechat_channel.line_channel_secret,
        )
        if not access_token:
            _logger.error('LINE: Failed to get access token for channel %s', livechat_channel.id)
            self._post_line_delivery_failure('無法取得 LINE Access Token，請確認 LINE Channel ID / Secret 設定是否正確。')
            return

        # Build messages
        messages = []

        # Process text content
        body = message.body or ''
        text = self._line_html_to_text(body)
        if text:
            messages.append(line_api.build_text_message(text))

        # Get base URL for attachments
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # Process attachments
        for attachment in message.attachment_ids:
            mimetype = attachment.mimetype or ''

            # Ensure attachment has access_token for public URL access
            # Odoo doesn't auto-generate access_token, we need to call generate_access_token()
            if not attachment.access_token:
                attachment.sudo().generate_access_token()
                _logger.info('LINE: Generated access_token for attachment id=%s', attachment.id)

            att_token = attachment.access_token
            _logger.info('LINE: Processing attachment id=%s, name=%s, mimetype=%s, access_token=%s',
                        attachment.id, attachment.name, mimetype, att_token[:10] if att_token else 'None')

            if mimetype.startswith('image/'):
                # Image message - use /web/image/ endpoint for better compatibility
                image_url = f'{base_url}/web/image/{attachment.id}?access_token={att_token}'
                image_url = self._ensure_https_url(image_url)
                if image_url:
                    _logger.info('LINE: Sending image URL=%s', image_url)
                    messages.append(line_api.build_image_message(image_url))
                else:
                    _logger.warning('LINE: Cannot send image - URL must be HTTPS')
                    # Fallback: send as text link
                    messages.append(line_api.build_text_message(
                        f'Image: {attachment.name}\n{base_url}/web/image/{attachment.id}'
                    ))

            elif mimetype.startswith('video/'):
                # Video message - needs preview image
                video_url = f'{base_url}/web/content/{attachment.id}?access_token={att_token}'
                video_url = self._ensure_https_url(video_url)
                if video_url:
                    # Use a default preview - use first frame or static image
                    preview_url = f'{base_url}/woow_odoo_livechat_line/static/img/video_preview.png'
                    preview_url = self._ensure_https_url(preview_url) or video_url
                    _logger.info('LINE: Sending video URL=%s, preview=%s', video_url, preview_url)
                    messages.append(line_api.build_video_message(video_url, preview_url))
                else:
                    _logger.warning('LINE: Cannot send video - URL must be HTTPS')
                    messages.append(line_api.build_text_message(
                        f'Video: {attachment.name}\n{base_url}/web/content/{attachment.id}'
                    ))

            elif mimetype.startswith('audio/'):
                # Audio message - estimate duration (LINE requires it)
                audio_url = f'{base_url}/web/content/{attachment.id}?access_token={att_token}'
                audio_url = self._ensure_https_url(audio_url)
                if audio_url:
                    duration_ms = 60000  # Default 60 seconds
                    _logger.info('LINE: Sending audio URL=%s', audio_url)
                    messages.append(line_api.build_audio_message(audio_url, duration_ms))
                else:
                    _logger.warning('LINE: Cannot send audio - URL must be HTTPS')
                    messages.append(line_api.build_text_message(
                        f'Audio: {attachment.name}\n{base_url}/web/content/{attachment.id}'
                    ))

            else:
                # Other files - send as Flex Message card (similar to LINE official style)
                file_url = f'{base_url}/web/content/{attachment.id}?access_token={att_token}&download=true'
                file_url = self._ensure_https_url(file_url)

                _logger.info('LINE: Sending file as Flex Message card, name=%s, url=%s', attachment.name, file_url)
                messages.append(line_api.build_file_message(
                    attachment.name,
                    file_url,
                    attachment.file_size
                ))

        # Send messages to LINE (max 5 messages per push)
        if messages:
            # LINE allows max 5 messages per push request
            for i in range(0, len(messages), 5):
                batch = messages[i:i + 5]
                # Call _push_message_raw() directly instead of the public
                # push_message() wrapper: same HTTP request, but it also
                # gives us the status code so the failure notice below can
                # say something more useful than "it failed".
                success, status_code, _resp_text = line_api._push_message_raw(
                    access_token, self.line_user_id, batch,
                )
                if success:
                    _logger.info('LINE: Sent %s messages to user %s', len(batch), self.line_user_id)
                else:
                    _logger.error('LINE: Failed to send messages to user %s', self.line_user_id)
                    self._post_line_delivery_failure(
                        f'LINE API 回應失敗（HTTP {status_code}）。' if status_code
                        else 'LINE API 無回應（網路錯誤）。'
                    )

    def _line_html_to_text(self, body):
        """Convert a mail.message HTML body into LINE-friendly plain text.

        A naive tag-strip (the previous implementation) drops block
        boundaries entirely, so e.g. `<div>A<br/>B</div>` becomes "AB" and
        multi-line templates like appointment reminders collapse into one
        unreadable run-on line. This converts block-ending tags and <br>
        into real newlines first, turns <li> into a bullet, THEN strips
        the remaining tags and unescapes HTML entities (so "A &amp; B"
        becomes "A & B" instead of staying escaped).

        Args:
            body: str, HTML body from mail.message.

        Returns:
            str: plain text with real line breaks, suitable for a LINE
            text message.
        """
        if not body:
            return ''
        text = _BR_RE.sub('\n', body)
        text = _LI_OPEN_RE.sub('• ', text)
        text = _BLOCK_CLOSE_RE.sub('\n', text)
        text = _TAG_RE.sub('', text)
        text = html.unescape(text)
        text = '\n'.join(line.strip() for line in text.split('\n'))
        text = _MULTI_BLANK_RE.sub('\n\n', text)
        return text.strip()

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
