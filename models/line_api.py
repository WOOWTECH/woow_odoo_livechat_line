# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import time
import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

LINE_API_BASE_URL = 'https://api.line.me/v2'
LINE_DATA_API_BASE_URL = 'https://api-data.line.me/v2'

# Token cache: {channel_id: {'token': str, 'expires_at': float}}
_token_cache = {}
# Token validity buffer (refresh 5 minutes before expiry)
TOKEN_EXPIRY_BUFFER = 300


class LineApiMixin(models.AbstractModel):
    """Mixin providing LINE Messaging API methods."""
    _name = 'line.api.mixin'
    _description = 'LINE API Mixin'

    def _line_get_access_token(self, channel_id, channel_secret):
        """Get LINE access token using Channel ID and Secret.

        Uses in-memory cache to avoid repeated API calls. LINE tokens
        are valid for 30 days, but we refresh 5 minutes before expiry.

        Args:
            channel_id: LINE Channel ID.
            channel_secret: LINE Channel Secret.

        Returns:
            str: Access token or None on failure.
        """
        global _token_cache

        # Check cache first
        cached = _token_cache.get(channel_id)
        if cached and cached['expires_at'] > time.time():
            return cached['token']

        # Request new token
        url = 'https://api.line.me/v2/oauth/accessToken'
        data = {
            'grant_type': 'client_credentials',
            'client_id': channel_id,
            'client_secret': channel_secret,
        }

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            access_token = result.get('access_token')
            # LINE tokens are valid for 30 days (2592000 seconds)
            expires_in = result.get('expires_in', 2592000)

            # Cache the token
            _token_cache[channel_id] = {
                'token': access_token,
                'expires_at': time.time() + expires_in - TOKEN_EXPIRY_BUFFER,
            }
            _logger.info('LINE API: Access token refreshed for channel %s', channel_id)
            return access_token
        except requests.exceptions.RequestException as e:
            _logger.error('LINE API: Failed to get access token: %s', e)
            return None

    def _line_push_message(self, access_token, line_user_id, messages):
        """Push message to LINE user.

        Args:
            access_token: LINE access token.
            line_user_id: LINE User ID.
            messages: List of message objects.

        Returns:
            bool: True on success.
        """
        url = f'{LINE_API_BASE_URL}/bot/message/push'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}',
        }
        data = {
            'to': line_user_id,
            'messages': messages,
        }

        try:
            response = requests.post(
                url, headers=headers, json=data, timeout=30
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            _logger.error('LINE API: Failed to push message: %s', e)
            return False

    def _line_get_profile(self, access_token, line_user_id):
        """Get LINE user profile.

        Args:
            access_token: LINE access token.
            line_user_id: LINE User ID.

        Returns:
            dict: User profile or empty dict on failure.
        """
        url = f'{LINE_API_BASE_URL}/bot/profile/{line_user_id}'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error('LINE API: Failed to get profile: %s', e)
            return {}

    def _line_get_content(self, access_token, message_id):
        """Get content (image, video, audio, file) from LINE.

        Args:
            access_token: LINE access token.
            message_id: LINE message ID.

        Returns:
            tuple: (bytes content, str content_type) or (None, None) on failure.
        """
        url = f'{LINE_DATA_API_BASE_URL}/bot/message/{message_id}/content'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        _logger.info('LINE API: Fetching content from %s', url)

        try:
            response = requests.get(url, headers=headers, timeout=60)
            _logger.info('LINE API: Content response status=%s, content-type=%s, size=%s',
                        response.status_code,
                        response.headers.get('Content-Type', 'unknown'),
                        len(response.content) if response.content else 0)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            return response.content, content_type
        except requests.exceptions.RequestException as e:
            _logger.error('LINE API: Failed to get content: %s', e)
            if hasattr(e, 'response') and e.response is not None:
                _logger.error('LINE API: Response status=%s, body=%s',
                             e.response.status_code,
                             e.response.text[:500] if e.response.text else '')
            return None, None

    def _line_build_text_message(self, text):
        """Build LINE text message object.

        Args:
            text: Message text.

        Returns:
            dict: LINE message object.
        """
        return {
            'type': 'text',
            'text': text,
        }

    def _line_build_image_message(self, original_url, preview_url=None):
        """Build LINE image message object.

        Args:
            original_url: Original image URL (must be HTTPS, JPEG/PNG, max 10MB).
            preview_url: Preview image URL (optional, max 1MB).

        Returns:
            dict: LINE message object.
        """
        return {
            'type': 'image',
            'originalContentUrl': original_url,
            'previewImageUrl': preview_url or original_url,
        }

    def _line_build_video_message(self, original_url, preview_url):
        """Build LINE video message object.

        Args:
            original_url: Video URL (must be HTTPS, MP4, max 200MB).
            preview_url: Preview image URL (must be HTTPS, JPEG/PNG, max 1MB).

        Returns:
            dict: LINE message object.
        """
        return {
            'type': 'video',
            'originalContentUrl': original_url,
            'previewImageUrl': preview_url,
        }

    def _line_build_audio_message(self, original_url, duration_ms):
        """Build LINE audio message object.

        Args:
            original_url: Audio URL (must be HTTPS, M4A, max 200MB).
            duration_ms: Duration in milliseconds.

        Returns:
            dict: LINE message object.
        """
        return {
            'type': 'audio',
            'originalContentUrl': original_url,
            'duration': duration_ms,
        }

    def _line_build_file_message(self, filename, file_url, file_size=None):
        """Build LINE Flex Message for file download.

        LINE doesn't support native file messages, so we use Flex Message
        to provide a download link.

        Args:
            filename: Name of the file.
            file_url: URL to download the file.
            file_size: Optional file size in bytes.

        Returns:
            dict: LINE Flex message object.
        """
        size_text = ''
        if file_size:
            if file_size < 1024:
                size_text = f' ({file_size} B)'
            elif file_size < 1024 * 1024:
                size_text = f' ({file_size // 1024} KB)'
            else:
                size_text = f' ({file_size // (1024 * 1024)} MB)'

        return {
            'type': 'flex',
            'altText': f'File: {filename}',
            'contents': {
                'type': 'bubble',
                'size': 'kilo',
                'body': {
                    'type': 'box',
                    'layout': 'vertical',
                    'contents': [
                        {
                            'type': 'text',
                            'text': '📎 File',
                            'weight': 'bold',
                            'size': 'sm',
                            'color': '#1DB446',
                        },
                        {
                            'type': 'text',
                            'text': filename + size_text,
                            'size': 'sm',
                            'wrap': True,
                            'margin': 'md',
                        },
                    ],
                },
                'footer': {
                    'type': 'box',
                    'layout': 'vertical',
                    'contents': [
                        {
                            'type': 'button',
                            'action': {
                                'type': 'uri',
                                'label': 'Download',
                                'uri': file_url,
                            },
                            'style': 'primary',
                            'height': 'sm',
                        },
                    ],
                },
            },
        }
