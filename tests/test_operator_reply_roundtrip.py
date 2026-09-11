# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Verify _line_html_to_text round-trips what an operator actually types,
using the body format Odoo 18's Discuss composer actually submits — not a
hand-picked HTML fixture.

The composer never sends the operator's raw keystrokes. Before message_post
ever sees it, mail/static/src/utils/common/format.js's
escapeAndCompactTextContent HTML-escapes the text (&, <, >, ', ", `) and then
turns line breaks into <br/>, and prettifyMessageContent additionally wraps
bare URLs in an <a href=...> pulled from the (already-escaped) text. Building
a test body by writing raw HTML risks passing by construction — this
reproduces the composer's actual transform (verified by reading
odoo/addons/mail/static/src/utils/common/format.js in the Odoo 18 image) and
checks what LINE receives back is character-for-character what the operator
typed.

Seam: discuss_channel.message_post(), called as the operator (with_user),
the same public method the Discuss UI calls. Only the LINE push HTTP
boundary is mocked.
"""

import re
from unittest.mock import patch

from markupsafe import Markup

from odoo.tests import TransactionCase, tagged

from .common import (
    FAKE_LINE_CHANNEL_ID,
    FAKE_LINE_CHANNEL_SECRET,
    route_mock_post,
)


def _js_escape(text):
    """odoo/addons/web/static/src/core/utils/strings.js escape()."""
    for a, b in (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'),
                 ("'", '&#x27;'), ('"', '&quot;'), ('`', '&#x60;')):
        text = text.replace(a, b)
    return text


def _composer_body(raw_text):
    """mail/static/src/utils/common/format.js escapeAndCompactTextContent(),
    for plain text with no mentions/emoji (not relevant to an operator
    typing a reply)."""
    value = _js_escape(raw_text).strip()
    value = re.sub(r'(\r|\n){2,}', '<br/><br/>', value)
    value = re.sub(r'(\r|\n)', '<br/>', value)
    value = value.replace(' ', '&nbsp;')
    value = re.sub(r'([^>])&nbsp;([^<])', r'\1 \2', value)
    return value


def _composer_body_with_url_link(raw_url):
    """prettifyMessageContent()'s addLink() wraps a bare URL in an <a> tag
    built from the already-escaped text, e.g. a literal '&' in the query
    string is '&amp;' both in href and in the link text."""
    escaped = _composer_body(raw_url)
    return f'<a target="_blank" rel="noreferrer noopener" href="{escaped}">{escaped}</a>'


@tagged('post_install', '-at_install', 'line_ci')
class TestOperatorReplyRoundTrip(TransactionCase):
    """H-1 follow-up: confirm _line_html_to_text round-trips real composer
    output. If every case here already passes on main, this is a guard
    against regressions, not a bug fix (see report)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = cls.env['res.users'].create({
            'name': 'Roundtrip Operator',
            'login': 'roundtrip_operator',
            'email': 'roundtrip@test.com',
            'groups_id': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('im_livechat.im_livechat_group_user').id),
            ],
        })
        cls.livechat = cls.env['im_livechat.channel'].create({'name': 'roundtrip fixture'})
        cls.livechat.sudo().write({
            'user_ids': [(4, cls.operator.id)],
            'line_channel_id': FAKE_LINE_CHANNEL_ID,
            'line_channel_secret': FAKE_LINE_CHANNEL_SECRET,
            'line_enabled': True,
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'roundtrip channel',
            'channel_type': 'livechat',
            'livechat_channel_id': cls.livechat.id,
            'livechat_active': True,
            'livechat_operator_id': cls.operator.partner_id.id,
            'line_user_id': 'Uroundtriptest0000000000000001',
            'channel_member_ids': [(0, 0, {'partner_id': cls.operator.partner_id.id})],
        })

    def test_ampersand(self):
        raw = 'A & B'
        text = self._post_and_get_line_text(_composer_body(raw))
        self.assertEqual(text, raw)

    def test_angle_brackets_with_ampersand(self):
        raw = '價格 <500 & >100'
        text = self._post_and_get_line_text(_composer_body(raw))
        self.assertEqual(text, raw)

    def test_literal_entity_text_is_not_double_unescaped(self):
        raw = '&lt;literally&gt;'
        text = self._post_and_get_line_text(_composer_body(raw))
        self.assertEqual(text, raw)

    def test_two_lines_separated_by_enter(self):
        raw = 'line one\nline two'
        text = self._post_and_get_line_text(_composer_body(raw))
        self.assertEqual(text, raw)

    def test_url_with_ampersand_query_params(self):
        raw = 'https://example.com/search?q=test&lang=zh'
        text = self._post_and_get_line_text(_composer_body_with_url_link(raw))
        self.assertEqual(text, raw)

    def _post_and_get_line_text(self, composer_body):
        captured = []

        def capture_post(url, **kwargs):
            if '/bot/message/push' in url:
                captured.append(kwargs.get('json'))
            return route_mock_post(url, **kwargs)

        with patch('odoo.addons.woow_line_base.models.line_api_service.http_requests.post',
                   side_effect=capture_post):
            self.channel.with_user(self.operator).message_post(
                # The real composer's RPC call carries already-sanitized,
                # trusted HTML. Passing a plain str here would make Odoo's
                # own message_post treat it as untrusted plain text and
                # HTML-escape it a second time (confirmed empirically: a
                # plain str body of 'A &amp; B' is stored as
                # '<p>A &amp;amp; B</p>', double-escaping the ampersand).
                # Markup() reproduces what the composer actually sends.
                body=Markup(composer_body),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        self.assertTrue(captured, 'no push request reached LINE')
        return captured[-1]['messages'][0]['text']
