# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

LINE_API_BASE_URL = 'https://api.line.me/v2'
LINE_DATA_API_BASE_URL = 'https://api-data.line.me/v2'


class LineApiMixin(models.AbstractModel):
    """Mixin providing LINE Messaging API methods."""
    _name = 'line.api.mixin'
    _description = 'LINE API Mixin'

    def _line_get_access_token(self, channel_id, channel_secret):
        """Get LINE access token using Channel ID and Secret.

        Args:
            channel_id: LINE Channel ID.
            channel_secret: LINE Channel Secret.

        Returns:
            str: Access token or None on failure.
        """
        url = 'https://api.line.me/v2/oauth/accessToken'
        data = {
            'grant_type': 'client_credentials',
            'client_id': channel_id,
            'client_secret': channel_secret,
        }

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            return response.json().get('access_token')
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
            bytes: Content data or None on failure.
        """
        url = f'{LINE_DATA_API_BASE_URL}/bot/message/{message_id}/content'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            _logger.error('LINE API: Failed to get content: %s', e)
            return None

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
            original_url: Original image URL.
            preview_url: Preview image URL (optional).

        Returns:
            dict: LINE message object.
        """
        return {
            'type': 'image',
            'originalContentUrl': original_url,
            'previewImageUrl': preview_url or original_url,
        }
