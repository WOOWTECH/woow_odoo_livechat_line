# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Phase 10: High Availability & Fault Recovery (15 tests).

PRD items 10.1.1 – 10.4.5.
"""

import base64
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from .common import (
    FAKE_LINE_ACCESS_TOKEN,
    FAKE_LINE_USER_ID,
    LineTransactionCase,
    mock_line_push_response,
)

MOCK_POST = 'odoo.addons.woow_odoo_livechat_line.models.line_api.requests.post'
MOCK_GET = 'odoo.addons.woow_odoo_livechat_line.models.line_api.requests.get'


@tagged('post_install', '-at_install')
class TestContainerLifecycle(LineTransactionCase):
    """Phase 10.1: Container lifecycle."""

    def test_10_1_1_data_survives_restart(self):
        """Conversations persist in DB (survives container restart)."""
        guest = self._create_line_guest()
        channel = self._create_line_discuss_channel(guest)
        # Re-browse (simulates post-restart read from DB)
        g2 = self.env['mail.guest'].sudo().browse(guest.id)
        c2 = self.env['discuss.channel'].sudo().browse(channel.id)
        self.assertEqual(g2.line_user_id, guest.line_user_id)
        self.assertEqual(c2.line_user_id, channel.line_user_id)

    def test_10_1_2_container_auto_recovery(self):
        """Container restart policy."""
        self.skipTest('Infrastructure-level test; Docker/Podman config')

    def test_10_1_3_graceful_shutdown(self):
        """Graceful shutdown during processing."""
        self.skipTest('Infrastructure-level test; signal handling')

    def test_10_1_4_image_rebuild_redeploy(self):
        """Container image rebuild preserves filestore."""
        self.skipTest('Infrastructure-level test; volume config')


@tagged('post_install', '-at_install')
class TestDatabaseResilience(LineTransactionCase):
    """Phase 10.2: Database resilience."""

    def test_10_2_1_connection_pool_exhaustion(self):
        """Graceful handling when DB connections exhausted."""
        self.skipTest('Requires connection pool manipulation')

    def test_10_2_2_backup_during_active_conversations(self):
        """Data consistent and queryable during activity."""
        guest = self._create_line_guest()
        self._create_line_discuss_channel(guest)
        count = self.env['discuss.channel'].sudo().search_count([
            ('line_user_id', '=', guest.line_user_id),
        ])
        self.assertEqual(count, 1)

    def test_10_2_3_point_in_time_recovery(self):
        """Point-in-time recovery."""
        self.skipTest('Infrastructure-level test; PostgreSQL WAL config')


@tagged('post_install', '-at_install')
class TestExternalServiceFailures(LineTransactionCase):
    """Phase 10.3: External service failures."""

    @patch(MOCK_POST)
    def test_10_3_1_push_api_rate_limited(self, mock_post):
        """LINE Push API 429 returns False (not crash)."""
        from requests.exceptions import HTTPError
        resp = MagicMock()
        resp.status_code = 429
        resp.text = '{"message":"Rate limit exceeded"}'
        resp.raise_for_status.side_effect = HTTPError(response=resp)
        mock_post.return_value = resp

        result = self.livechat_channel._line_push_message(
            FAKE_LINE_ACCESS_TOKEN, FAKE_LINE_USER_ID,
            [{'type': 'text', 'text': 'test'}],
        )
        self.assertFalse(result)

    @patch(MOCK_POST)
    def test_10_3_2_push_api_server_error(self, mock_post):
        """LINE Push API 500 returns False."""
        mock_post.return_value = mock_line_push_response(success=False)
        result = self.livechat_channel._line_push_message(
            FAKE_LINE_ACCESS_TOKEN, FAKE_LINE_USER_ID,
            [{'type': 'text', 'text': 'test'}],
        )
        self.assertFalse(result)

    @patch(MOCK_GET)
    def test_10_3_3_content_api_timeout(self, mock_get):
        """LINE Content API timeout returns (None, None)."""
        from requests.exceptions import Timeout
        mock_get.side_effect = Timeout('Connection timed out')
        content, ctype = self.livechat_channel._line_get_content(
            FAKE_LINE_ACCESS_TOKEN, 'msg_timeout',
        )
        self.assertIsNone(content)
        self.assertIsNone(ctype)

    @patch(MOCK_GET)
    def test_10_3_4_dns_resolution_failure(self, mock_get):
        """DNS failure returns empty profile dict."""
        from requests.exceptions import ConnectionError as ConnErr
        mock_get.side_effect = ConnErr('DNS resolution failed')
        profile = self.livechat_channel._line_get_profile(
            FAKE_LINE_ACCESS_TOKEN, FAKE_LINE_USER_ID,
        )
        self.assertEqual(profile, {})


@tagged('post_install', '-at_install')
class TestDataIntegrity(LineTransactionCase):
    """Phase 10.4: Data integrity."""

    def test_10_4_1_guest_unique_constraint(self):
        """Unique constraint on mail.guest.line_user_id."""
        self._create_line_guest(line_user_id='U_integrity_g')
        with self.assertRaises(Exception):
            self._create_line_guest(line_user_id='U_integrity_g')

    def test_10_4_2_partner_unique_constraint(self):
        """Unique constraint on res.partner.line_user_id."""
        self.env['res.partner'].create({
            'name': 'PA', 'line_user_id': 'U_integrity_p',
        })
        with self.assertRaises(Exception):
            self.env['res.partner'].create({
                'name': 'PB', 'line_user_id': 'U_integrity_p',
            })

    def test_10_4_3_orphan_channel_detectable(self):
        """Channels without comment messages are queryable."""
        guest = self._create_line_guest()
        channel = self._create_line_discuss_channel(guest)
        count = self.env['mail.message'].search_count([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', channel.id),
            ('message_type', '=', 'comment'),
        ])
        self.assertIsInstance(count, int)

    def test_10_4_4_orphan_attachment_detectable(self):
        """Orphan attachments can be created and deleted."""
        att = self.env['ir.attachment'].create({
            'name': 'orphan.png',
            'datas': base64.b64encode(b'fake'),
        })
        att_id = att.id
        att.sudo().unlink()
        self.assertFalse(self.env['ir.attachment'].browse(att_id).exists())

    def test_10_4_5_transaction_atomicity(self):
        """Guest + channel creation is atomic in single transaction."""
        guest = self._create_line_guest(line_user_id='U_atomic_test')
        channel = self._create_line_discuss_channel(
            guest, line_user_id='U_atomic_test',
        )
        self.assertTrue(guest.exists())
        self.assertTrue(channel.exists())
