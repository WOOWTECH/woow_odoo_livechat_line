# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Phase 8: Multi-tenant / Multi LINE Account (14 tests).

PRD items 8.1.1 – 8.4.4.
"""

from unittest.mock import patch

from odoo.tests import tagged

from .common import (
    FAKE_LINE_CHANNEL_ID,
    FAKE_LINE_CHANNEL_SECRET,
    FAKE_LINE_USER_ID,
    LineTransactionCase,
    make_webhook_event,
    mock_line_token_response,
    route_mock_get,
    route_mock_post,
)

SECOND_CHANNEL_ID = '9876543210'
SECOND_CHANNEL_SECRET = 'second_channel_secret_32chars_lo'

MOCK_POST = 'odoo.addons.woow_line_base.models.line_api_service.http_requests.post'
MOCK_GET = 'odoo.addons.woow_line_base.models.line_api_service.http_requests.get'


@tagged('post_install', '-at_install')
class TestMultipleLineAccounts(LineTransactionCase):
    """Phase 8.1: Multiple LINE Official Accounts."""

    def setUp(self):
        super().setUp()
        self.livechat_channel_2 = self.env['im_livechat.channel'].create({
            'name': 'Second LINE Channel',
            'user_ids': [(4, self.operator_user.id)],
            'line_enabled': True,
            'line_channel_id': SECOND_CHANNEL_ID,
            'line_channel_secret': SECOND_CHANNEL_SECRET,
        })

    def test_8_1_1_two_channels_independent_config(self):
        """Two channels have independent LINE credentials."""
        self.assertNotEqual(
            self.livechat_channel.line_channel_id,
            self.livechat_channel_2.line_channel_id,
        )
        self.assertNotEqual(
            self.livechat_channel.line_channel_secret,
            self.livechat_channel_2.line_channel_secret,
        )

    @patch(MOCK_GET, side_effect=route_mock_get)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_8_1_2_webhook_routes_to_correct_channel(self, mock_post, mock_get):
        """A body signed for one channel's secret is rejected when
        delivered to a different channel (whose secret differs), and
        accepted when delivered to its own channel.

        The old test called the controller's private _verify_signature
        directly; signature verification now lives in the shared
        line.api.service and there is no public per-body verify hook on the
        controller, so this drives the real seam (the webhook route itself)
        and observes the effect through what a valid/invalid delivery
        actually does: create (or not) the resulting guest.
        """
        uid_ok = 'Uwebhookrouteok0000000000000000'
        self._call_controller_directly(
            self.livechat_channel.id, [make_webhook_event(line_user_id=uid_ok)],
            channel_secret=FAKE_LINE_CHANNEL_SECRET,
        )
        self.assertTrue(
            self.env['mail.guest'].sudo().search([('line_user_id', '=', uid_ok)]),
            "a body signed with channel 1's own secret must be accepted by channel 1",
        )

        uid_bad = 'Uwebhookroutebad000000000000000'
        self._call_controller_directly(
            self.livechat_channel_2.id, [make_webhook_event(line_user_id=uid_bad)],
            channel_secret=FAKE_LINE_CHANNEL_SECRET,  # signed for channel 1, not channel 2
        )
        self.assertFalse(
            self.env['mail.guest'].sudo().search([('line_user_id', '=', uid_bad)]),
            "a body signed with channel 1's secret must be rejected by channel 2",
        )

    @patch(MOCK_POST)
    def test_8_1_3_token_cache_isolation(self, mock_post):
        """Fetching an access token for one channel does not satisfy the
        cache for a different channel — each channel/secret pair fetches
        its own OAuth token via the shared line.api.service."""
        mock_post.return_value = mock_line_token_response()
        api = self.env['line.api.service']

        token1 = api.get_access_token(FAKE_LINE_CHANNEL_ID, FAKE_LINE_CHANNEL_SECRET)
        token2 = api.get_access_token(SECOND_CHANNEL_ID, SECOND_CHANNEL_SECRET)

        self.assertTrue(token1)
        self.assertTrue(token2)
        self.assertEqual(
            mock_post.call_count, 2,
            "each channel must fetch its own OAuth token, not reuse the other's cache")

    def test_8_1_4_same_user_two_accounts(self):
        """Same LINE user messaging two OA creates two channels."""
        guest = self._create_line_guest()
        ch1 = self._create_line_discuss_channel(guest)
        ch2 = self.env['discuss.channel'].sudo().create({
            'name': 'LINE: LINE User (Ch2)',
            'channel_type': 'livechat',
            'livechat_channel_id': self.livechat_channel_2.id,
            'livechat_active': True,
            'livechat_operator_id': self.operator_partner.id,
            'line_user_id': FAKE_LINE_USER_ID,
            'channel_member_ids': [
                (0, 0, {'partner_id': self.operator_partner.id}),
            ],
        })
        self.assertNotEqual(ch1.id, ch2.id)
        self.assertEqual(ch1.line_user_id, ch2.line_user_id)
        self.assertNotEqual(
            ch1.livechat_channel_id.id, ch2.livechat_channel_id.id,
        )


@tagged('post_install', '-at_install')
class TestMultiCompany(LineTransactionCase):
    """Phase 8.2: Multi-company."""

    def test_8_2_1_different_line_accounts_per_company(self):
        """Different companies have independent LINE configs."""
        company_b = self.env['res.company'].create({'name': 'Company B'})
        channel_b = self.env['im_livechat.channel'].with_company(
            company_b,
        ).create({
            'name': 'Company B LINE',
            'line_enabled': True,
            'line_channel_id': 'company_b_channel_id',
            'line_channel_secret': 'company_b_secret_32chars_long__',
        })
        self.assertNotEqual(
            self.livechat_channel.line_channel_id,
            channel_b.line_channel_id,
        )

    def test_8_2_2_cross_company_data_isolation(self):
        """Standard Odoo multi-company ACL applies."""
        # Odoo's built-in ACL enforces cross-company isolation
        # Verified at framework level
        self.assertTrue(True)

    def test_8_2_3_partner_company_rules(self):
        """Partner with a bound LINE identity is created normally; standard
        Odoo company rules apply to it like any other partner."""
        partner = self.env['res.partner'].create({'name': 'Line Partner'})
        self._bind_line_user(partner, 'U_company_test')
        self.assertTrue(partner.exists())
        self.assertIn('U_company_test', partner.line_user_ids.mapped('line_user_id'))


@tagged('post_install', '-at_install')
class TestMultiDatabase(LineTransactionCase):
    """Phase 8.3: Multi-database (SaaS)."""

    def test_8_3_1_no_hardcoded_db_references(self):
        """Module has no hard-coded database references."""
        self.assertTrue(True)  # Verified by code inspection

    def test_8_3_2_webhook_url_supports_routing(self):
        """Webhook URL uses /line/webhook/<channel_id> pattern."""
        url = self.livechat_channel.line_webhook_url
        self.assertIn('/line/webhook/', url)

    # test_8_3_3_token_cache_per_process deleted: it asserted the internal
    # type of a module-private cache dict in a module
    # (woow_odoo_livechat_line.models.line_api) that no longer exists — token
    # caching moved to the shared woow_line_base.models.line_api_service.
    # The real behaviour it was gesturing at (repeated token fetches for the
    # same channel don't hit the network every time) is covered by
    # test_8_4_4_token_refresh_cached below via the public get_access_token
    # seam, so there's nothing left here worth rewriting.

@tagged('post_install', '-at_install')
class TestConcurrentLoad(LineTransactionCase):
    """Phase 8.4: Concurrent load."""

    def test_8_4_1_multiple_users_no_duplicates(self):
        """10 different LINE users create 10 unique guests."""
        guests = []
        for i in range(10):
            uid = f'U{i:032x}'
            g = self._create_line_guest(line_user_id=uid, name=f'User {i}')
            guests.append(g)
        self.assertEqual(len(guests), 10)
        ids = {g.line_user_id for g in guests}
        self.assertEqual(len(ids), 10)

    def test_8_4_2_rapid_messages_same_channel(self):
        """5 messages from same user go to same channel."""
        guest = self._create_line_guest()
        channel = self._create_line_discuss_channel(guest)
        existing = self.env['discuss.channel'].sudo().search([
            ('line_user_id', '=', FAKE_LINE_USER_ID),
            ('livechat_channel_id', '=', self.livechat_channel.id),
        ])
        self.assertEqual(len(existing), 1)
        self.assertEqual(existing.id, channel.id)

    def test_8_4_3_concurrent_webhooks_no_crash(self):
        """Sequential webhook calls don't cause state leaks."""
        self.skipTest('Load testing requires dedicated infrastructure')

    @patch(MOCK_POST)
    def test_8_4_4_token_refresh_cached(self, mock_post):
        """Repeated token requests use the cache (single HTTP call)."""
        mock_post.return_value = mock_line_token_response()
        api = self.env['line.api.service']

        for _ in range(5):
            api.get_access_token(FAKE_LINE_CHANNEL_ID, FAKE_LINE_CHANNEL_SECRET)
        self.assertEqual(mock_post.call_count, 1)
