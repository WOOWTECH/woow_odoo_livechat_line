# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..tools.line_text import html_to_line_text, split_line_text

_logger = logging.getLogger(__name__)

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
    line_processed_message_ids = fields.Text(
        default='[]',
        help='JSON list of recently processed LINE message.id values for '
             'this conversation, most-recent last. Used to make webhook '
             'redelivery idempotent — see _line_try_claim_message.',
    )

    # The fields that make a channel "a LINE conversation". Whoever can set
    # them can make Odoo push messages to any LINE user id through the
    # official account (see _notify_line_user, which uses sudo() for the
    # credentials). Core gives every internal user create/write on
    # discuss.channel, so only trusted code (sudo, e.g. the webhook) and
    # Live Chat managers may set them.
    _LINE_PROTECTED_FIELDS = frozenset((
        'line_user_id', 'line_display_name', 'line_picture_url',
        'line_processed_message_ids',
    ))

    def _line_check_protected_fields(self, vals_list):
        if self.env.su or self.env.user.has_group('im_livechat.im_livechat_group_manager'):
            return
        for vals in vals_list:
            if self._LINE_PROTECTED_FIELDS & set(vals):
                raise AccessError(_('Only Live Chat managers can change LINE conversation fields.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._line_check_protected_fields(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._line_check_protected_fields([vals])
        return super().write(vals)

    # Bounded so this column does not grow forever on a long-lived
    # conversation; LINE redelivers shortly after the original attempt, so
    # remembering this many recent ids is far more than redelivery needs.
    _LINE_PROCESSED_IDS_LIMIT = 200

    def _line_try_claim_message(self, line_message_id):
        """Atomically check whether `line_message_id` was already processed
        for this channel, and if not, record it.

        LINE redelivers webhook events on network hiccups (and via the
        "Webhook redelivery" console toggle) using the same message.id. A
        plain read-then-write dedup check races: two concurrent deliveries
        of the same event can both read "not seen yet" before either
        writes, and both go on to create a message. Locking this channel's
        row with SELECT ... FOR UPDATE serializes concurrent calls: the
        second call blocks until the first transaction's write commits,
        then correctly observes the id as already claimed.

        Args:
            line_message_id: str, LINE's message.id for this event.

        Returns:
            bool: True if this call claimed the id (caller should process
            the message), False if it was already processed (caller
            should skip it — this is a redelivery).
        """
        self.ensure_one()
        self.env.cr.execute(
            'SELECT line_processed_message_ids FROM discuss_channel '
            'WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        raw = row[0] if row else None
        processed = json.loads(raw) if raw else []
        if line_message_id in processed:
            return False
        processed.append(line_message_id)
        processed = processed[-self._LINE_PROCESSED_IDS_LIMIT:]
        self.env.cr.execute(
            'UPDATE discuss_channel SET line_processed_message_ids = %s WHERE id = %s',
            (json.dumps(processed), self.id),
        )
        return True

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
        # LINE rejects a text message over 5,000 characters: send long
        # replies as several messages (pushed 5 per request below).
        for chunk in split_line_text(text):
            messages.append(line_api.build_text_message(chunk))

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
            _logger.info('LINE: Processing attachment id=%s, mimetype=%s', attachment.id, mimetype)

            if mimetype.startswith('image/'):
                # Image message - use /web/image/ endpoint for better compatibility
                image_url = f'{base_url}/web/image/{attachment.id}?access_token={att_token}'
                image_url = self._ensure_https_url(image_url)
                if image_url:
                    _logger.info('LINE: Sending image attachment id=%s', attachment.id)
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
                    _logger.info('LINE: Sending video attachment id=%s', attachment.id)
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
                    _logger.info('LINE: Sending audio attachment id=%s', attachment.id)
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

                _logger.info('LINE: Sending file attachment id=%s as Flex Message card', attachment.id)
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
        """Convert a mail.message HTML body into LINE plain text.

        See tools/line_text.py: line breaks for <br> and blocks, list
        bullets/numbers, one line per table row (cells joined by "｜"),
        external link addresses kept next to their text, entities
        unescaped once.

        Args:
            body: str, HTML body from mail.message.

        Returns:
            str: plain text suitable for a LINE text message.
        """
        return html_to_line_text(body)

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
