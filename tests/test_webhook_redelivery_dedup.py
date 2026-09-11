# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""H-13: a LINE webhook redelivery (network hiccup, or "webhook redelivery"
enabled in the LINE console) creates a duplicate Discuss message, and a
duplicate attachment for media messages.

LINE gives each message a unique `message.id`; a redelivery resends the same
event with the same message.id (and sets deliveryContext.isRedelivery). The
fix must remember processed ids across requests and skip a repeat, and the
guarantee has to survive two overlapping deliveries of the same event rather
than relying on a plain read-then-write check.

Seam: real HTTP POSTs to /line/webhook/<channel_id> via HttpCase.url_open,
delivering the same signed event twice. Mock only the LINE HTTP boundary.
"""

import json
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from .common import (
    FAKE_LINE_CHANNEL_SECRET,
    FAKE_LINE_USER_ID,
    LineTestMixin,
    make_line_signature,
    make_webhook_body,
    make_webhook_event,
    mock_line_content_response,
    mock_line_profile_response,
    mock_line_token_response,
)


def _route_post():
    def _post(url, **kwargs):
        if 'oauth/accessToken' in url:
            return mock_line_token_response()
        raise AssertionError(f'unexpected POST to {url}')
    return _post


def _route_get():
    def _get(url, **kwargs):
        if '/bot/profile/' in url:
            return mock_line_profile_response()
        if '/bot/message/' in url and '/content' in url:
            return mock_line_content_response()
        raise AssertionError(f'unexpected GET to {url}')
    return _get


@tagged('post_install', '-at_install', 'line_ci')
class TestRedeliveryDedup(HttpCase, LineTestMixin):

    def setUp(self):
        super().setUp()
        self._setup_line_livechat()

    def _url(self):
        return f'/line/webhook/{self.livechat_channel.id}'

    def _post_event(self, event, is_redelivery=False):
        body_dict = {'destination': 'test_destination', 'events': [event]}
        if is_redelivery:
            event.setdefault('deliveryContext', {})['isRedelivery'] = True
        body = json.dumps(body_dict)
        signature = make_line_signature(body, FAKE_LINE_CHANNEL_SECRET)
        with patch('odoo.addons.woow_line_base.models.line_api_service.http_requests.post',
                   side_effect=_route_post()), \
             patch('odoo.addons.woow_line_base.models.line_api_service.http_requests.get',
                   side_effect=_route_get()):
            return self.url_open(
                self._url(), data=body.encode(),
                headers={
                    'Content-Type': 'application/json',
                    'X-Line-Signature': signature,
                },
            )

    def _channel(self):
        return self.env['discuss.channel'].search(
            [('line_user_id', '=', FAKE_LINE_USER_ID)], limit=1)

    def test_redelivered_text_message_is_not_duplicated(self):
        event = make_webhook_event(text='redeliver me once', message_id='msg_dup_001')
        r1 = self._post_event(event)
        self.assertEqual(r1.status_code, 200)

        channel = self._channel()
        self.assertTrue(channel)
        bodies_after_first = [b for b in channel.message_ids.mapped('body') if 'redeliver me once' in b]
        self.assertEqual(len(bodies_after_first), 1)

        # Same event, redelivered.
        event2 = make_webhook_event(text='redeliver me once', message_id='msg_dup_001')
        r2 = self._post_event(event2, is_redelivery=True)
        self.assertEqual(r2.status_code, 200, 'a duplicate must not turn into a 500')

        channel.invalidate_recordset()
        bodies_after_second = [b for b in channel.message_ids.mapped('body') if 'redeliver me once' in b]
        self.assertEqual(
            len(bodies_after_second), 1,
            'the LINE Discuss channel must contain exactly one message for a '
            'redelivered event, as the operator sees it')

    def test_redelivered_image_message_is_not_duplicated(self):
        event = make_webhook_event(message_type='image', message_id='msg_dup_img_001')
        r1 = self._post_event(event)
        self.assertEqual(r1.status_code, 200)

        channel = self._channel()
        self.assertTrue(channel)
        attachments_after_first = channel.message_ids.mapped('attachment_ids')
        self.assertEqual(len(attachments_after_first), 1)

        event2 = make_webhook_event(message_type='image', message_id='msg_dup_img_001')
        r2 = self._post_event(event2, is_redelivery=True)
        self.assertEqual(r2.status_code, 200)

        channel.invalidate_recordset()
        attachments_after_second = channel.message_ids.mapped('attachment_ids')
        self.assertEqual(
            len(attachments_after_second), 1,
            'exactly one attachment must exist for a redelivered image event')

    def test_two_different_message_ids_both_land(self):
        r1 = self._post_event(make_webhook_event(text='first message', message_id='msg_a'))
        r2 = self._post_event(make_webhook_event(text='second message', message_id='msg_b'))
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

        channel = self._channel()
        self.assertTrue(channel)
        bodies = ''.join(channel.message_ids.mapped('body'))
        self.assertIn('first message', bodies)
        self.assertIn('second message', bodies)
