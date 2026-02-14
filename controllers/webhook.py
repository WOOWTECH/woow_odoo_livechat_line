# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import hashlib
import hmac
import json
import logging

from markupsafe import escape

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class LineWebhookController(http.Controller):
    """Controller for LINE Messaging API webhook."""

    @http.route(
        '/line/webhook/<int:channel_id>',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def line_webhook(self, channel_id, **kwargs):
        """Handle LINE webhook events.

        Args:
            channel_id: The LiveChat channel ID.

        Returns:
            dict: Empty dict on success (LINE expects 200 OK).
        """
        _logger.info('LINE webhook: Received request for channel_id=%s', channel_id)
        _logger.info('LINE webhook: Headers=%s', dict(request.httprequest.headers))

        livechat_channel = request.env['im_livechat.channel'].sudo().browse(channel_id)
        if not livechat_channel.exists() or not livechat_channel.line_enabled:
            _logger.warning('LINE webhook: Invalid or disabled channel %s', channel_id)
            return {}

        # Verify LINE signature
        body = request.httprequest.get_data(as_text=True)
        signature = request.httprequest.headers.get('X-Line-Signature', '')

        _logger.info('LINE webhook: Body length=%s, signature=%s', len(body), signature[:20] if signature else 'None')

        if not self._verify_signature(body, signature, livechat_channel.line_channel_secret):
            _logger.warning('LINE webhook: Invalid signature for channel %s', channel_id)
            _logger.warning('LINE webhook: Body=%s', body[:200] if body else 'None')
            return {}

        # Process events
        data = json.loads(body)
        events = data.get('events', [])

        for event in events:
            try:
                self._process_event(event, livechat_channel)
            except Exception:
                _logger.exception('LINE webhook [%s]: Error processing event', channel_id)

        return {}

    def _verify_signature(self, body, signature, channel_secret):
        """Verify LINE webhook signature using HMAC-SHA256.

        Args:
            body: Request body as string.
            signature: X-Line-Signature header value.
            channel_secret: LINE Channel Secret.

        Returns:
            bool: True if signature is valid.
        """
        if not channel_secret or not signature:
            return False

        hash_value = hmac.new(
            channel_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256,
        ).digest()
        expected_signature = base64.b64encode(hash_value).decode('utf-8')

        return hmac.compare_digest(signature, expected_signature)

    def _process_event(self, event, livechat_channel):
        """Process a single LINE event.

        Args:
            event: LINE event dict.
            livechat_channel: im_livechat.channel record.
        """
        event_type = event.get('type')

        if event_type == 'message':
            self._handle_message_event(event, livechat_channel)
        elif event_type == 'follow':
            _logger.info('LINE webhook: User followed channel')
        elif event_type == 'unfollow':
            _logger.info('LINE webhook: User unfollowed channel')
        else:
            _logger.debug('LINE webhook: Unhandled event type: %s', event_type)

    def _handle_message_event(self, event, livechat_channel):
        """Handle LINE message event.

        Args:
            event: LINE message event dict.
            livechat_channel: im_livechat.channel record.
        """
        source = event.get('source', {})
        line_user_id = source.get('userId')

        if not line_user_id:
            _logger.warning('LINE webhook: Message without user ID')
            return

        message = event.get('message', {})
        message_type = message.get('type')
        reply_token = event.get('replyToken')

        # Find or create guest
        guest = self._get_or_create_guest(line_user_id, livechat_channel)

        # Find or create discuss channel
        discuss_channel = self._get_or_create_discuss_channel(
            line_user_id, guest, livechat_channel
        )

        if not discuss_channel:
            _logger.error('LINE webhook: Failed to create discuss channel for user %s', line_user_id)
            return

        # Process message based on type
        self._create_message(message, message_type, discuss_channel, guest, livechat_channel)

    def _get_or_create_guest(self, line_user_id, livechat_channel):
        """Get or create a mail.guest record for LINE user.

        Args:
            line_user_id: LINE User ID.
            livechat_channel: im_livechat.channel record.

        Returns:
            mail.guest record.
        """
        Guest = request.env['mail.guest'].sudo()

        guest = Guest.search([('line_user_id', '=', line_user_id)], limit=1)
        if not guest:
            guest = Guest.create({
                'name': f'LINE User',
                'line_user_id': line_user_id,
            })

        return guest

    def _get_or_create_discuss_channel(self, line_user_id, guest, livechat_channel):
        """Get or create a discuss.channel for LINE conversation.

        Args:
            line_user_id: LINE User ID.
            guest: mail.guest record.
            livechat_channel: im_livechat.channel record.

        Returns:
            discuss.channel record.
        """
        DiscussChannel = request.env['discuss.channel'].sudo()

        # Search for existing channel with this LINE user
        discuss_channel = DiscussChannel.search([
            ('line_user_id', '=', line_user_id),
            ('livechat_channel_id', '=', livechat_channel.id),
        ], limit=1)

        if not discuss_channel:
            # Get channel values using Odoo 18 API
            channel_vals = livechat_channel._get_livechat_discuss_channel_vals(
                anonymous_name=guest.name,
                previous_operator_id=None,
                chatbot_script=None,
                user_id=None,
                country_id=None,
            )

            if not channel_vals:
                _logger.warning('LINE webhook: No available operator for channel %s', livechat_channel.id)
                # Get first operator from the livechat channel as fallback
                fallback_operator = livechat_channel.user_ids[:1]
                if not fallback_operator:
                    _logger.error('LINE webhook: No operators configured for channel %s', livechat_channel.id)
                    return None

                operator_partner_id = fallback_operator.partner_id.id
                channel_vals = {
                    'channel_type': 'livechat',
                    'livechat_channel_id': livechat_channel.id,
                    'livechat_active': True,
                    'livechat_operator_id': operator_partner_id,
                    'anonymous_name': guest.name,
                    'name': f'LINE: {guest.name}',
                    'channel_member_ids': [
                        (0, 0, {'partner_id': operator_partner_id}),
                    ],
                }

            # Create the discuss channel
            discuss_channel = DiscussChannel.with_context(
                mail_create_nosubscribe=False
            ).create(channel_vals)

            # Add LINE user ID
            discuss_channel.write({
                'line_user_id': line_user_id,
            })

            # Add guest to channel members
            discuss_channel.add_members(guest_ids=[guest.id])

            # Broadcast to operator to notify them of new conversation
            if discuss_channel.livechat_operator_id:
                discuss_channel._broadcast([discuss_channel.livechat_operator_id.id])

            _logger.info('LINE webhook: Created new discuss channel %s for LINE user %s',
                        discuss_channel.id, line_user_id)

        return discuss_channel

    def _create_message(self, message, message_type, discuss_channel, guest, livechat_channel):
        """Create mail.message from LINE message.

        Args:
            message: LINE message dict.
            message_type: LINE message type.
            discuss_channel: discuss.channel record.
            guest: mail.guest record.
            livechat_channel: im_livechat.channel record.
        """
        body = ''
        attachment_ids = []
        message_id = message.get('id')

        if message_type == 'text':
            body = message.get('text', '')

        elif message_type in ('image', 'video', 'audio', 'file'):
            # Download content from LINE
            attachment = self._download_line_content(
                message_id, message_type, message, livechat_channel
            )
            if attachment:
                attachment_ids = [attachment.id]
                if message_type == 'image':
                    body = ''  # Image will be shown as attachment
                elif message_type == 'video':
                    body = '[Video]'
                elif message_type == 'audio':
                    body = '[Audio]'
                elif message_type == 'file':
                    body = ''  # File will be shown as attachment
            else:
                body = f'[{message_type.capitalize()} - download failed]'

        elif message_type == 'sticker':
            sticker_id = message.get('stickerId')
            package_id = message.get('packageId')
            body = f'[Sticker: {package_id}/{sticker_id}]'

        elif message_type == 'location':
            # Escape user-provided content to prevent XSS
            title = escape(message.get('title', ''))
            address = escape(message.get('address', ''))
            latitude = message.get('latitude')
            longitude = message.get('longitude')
            maps_url = f'https://www.google.com/maps?q={latitude},{longitude}'
            body = f'📍 {title}<br/>{address}<br/><a href="{maps_url}">View on Google Maps</a>'

        else:
            body = f'[Unsupported message type: {message_type}]'

        if body or attachment_ids:
            _logger.info('LINE webhook: Posting message to channel %s, body=%s, attachments=%s',
                        discuss_channel.id, body[:50] if body else '', attachment_ids)
            # Use context flag to prevent sending message back to LINE
            # Remove mail_create_nosubscribe to allow bus notifications
            posted_message = discuss_channel.with_context(
                from_line_webhook=True,  # Prevent message loop
            ).message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_guest_id=guest.id,
                attachment_ids=attachment_ids,
            )
            _logger.info('LINE webhook: Message posted successfully, id=%s', posted_message.id)

    def _download_line_content(self, message_id, message_type, message, livechat_channel):
        """Download content from LINE and create attachment.

        Args:
            message_id: LINE message ID.
            message_type: LINE message type.
            message: LINE message dict.
            livechat_channel: im_livechat.channel record.

        Returns:
            ir.attachment record or None.
        """
        _logger.info('LINE webhook: Starting content download for message_id=%s, type=%s',
                    message_id, message_type)

        # Get access token
        access_token = livechat_channel._line_get_access_token(
            livechat_channel.line_channel_id,
            livechat_channel.line_channel_secret,
        )
        if not access_token:
            _logger.error('LINE webhook: Failed to get access token for content download')
            return None

        _logger.info('LINE webhook: Got access token, downloading content...')

        # Download content (now returns tuple)
        result = livechat_channel._line_get_content(access_token, message_id)
        if result is None or (isinstance(result, tuple) and result[0] is None):
            _logger.error('LINE webhook: Failed to download content %s', message_id)
            return None

        # Handle both old (bytes) and new (tuple) return format
        if isinstance(result, tuple):
            content, content_type = result
        else:
            content = result
            content_type = None

        _logger.info('LINE webhook: Downloaded content, size=%s bytes, content_type=%s',
                    len(content) if content else 0, content_type)

        # Determine filename and mimetype from content_type or message_type
        if content_type:
            # Use actual content type from LINE response
            mimetype = content_type
            # Determine extension from mimetype
            ext_map = {
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'video/mp4': '.mp4',
                'audio/m4a': '.m4a',
                'audio/x-m4a': '.m4a',
                'audio/mp4': '.m4a',
                'audio/mpeg': '.mp3',
            }
            ext = ext_map.get(mimetype.split(';')[0], '')
            filename = f'line_{message_type}_{message_id}{ext}'
        else:
            # Fallback to message_type based detection
            if message_type == 'image':
                filename = f'line_image_{message_id}.jpg'
                mimetype = 'image/jpeg'
            elif message_type == 'video':
                filename = f'line_video_{message_id}.mp4'
                mimetype = 'video/mp4'
            elif message_type == 'audio':
                filename = f'line_audio_{message_id}.m4a'
                mimetype = 'audio/m4a'
            elif message_type == 'file':
                filename = message.get('fileName', f'line_file_{message_id}')
                mimetype = 'application/octet-stream'
            else:
                filename = f'line_content_{message_id}'
                mimetype = 'application/octet-stream'

        # Create attachment
        try:
            attachment = request.env['ir.attachment'].sudo().create({
                'name': filename,
                'datas': base64.b64encode(content),
                'mimetype': mimetype,
                'public': True,
            })
            _logger.info('LINE webhook: Created attachment id=%s, name=%s, mimetype=%s',
                        attachment.id, filename, mimetype)
            return attachment
        except Exception as e:
            _logger.error('LINE webhook: Failed to create attachment: %s', e)
            import traceback
            _logger.error('LINE webhook: Traceback: %s', traceback.format_exc())
            return None
