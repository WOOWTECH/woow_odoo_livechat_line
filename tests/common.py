# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Common test infrastructure for LINE LiveChat integration tests.

Provides base classes, mock factories, and helper functions used across
all test phases (6-13) of the production deployment test plan.
"""

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged

# ── Test constants ──────────────────────────────────────────────────

FAKE_LINE_CHANNEL_ID = '1234567890'
FAKE_LINE_CHANNEL_SECRET = 'test_channel_secret_32chars_long'
FAKE_LINE_ACCESS_TOKEN = 'test_access_token_for_line_api'
FAKE_LINE_USER_ID = 'U1234567890abcdef1234567890abcdef'
FAKE_LINE_USER_ID_2 = 'Uabcdef1234567890abcdef1234567890'
FAKE_LINE_DISPLAY_NAME = 'Test LINE User'
FAKE_LINE_PICTURE_URL = 'https://profile.line-scdn.net/abc123'


# ── Signature helper ───────────────────────────────────────────────

def make_line_signature(body_str, channel_secret):
    """Compute LINE X-Line-Signature (HMAC-SHA256, base64-encoded)."""
    hash_value = hmac.new(
        channel_secret.encode('utf-8'),
        body_str.encode('utf-8'),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(hash_value).decode('utf-8')


# ── Webhook event builders ─────────────────────────────────────────

def make_webhook_event(event_type='message', message_type='text',
                       text='Hello', line_user_id=FAKE_LINE_USER_ID,
                       message_id='msg_001', sticker_id=None,
                       package_id=None, latitude=None, longitude=None,
                       file_name=None):
    """Build a LINE webhook event dict for testing."""
    event = {
        'type': event_type,
        'replyToken': 'test_reply_token',
        'source': {'type': 'user', 'userId': line_user_id},
        'timestamp': int(time.time() * 1000),
    }
    if event_type == 'message':
        msg = {'id': message_id, 'type': message_type}
        if message_type == 'text':
            msg['text'] = text
        elif message_type == 'sticker':
            msg['stickerId'] = sticker_id or '1'
            msg['packageId'] = package_id or '1'
        elif message_type == 'location':
            msg['title'] = 'Test Location'
            msg['address'] = '123 Test St'
            msg['latitude'] = latitude or 25.0330
            msg['longitude'] = longitude or 121.5654
        elif message_type == 'file':
            msg['fileName'] = file_name or 'test_document.pdf'
            msg['fileSize'] = 12345
        event['message'] = msg
    return event


def make_webhook_body(events, destination='test_destination'):
    """Wrap event(s) in a LINE webhook body JSON string."""
    body = {
        'destination': destination,
        'events': events if isinstance(events, list) else [events],
    }
    return json.dumps(body)


# ── Mock response factories ────────────────────────────────────────

def mock_line_token_response():
    """Mock requests.Response for LINE OAuth token endpoint."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        'access_token': FAKE_LINE_ACCESS_TOKEN,
        'expires_in': 2592000,
        'token_type': 'Bearer',
    }
    resp.raise_for_status = MagicMock()
    return resp


