# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Replies go out with the customer's reply token when it is fresh.

LINE counts push messages toward the official account's monthly quota but not
reply messages. On 2026-11-05 woowtech's free plan (200/month) ran out and
every Odoo reply to LINE failed with HTTP 429 "You have reached your monthly
limit." although almost all of them answered a message or a rich-menu tap
seconds earlier. The first reply within the token lifetime must therefore be a
reply, falling back to push only when LINE rejects the token.

Seams: discuss.channel.message_post() for the outbound side, real signed
POSTs to /line/webhook/<id> for the inbound side; only the LINE HTTP boundary
is mocked.
"""
import json
from unittest.mock import patch

import requests
from markupsafe import Markup

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged

from .common import (
    FAKE_LINE_CHANNEL_ID,
    FAKE_LINE_CHANNEL_SECRET,
    FAKE_LINE_USER_ID,
    LineTestMixin,
    make_line_signature,
    make_webhook_event,
    mock_line_profile_response,
    mock_line_token_response,
)

POST = 'odoo.addons.woow_line_base.models.line_api_service.http_requests.post'
GET = 'odoo.addons.woow_line_base.models.line_api_service.http_requests.get'


class _Resp:
    def __init__(self, status_code, text='{}'):
        self.status_code = status_code
        self.text = text


@tagged('post_install', '-at_install', 'line_ci')
class TestReplyTokenFirst(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from odoo.addons.woow_line_base.models.line_api_service import _token_cache
        _token_cache.clear()
        cls.operator = cls.env['res.users'].create({
            'name': 'Reply Operator', 'login': 'line_reply_operator', 'email': 'reply@test.com',
            'groups_id': [(4, cls.env.ref('base.group_user').id),
                          (4, cls.env.ref('im_livechat.im_livechat_group_user').id)],
        })
        cls.employee = cls.env['res.users'].create({
            'name': 'Plain Employee Reply', 'login': 'line_reply_employee',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.bot = cls.env['res.partner'].create({'name': 'AI 用量報告'})
        cls.livechat = cls.env['im_livechat.channel'].create({'name': 'reply token fixture'})
        cls.livechat.sudo().write({
            'user_ids': [(4, cls.operator.id)],
            'line_channel_id': FAKE_LINE_CHANNEL_ID,
            'line_channel_secret': FAKE_LINE_CHANNEL_SECRET,
            'line_enabled': True,
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'reply token channel', 'channel_type': 'livechat',
            'livechat_channel_id': cls.livechat.id, 'livechat_active': True,
            'livechat_operator_id': cls.operator.partner_id.id,
            'line_user_id': 'Ureplytoken000000000000000000001',
            'channel_member_ids': [(0, 0, {'partner_id': cls.operator.partner_id.id})],
        })

    def _send(self, body='<p>報告</p>', reply=200, push=200, push_text='{}'):
        """Post a bot message; return the reply and push request bodies."""
        calls = {'reply': [], 'push': []}

        def fake_post(url, **kwargs):
            if 'oauth/accessToken' in url:
                return mock_line_token_response()
            if '/bot/message/reply' in url:
                calls['reply'].append(kwargs.get('json'))
                if isinstance(reply, Exception):
                    raise reply
                return _Resp(reply, '{}' if reply == 200 else '{"message":"Invalid reply token"}')
            if '/bot/message/push' in url:
                calls['push'].append(kwargs.get('json'))
                return _Resp(push, push_text)
            raise AssertionError(f'unexpected POST to {url}')

        with patch(POST, side_effect=fake_post):
            self.channel.message_post(body=Markup(body), author_id=self.bot.id,
                                      message_type='comment', subtype_xmlid='mail.mt_comment')
        return calls

    def _age_token(self, seconds):
        self.env.cr.execute(
            "UPDATE discuss_channel SET line_reply_token_at = "
            "(clock_timestamp() AT TIME ZONE 'UTC') - make_interval(secs => %s) WHERE id = %s",
            (seconds, self.channel.id))

    def _token(self):
        self.channel.invalidate_recordset(['line_reply_token'])
        return self.channel.sudo().line_reply_token

    def _notices(self, needle):
        return self.env['mail.message'].search_count([
            ('model', '=', 'discuss.channel'), ('res_id', '=', self.channel.id),
            ('body', 'ilike', needle)])

    def test_fresh_token_sends_a_reply_not_a_push(self):
        self.channel._line_store_reply_token('rt_fresh')
        calls = self._send()
        self.assertEqual([c['replyToken'] for c in calls['reply']], ['rt_fresh'])
        self.assertEqual(calls['push'], [])
        self.assertFalse(self._token(), 'a reply token can only be used once')

    def test_second_message_pushes(self):
        self.channel._line_store_reply_token('rt_once')
        self._send()
        calls = self._send()
        self.assertEqual(calls['reply'], [])
        self.assertEqual(len(calls['push']), 1)

    def test_expired_token_is_not_used(self):
        self.channel._line_store_reply_token('rt_old')
        self._age_token(120)
        calls = self._send()
        self.assertEqual(calls['reply'], [])
        self.assertEqual(len(calls['push']), 1)
        self.assertFalse(self._token())

    def test_rejected_token_falls_back_to_push(self):
        self.channel._line_store_reply_token('rt_used_by_liff')
        calls = self._send(reply=400)
        self.assertEqual(len(calls['reply']), 1)
        self.assertEqual(len(calls['push']), 1)
        self.assertEqual(self._notices('未能送達'), 0)

    def test_reply_without_response_is_not_pushed_again(self):
        self.channel._line_store_reply_token('rt_timeout')
        calls = self._send(reply=requests.exceptions.ConnectTimeout('boom'))
        self.assertEqual(len(calls['reply']), 1)
        self.assertEqual(calls['push'], [], 'pushing after an unknown reply outcome could duplicate it')
        self.assertEqual(self._notices('網路錯誤'), 1)

    def test_ttl_zero_disables_replies(self):
        self.env['ir.config_parameter'].sudo().set_param('woow_odoo_livechat_line.reply_token_ttl', '0')
        self.channel._line_store_reply_token('rt_disabled')
        calls = self._send()
        self.assertEqual(calls['reply'], [])
        self.assertEqual(len(calls['push']), 1)

    def test_only_first_batch_is_a_reply(self):
        self.channel._line_store_reply_token('rt_long')
        body = ''.join('<p>%s</p>' % ('長' * 4900) for _ in range(6))
        calls = self._send(body=body)
        self.assertEqual(len(calls['reply']), 1)
        self.assertEqual(len(calls['reply'][0]['messages']), 5)
        self.assertEqual(len(calls['push']), 1)
        self.assertEqual(len(calls['push'][0]['messages']), 1)

    def test_monthly_limit_notice_is_clear_and_not_repeated(self):
        limit = '{"message":"You have reached your monthly limit."}'
        self._send(push=429, push_text=limit)
        self._send(push=429, push_text=limit)
        self.assertEqual(self._notices('訊息額度已用完'), 1)
        self.assertEqual(self._notices('LINE API 回應失敗'), 0, 'no generic notice on top')

    def test_other_429_keeps_generic_notice(self):
        self._send(push=429, push_text='{"message":"Too many requests"}')
        self.assertEqual(self._notices('訊息額度已用完'), 0)
        self.assertEqual(self._notices('HTTP 429'), 1)

    def test_employee_cannot_plant_a_reply_token(self):
        channel = self.env['discuss.channel'].with_user(self.employee).create({'name': 'mine'})
        with self.assertRaises(AccessError):
            channel.write({'line_reply_token': 'forged'})


def _route_get(url, **kwargs):
    if '/bot/profile/' in url:
        return mock_line_profile_response()
    raise AssertionError(f'unexpected GET to {url}')


def _route_post(url, **kwargs):
    if 'oauth/accessToken' in url:
        return mock_line_token_response()
    raise AssertionError(f'unexpected POST to {url}')


@tagged('post_install', '-at_install', 'line_ci')
class TestReplyTokenWebhook(HttpCase, LineTestMixin):

    def setUp(self):
        super().setUp()
        self._setup_line_livechat()

    def _post_event(self, event):
        body = json.dumps({'destination': 'test_destination', 'events': [event]})
        with patch(POST, side_effect=_route_post), patch(GET, side_effect=_route_get):
            return self.url_open(
                f'/line/webhook/{self.livechat_channel.id}', data=body.encode(),
                headers={'Content-Type': 'application/json',
                         'X-Line-Signature': make_line_signature(body, FAKE_LINE_CHANNEL_SECRET)})

    def _channel(self, uid=FAKE_LINE_USER_ID):
        return self.env['discuss.channel'].sudo().search([('line_user_id', '=', uid)], limit=1)

    @staticmethod
    def _postback(uid=FAKE_LINE_USER_ID, token='rt_postback'):
        return {'type': 'postback', 'replyToken': token, 'timestamp': 1793700000000,
                'source': {'type': 'user', 'userId': uid}, 'mode': 'active',
                'webhookEventId': 'evt_pb', 'deliveryContext': {'isRedelivery': False},
                'postback': {'data': 'action=ai_usage'}}

    def test_message_event_keeps_its_reply_token(self):
        event = make_webhook_event(text='hi', message_id='rt_msg_1')
        event['replyToken'] = 'rt_from_message'
        self.assertEqual(self._post_event(event).status_code, 200)
        self.assertEqual(self._channel().line_reply_token, 'rt_from_message')

    def test_postback_updates_existing_conversation(self):
        self._post_event(make_webhook_event(text='hi', message_id='rt_msg_2'))
        self._post_event(self._postback(token='rt_menu_tap'))
        channel = self._channel()
        self.assertEqual(channel.line_reply_token, 'rt_menu_tap')
        self.assertFalse(self.env['mail.message'].search_count([
            ('model', '=', 'discuss.channel'), ('res_id', '=', channel.id),
            ('body', 'ilike', 'ai_usage')]), 'a postback posts nothing')

    def test_postback_from_unknown_user_creates_nothing(self):
        uid = 'Unobody00000000000000000000000001'
        self._post_event(self._postback(uid=uid))
        self.assertFalse(self._channel(uid))
        self.assertFalse(self.env['mail.guest'].sudo().search([('line_user_id', '=', uid)]))
