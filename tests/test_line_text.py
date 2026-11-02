# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""LINE plain text keeps link addresses, table cells and list numbers.

Before 18.0.2.0.3 the tag-strip turned an AI quote such as
``<td><a href="https://shop/x">Gateway</a></td><td>1</td><td>NT$2,599</td>``
into "Gateway1NT$2,599": the customer could not open the product page and
could not tell the quantity from the price.
"""
from unittest.mock import patch

from markupsafe import Markup

from odoo.tests import TransactionCase, tagged

from ..tools.line_text import LINE_TEXT_LIMIT, html_to_line_text, split_line_text
from .common import (
    FAKE_LINE_CHANNEL_ID,
    FAKE_LINE_CHANNEL_SECRET,
    route_mock_post,
)

# What an AI reply looks like after markdown rendering (im_livechat_ai /
# woow_ai_contact): paragraph, table with product links, list, closing link.
AI_QUOTE = (
    '<p>先以<strong>一間樣品房</strong>估算，總價 <strong>NT$9,549</strong>：</p>'
    '<table class="table"><thead><tr><th>設備</th><th>數量</th><th>小計</th></tr></thead>'
    '<tbody><tr><td>燈光：<a href="https://aiot.woowtech.io/shop/four-channel-module-171" '
    'target="_blank" rel="noopener noreferrer">WOOW 智能 4路模組</a></td><td>1 台</td>'
    '<td>NT$4,900</td></tr>'
    '<tr><td><a href="https://aiot.woowtech.io/shop/woow-matter-home-gateway-17">'
    'WOOW MATTER 家庭閘道器</a></td><td>1 台</td><td>NT$2,599</td></tr></tbody></table>'
    '<ol><li>安裝費另計</li><li>以客服報價為準</li></ol>'
    '<p>詳情請看 <a href="https://aiot.woowtech.io/shop">官網商店</a>，謝謝。</p>'
)


@tagged('post_install', '-at_install', 'line_ci')
class TestLineTextConversion(TransactionCase):

    def setUp(self):
        super().setUp()
        self.channel = self.env['discuss.channel']

    def test_link_address_is_kept_next_to_its_text(self):
        out = self.channel._line_html_to_text(
            '<p>看 <a href="https://aiot.woowtech.io/shop/x">這裡</a>，謝謝</p>')
        self.assertEqual(out, '看 這裡 https://aiot.woowtech.io/shop/x ，謝謝')

    def test_link_whose_text_is_the_address_is_not_repeated(self):
        url = 'https://example.com/search?q=test&lang=zh'
        out = self.channel._line_html_to_text(
            '<a href="https://example.com/search?q=test&amp;lang=zh">'
            'https://example.com/search?q=test&amp;lang=zh</a>')
        self.assertEqual(out, url)
        out = self.channel._line_html_to_text('<a href="https://www.woowtech.io/">woowtech.io</a>')
        self.assertEqual(out, 'woowtech.io')

    def test_internal_and_mention_links_keep_only_their_text(self):
        out = self.channel._line_html_to_text(
            '<p>請 <a href="/odoo/res.partner/3" class="o_mail_redirect" '
            'data-oe-model="res.partner" data-oe-id="3">@小明</a> 處理，'
            '<a href="mailto:a@b.c">寄信</a></p>')
        self.assertEqual(out, '請 @小明 處理，寄信')

    def test_table_rows_cells_and_link_addresses(self):
        lines = self.channel._line_html_to_text(AI_QUOTE).splitlines()
        self.assertIn('設備｜數量｜小計', lines)
        self.assertIn('・燈光：WOOW 智能 4路模組｜1 台｜NT$4,900', lines)
        row = lines.index('・燈光：WOOW 智能 4路模組｜1 台｜NT$4,900')
        self.assertEqual(lines[row + 1], 'https://aiot.woowtech.io/shop/four-channel-module-171')
        self.assertIn('・WOOW MATTER 家庭閘道器｜1 台｜NT$2,599', lines)
        self.assertIn('https://aiot.woowtech.io/shop/woow-matter-home-gateway-17', lines)

    def test_ordered_and_nested_lists(self):
        out = self.channel._line_html_to_text(
            '<ol><li>客廳</li><li>臥室<ul><li>雙切</li><li>三切</li></ul></li></ol>'
            '<ul><li>one</li><li>two</li></ul>')
        self.assertEqual(out.splitlines(), ['1. 客廳', '2. 臥室', '– 雙切', '– 三切', '• one', '• two'])

    def test_paragraphs_breaks_and_entities(self):
        self.assertEqual(self.channel._line_html_to_text('<p>x</p><p>y</p>'), 'x\ny')
        self.assertEqual(self.channel._line_html_to_text('<p>a<br/><br/>b</p>'), 'a\n\nb')
        self.assertEqual(self.channel._line_html_to_text('<p>Wi-Fi &amp; &#34;Pro&#34; &lt;86&gt;</p>'),
                         'Wi-Fi & "Pro" <86>')

    def test_script_and_style_content_is_dropped(self):
        self.assertEqual(
            self.channel._line_html_to_text('<p>x<script>alert(1)</script><style>p{}</style>y</p>'),
            'xy')

    def test_broken_html_keeps_text(self):
        out = self.channel._line_html_to_text('<p>a <a href="https://a.b/c">unclosed</p>')
        self.assertIn('unclosed', out)
        self.assertIn('https://a.b/c', out)

    def test_pure_helper_matches_channel_method(self):
        self.assertEqual(html_to_line_text(AI_QUOTE), self.channel._line_html_to_text(AI_QUOTE))

    def test_split_keeps_every_chunk_under_the_line_limit(self):
        text = '\n'.join(['一' * 3000] * 4)
        chunks = split_line_text(text)
        self.assertEqual(len(chunks), 4)
        self.assertTrue(all(len(c) <= LINE_TEXT_LIMIT for c in chunks))
        # emoji are 2 UTF-16 units each: LINE counts them that way
        chunks = split_line_text('😀' * 2600)
        self.assertEqual([len(c) for c in chunks], [2500, 100])
        self.assertEqual(split_line_text(''), [])
        self.assertEqual(split_line_text('short'), ['short'])


@tagged('post_install', '-at_install', 'line_ci')
class TestLineTextPush(TransactionCase):
    """What actually reaches the LINE push API for a bot/AI reply."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = cls.env['res.users'].create({
            'name': 'Text Push Operator',
            'login': 'line_text_push_operator',
            'email': 'line_text_push@test.com',
            'groups_id': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('im_livechat.im_livechat_group_user').id),
            ],
        })
        cls.bot = cls.env['res.partner'].create({'name': 'AI 客服助理'})
        cls.livechat = cls.env['im_livechat.channel'].create({'name': 'line text fixture'})
        cls.livechat.sudo().write({
            'user_ids': [(4, cls.operator.id)],
            'line_channel_id': FAKE_LINE_CHANNEL_ID,
            'line_channel_secret': FAKE_LINE_CHANNEL_SECRET,
            'line_enabled': True,
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'line text channel',
            'channel_type': 'livechat',
            'livechat_channel_id': cls.livechat.id,
            'livechat_active': True,
            'livechat_operator_id': cls.operator.partner_id.id,
            'line_user_id': 'Ulinetexttest00000000000000001',
            'channel_member_ids': [(0, 0, {'partner_id': cls.operator.partner_id.id})],
        })

    def _push(self, body):
        captured = []

        def capture_post(url, **kwargs):
            if '/bot/message/push' in url:
                captured.append(kwargs.get('json'))
            return route_mock_post(url, **kwargs)

        with patch('odoo.addons.woow_line_base.models.line_api_service.http_requests.post',
                   side_effect=capture_post):
            self.channel.message_post(
                body=Markup(body),
                author_id=self.bot.id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        self.assertTrue(captured, 'no push request reached LINE')
        return [m for request in captured for m in request['messages']]

    def test_ai_quote_reaches_line_with_addresses_and_rows(self):
        messages = self._push(AI_QUOTE)
        self.assertEqual(len(messages), 1)
        text = messages[0]['text']
        self.assertIn('https://aiot.woowtech.io/shop/four-channel-module-171', text)
        self.assertIn('・WOOW MATTER 家庭閘道器｜1 台｜NT$2,599', text)
        self.assertIn('官網商店 https://aiot.woowtech.io/shop ，謝謝。', text)
        self.assertNotIn('<', text.replace('<86', ''))

    def test_long_reply_is_split_into_several_text_messages(self):
        paragraph = '<p>%s</p>' % ('長' * 3000)
        messages = self._push(paragraph * 3)
        texts = [m['text'] for m in messages if m['type'] == 'text']
        self.assertEqual(len(texts), 3)
        self.assertTrue(all(len(t) <= LINE_TEXT_LIMIT for t in texts))
