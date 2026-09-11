# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""H-11: a forged (badly-signed) LINE webhook request gets HTTP 200 and its
attacker-controlled body is written to the log at WARNING. Because the route
is type='json', Odoo answers 200 even when we return early on a bad
signature, so forged requests and vulnerability scans are indistinguishable
from real traffic to anyone watching responses. And because the WARNING log
includes the raw body, an anonymous caller can write arbitrary text into the
server log.

Separately, several INFO logs on the real (correctly-signed) path carry
message text and LINE display names verbatim. One tenant is medical, and
these logs end up in log aggregation.

Seam: real HTTP POSTs to /line/webhook/<channel_id> via HttpCase.url_open,
mocking only the LINE HTTP boundary (line_api_service's http_requests calls).
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
    mock_line_profile_response,
    mock_line_token_response,
)

LOGGER_NAME = 'odoo.addons.woow_odoo_livechat_line'


def _route_post():
    def _post(url, **kwargs):
        if 'oauth/accessToken' in url:
            return mock_line_token_response()
        raise AssertionError(f'unexpected POST to {url}')
    return _post


def _route_get(display_name):
    def _get(url, **kwargs):
        if '/bot/profile/' in url:
            return mock_line_profile_response(display_name=display_name)
        raise AssertionError(f'unexpected GET to {url}')
    return _get


class _LineWebhookHttpCase(HttpCase, LineTestMixin):

    def setUp(self):
        super().setUp()
        self._setup_line_livechat()

    def _url(self):
        return f'/line/webhook/{self.livechat_channel.id}'

    def _liff_installed(self):
        # Woow_odoo_line_liff declares the same route pattern
        # (/line/webhook/<int:...>) and, when installed, is the controller
        # that actually answers it — it has its own (already-safe)
        # signature check and 403 response, and only *forwards* the event
        # to this module's _process_event for business logic. So this
        # module's own signature-rejection path (and its own warning log)
        # is only reachable when liff is not installed. See Marlin's brief
        # "Routing, before you start".
        return bool(self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'woow_odoo_line_liff'), ('state', '=', 'installed'),
        ]))


@tagged('post_install', '-at_install', 'line_ci')
class TestForgedWebhookRequest(_LineWebhookHttpCase):

    def test_bad_signature_is_rejected_with_403(self):
        body = make_webhook_body(make_webhook_event(text='hello'))
        response = self.url_open(
            self._url(), data=body.encode(),
            headers={
                'Content-Type': 'application/json',
                'X-Line-Signature': 'not-a-real-signature',
            },
        )
        self.assertEqual(
            response.status_code, 403,
            'a forged/scanned request must not be answered with 200 — '
            'today it is indistinguishable from a real, accepted webhook call')

    def test_bad_signature_does_not_write_the_body_to_the_log(self):
        if self._liff_installed():
            self.skipTest(
                'liff answers this route and forwards only successfully-'
                'verified events to this module; this module\'s own '
                'signature-rejection path (and its log line) is not '
                'reachable in this state — see brief\'s "Routing" note')
        # Built by hand (not make_webhook_body/make_webhook_event) to keep
        # the marker within the first 200 chars of the JSON — the exact
        # slice the vulnerable code logs — so this test actually exercises
        # the leak instead of missing it by accident of field ordering.
        distinctive_body_marker = 'forged-body-marker-9f31'
        body = json.dumps({'events': [{
            'type': 'message',
            'replyToken': 'r',
            'source': {'type': 'user', 'userId': 'U1'},
            'timestamp': 0,
            'message': {'id': 'm1', 'type': 'text', 'text': distinctive_body_marker},
        }]})
        with self.assertLogs(LOGGER_NAME, level='WARNING') as cm:
            self.url_open(
                self._url(), data=body.encode(),
                headers={
                    'Content-Type': 'application/json',
                    'X-Line-Signature': 'not-a-real-signature',
                },
            )
        joined = '\n'.join(cm.output)
        self.assertNotIn(
            distinctive_body_marker, joined,
            'the attacker-controlled request body must never be logged; '
            'only channel id and body length are safe to log')

    def test_correctly_signed_request_still_gets_200_and_is_processed(self):
        with patch('odoo.addons.woow_line_base.models.line_api_service.http_requests.post',
                   side_effect=_route_post()), \
             patch('odoo.addons.woow_line_base.models.line_api_service.http_requests.get',
                   side_effect=_route_get('Real Customer')):
            body = make_webhook_body(make_webhook_event(text='hello there'))
            signature = make_line_signature(body, FAKE_LINE_CHANNEL_SECRET)
            response = self.url_open(
                self._url(), data=body.encode(),
                headers={
                    'Content-Type': 'application/json',
                    'X-Line-Signature': signature,
                },
            )
        self.assertEqual(response.status_code, 200)
        channel = self.env['discuss.channel'].search(
            [('line_user_id', '=', FAKE_LINE_USER_ID)], limit=1)
        self.assertTrue(channel, 'a correctly-signed message must still create the conversation')
        bodies = ''.join(channel.message_ids.mapped('body'))
        self.assertIn('hello there', bodies)


@tagged('post_install', '-at_install', 'line_ci')
class TestNoPiiAtInfoLevel(_LineWebhookHttpCase):

    def test_message_text_and_display_name_do_not_appear_in_info_logs(self):
        distinctive_text = 'Patient reports chest pain since Tuesday morning, please call back'
        distinctive_name = 'Confidential Patient Chen'

        body = make_webhook_body(make_webhook_event(
            text=distinctive_text, line_user_id='Upiitest0000000000000000000001'))
        signature = make_line_signature(body, FAKE_LINE_CHANNEL_SECRET)

        with patch('odoo.addons.woow_line_base.models.line_api_service.http_requests.post',
                   side_effect=_route_post()), \
             patch('odoo.addons.woow_line_base.models.line_api_service.http_requests.get',
                   side_effect=_route_get(distinctive_name)), \
             self.assertLogs(LOGGER_NAME, level='INFO') as cm:
            response = self.url_open(
                self._url(), data=body.encode(),
                headers={
                    'Content-Type': 'application/json',
                    'X-Line-Signature': signature,
                },
            )
        self.assertEqual(response.status_code, 200)
        joined = '\n'.join(cm.output)
        self.assertNotIn(
            distinctive_text, joined,
            'the customer/operator message text must not appear at INFO — '
            'move it to DEBUG or drop it')
        self.assertNotIn(
            distinctive_name, joined,
            'the LINE displayName must not appear at INFO — '
            'move it to DEBUG or drop it')
