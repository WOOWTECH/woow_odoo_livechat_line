# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Regression tests for the 2026-09 pre-deployment fixes."""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'line_ci')
class TestChannelSecretAccess(TransactionCase):
    """B-1: the LINE credentials sat on a model that Portal and Public can
    read, with no ORM-level restriction at all."""

    def test_credential_fields_are_group_restricted(self):
        fields = self.env['im_livechat.channel']._fields
        for name in ('line_channel_id', 'line_channel_secret'):
            self.assertEqual(
                fields[name].groups, 'im_livechat.im_livechat_group_manager',
                f'{name} must stay restricted — a view-level password widget '
                f'does not stop an RPC read')

    def test_non_credential_field_stays_open(self):
        """The restriction must not spill onto fields the UI needs."""
        self.assertFalse(self.env['im_livechat.channel']._fields['line_enabled'].groups)


@tagged('post_install', '-at_install', 'line_ci')
class TestHtmlToText(TransactionCase):
    """H-1: operator replies arrived on the customer's phone as one run-on
    line, because a bare tag-strip drops every block boundary."""

    def setUp(self):
        super().setUp()
        self.channel = self.env['discuss.channel']

    def test_br_becomes_a_newline(self):
        out = self.channel._line_html_to_text('<p>line one<br/>line two</p>')
        self.assertIn('\n', out)
        self.assertEqual(out.splitlines(), ['line one', 'line two'])

    def test_block_close_separates_lines(self):
        out = self.channel._line_html_to_text('<div>12:00</div><div>台北市</div>')
        self.assertEqual(out.splitlines(), ['12:00', '台北市'])

    def test_entities_are_unescaped(self):
        self.assertEqual(self.channel._line_html_to_text('<p>A &amp; B</p>'), 'A & B')

    def test_list_items_get_a_bullet(self):
        out = self.channel._line_html_to_text('<ul><li>one</li><li>two</li></ul>')
        self.assertIn('•', out)
        self.assertEqual(len([l for l in out.splitlines() if l.strip()]), 2)

    def test_blank_input_is_safe(self):
        self.assertEqual(self.channel._line_html_to_text(''), '')
        self.assertEqual(self.channel._line_html_to_text(False), '')


@tagged('post_install', '-at_install', 'line_ci')
class TestDeliveryFailureIsVisible(TransactionCase):
    """新-1: the operator reply path was the one caller using the low-level
    push that neither logs nor filters, so every failure was silent while
    Discuss still showed the message as sent."""

    def test_failure_notice_is_posted_to_the_channel(self):
        # A plain channel is enough: the notice only goes through message_post.
        # A livechat-typed channel would need livechat_operator_id to satisfy
        # discuss_channel_livechat_operator_id.
        channel = self.env['discuss.channel'].create({'name': 'line delivery test'})
        before = len(channel.message_ids)
        channel._post_line_delivery_failure('測試原因')
        channel.invalidate_recordset()
        self.assertGreater(
            len(channel.message_ids), before,
            'a failed delivery must leave a visible trace in the conversation')
        self.assertIn('測試原因', channel.message_ids[0].body)

    def test_notice_does_not_loop_back_out(self):
        """The notice is posted with from_line_webhook so the outbound hook
        skips it — otherwise every failure would trigger another send."""
        import inspect
        src = inspect.getsource(
            type(self.env['discuss.channel'])._post_line_delivery_failure)
        self.assertIn('from_line_webhook', src)