def mock_line_profile_response(display_name=FAKE_LINE_DISPLAY_NAME,
                                picture_url=FAKE_LINE_PICTURE_URL,
                                user_id=FAKE_LINE_USER_ID):
    """Mock requests.Response for LINE Profile API."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        'displayName': display_name,
        'userId': user_id,
        'pictureUrl': picture_url,
        'statusMessage': 'Hello World',
    }
    resp.raise_for_status = MagicMock()
    return resp


def mock_line_push_response(success=True):
    """Mock requests.Response for LINE Push API."""
    resp = MagicMock()
    resp.status_code = 200 if success else 500
    resp.text = '{}' if success else '{"message":"Internal server error"}'
    resp.raise_for_status = MagicMock()
    if not success:
        from requests.exceptions import HTTPError
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp


def mock_line_content_response(content=None, content_type='image/png'):
    """Mock requests.Response for LINE Content API."""
    resp = MagicMock()
    resp.status_code = 200
    resp.content = content or (b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
    resp.headers = {'Content-Type': content_type}
    resp.raise_for_status = MagicMock()
    return resp


# ── URL-based request routing ──────────────────────────────────────

def route_mock_post(url, **kwargs):
    """Route mocked POST requests by URL pattern."""
    if 'oauth/accessToken' in url:
        return mock_line_token_response()
    if '/bot/message/push' in url:
        return mock_line_push_response(success=True)
    raise ValueError(f'Unexpected POST to {url}')


def route_mock_get(url, **kwargs):
    """Route mocked GET requests by URL pattern."""
    if '/bot/profile/' in url:
        return mock_line_profile_response()
    if '/bot/message/' in url and '/content' in url:
        return mock_line_content_response()
    raise ValueError(f'Unexpected GET to {url}')


# ── Base test mixin ────────────────────────────────────────────────

class LineTestMixin:
    """Mixin providing common LINE test setup and helpers."""

    def _setup_line_livechat(self):
        """Create operator user + LiveChat channel with LINE config."""
        # Clear global token cache
        from odoo.addons.woow_odoo_livechat_line.models.line_api import (
            _token_cache,
        )
        _token_cache.clear()

        # Set HTTPS base URL
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://test.example.com',
        )

        # Create operator
        self.operator_user = self.env['res.users'].create({
            'name': 'Test Operator',
            'login': 'test_operator_line',
            'email': 'operator@test.com',
            'groups_id': [
                (4, self.env.ref('im_livechat.im_livechat_group_user').id),
            ],
        })
        self.operator_partner = self.operator_user.partner_id

        # Create LiveChat channel with LINE enabled
        self.livechat_channel = self.env['im_livechat.channel'].create({
            'name': 'Test LINE Channel',
            'user_ids': [(4, self.operator_user.id)],
            'line_enabled': True,
            'line_channel_id': FAKE_LINE_CHANNEL_ID,
            'line_channel_secret': FAKE_LINE_CHANNEL_SECRET,
        })

    def _create_line_guest(self, line_user_id=FAKE_LINE_USER_ID,
                           name='LINE User'):
        """Create a mail.guest with LINE user ID."""
        return self.env['mail.guest'].sudo().create({
            'name': name,
            'line_user_id': line_user_id,
        })

    def _create_line_discuss_channel(self, guest,
                                      line_user_id=FAKE_LINE_USER_ID):
        """Create a discuss.channel linked to a LINE user."""
        channel = self.env['discuss.channel'].sudo().create({
            'name': f'LINE: {guest.name}',
            'channel_type': 'livechat',
            'livechat_channel_id': self.livechat_channel.id,
            'livechat_active': True,
            'livechat_operator_id': self.operator_partner.id,
            'line_user_id': line_user_id,
            'channel_member_ids': [
                (0, 0, {'partner_id': self.operator_partner.id}),
            ],
        })
        channel.add_members(guest_ids=[guest.id])
        return channel

    def _call_controller_directly(self, channel_id, events,
                                   channel_secret=FAKE_LINE_CHANNEL_SECRET):
        """Call the webhook controller with mocked HTTP request."""
        from odoo.addons.woow_odoo_livechat_line.controllers.webhook import (
            LineWebhookController,
        )
        controller = LineWebhookController()
        body_str = make_webhook_body(events)
        signature = make_line_signature(body_str, channel_secret)

        mock_httprequest = MagicMock()
        mock_httprequest.get_data.return_value = body_str
        mock_httprequest.headers = {
            'X-Line-Signature': signature,
            'Content-Type': 'application/json',
        }

        mock_request = MagicMock()
        mock_request.httprequest = mock_httprequest
        mock_request.env = self.env

        with patch(
            'odoo.addons.woow_odoo_livechat_line.controllers.webhook.request',
            mock_request,
        ):
            return controller.line_webhook(channel_id)


# ── Base test case ─────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class LineTransactionCase(TransactionCase, LineTestMixin):
    """Base TransactionCase for LINE integration tests."""

    def setUp(self):
        super().setUp()
        self._setup_line_livechat()
