# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Phase 13: Operations Procedures (15 tests).

PRD items 13.1.1 – 13.5.3.
"""

import base64
import time
from unittest.mock import patch

from odoo.tests import tagged

from .common import (
    FAKE_LINE_ACCESS_TOKEN,
    FAKE_LINE_CHANNEL_ID,
    FAKE_LINE_CHANNEL_SECRET,
    FAKE_LINE_USER_ID,
    LineTransactionCase,
    mock_line_push_response,
    mock_line_token_response,
)

MOCK_POST = 'odoo.addons.woow_odoo_livechat_line.models.line_api.requests.post'


@tagged('post_install', '-at_install')
class TestModuleUpgrade(LineTransactionCase):
    """Phase 13.1: Module upgrade and migration."""

    def test_13_1_1_module_installed_state(self):
        """Module is in installed state (upgrade-ready)."""
        module = self.env['ir.module.module'].search([
            ('name', '=', 'woow_odoo_livechat_line'),
        ])
        self.assertEqual(module.state, 'installed')

    def test_13_1_2_schema_fields_readable(self):
        """All fields can be read without error."""
        ch = self.livechat_channel
        _ = ch.line_enabled
        _ = ch.line_channel_id
        _ = ch.line_channel_secret
        _ = ch.line_webhook_url
        self.assertTrue(True)

    def test_13_1_3_rollback_documented(self):
        """Rollback path documented."""
        self.skipTest('Documentation verification; not testable in code')

    def test_13_1_4_version_compatible(self):
        """Module version matches Odoo 18."""
        module = self.env['ir.module.module'].search([
            ('name', '=', 'woow_odoo_livechat_line'),
        ])
        self.assertTrue(module.installed_version.startswith('18.0'))


@tagged('post_install', '-at_install')
class TestLineAccountLifecycle(LineTransactionCase):
    """Phase 13.2: LINE account lifecycle."""

    @patch(MOCK_POST)
    def test_13_2_1_token_expiry_refresh(self, mock_post):
        """Expired token triggers re-auth from LINE API."""
        from odoo.addons.woow_odoo_livechat_line.models import line_api
        line_api._token_cache.clear()

        # Populate cache with expired token
        line_api._token_cache[FAKE_LINE_CHANNEL_ID] = {
            'token': 'expired_token',
            'expires_at': time.time() - 100,
        }

        mock_post.return_value = mock_line_token_response()
        token = self.livechat_channel._line_get_access_token(
            FAKE_LINE_CHANNEL_ID, FAKE_LINE_CHANNEL_SECRET,
        )
        self.assertEqual(token, FAKE_LINE_ACCESS_TOKEN)
        mock_post.assert_called_once()

    def test_13_2_2_messaging_quota(self):
        """LINE messaging quota handling."""
        self.skipTest('Quota handling not yet implemented')

    def test_13_2_3_credential_rotation(self):
        """Updating LINE credentials in Odoo."""
        self.livechat_channel.write({
            'line_channel_secret': 'new_secret_value_32chars_long___',
        })
        self.assertEqual(
            self.livechat_channel.line_channel_secret,
            'new_secret_value_32chars_long___',
        )

    def test_13_2_4_webhook_url_reflects_base_url(self):
        """Webhook URL updates when base URL changes."""
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://new-domain.example.com',
        )
        self.livechat_channel.invalidate_recordset()
        url = self.livechat_channel.line_webhook_url
        self.assertIn('new-domain.example.com', url)


@tagged('post_install', '-at_install')
class TestIncidentResponse(LineTransactionCase):
    """Phase 13.3: Incident response."""

    @patch(MOCK_POST)
    def test_13_3_1_line_platform_outage(self, mock_post):
        """LINE platform 5xx returns False (no crash)."""
        mock_post.return_value = mock_line_push_response(success=False)
        result = self.livechat_channel._line_push_message(
            FAKE_LINE_ACCESS_TOKEN, FAKE_LINE_USER_ID,
            [{'type': 'text', 'text': 'during outage'}],
        )
        self.assertFalse(result)

    def test_13_3_2_database_connection_lost(self):
        """Database connection loss handling."""
        self.skipTest('Requires DB connection manipulation')

    def test_13_3_3_container_oom_kill(self):
        """Container OOM recovery."""
        self.skipTest('Infrastructure-level test')

    def test_13_3_4_disk_full(self):
        """Disk full error handling."""
        self.skipTest('Infrastructure-level test')


@tagged('post_install', '-at_install')
class TestBackupRestore(LineTransactionCase):
    """Phase 13.4: Backup and restore."""

    def test_13_4_1_line_data_in_database(self):
        """LINE data stored in DB (included in pg_dump)."""
        guest = self._create_line_guest(line_user_id='U_backup_test')
        self._create_line_discuss_channel(
            guest, line_user_id='U_backup_test',
        )
        self.env.cr.execute(
            'SELECT line_user_id FROM mail_guest WHERE id = %s',
            (guest.id,),
        )
        row = self.env.cr.fetchone()
        self.assertEqual(row[0], 'U_backup_test')

    def test_13_4_2_attachments_in_filestore(self):
        """Attachments have storage reference."""
        att = self.env['ir.attachment'].create({
            'name': 'line_backup_test.png',
            'datas': base64.b64encode(b'fake png data'),
        })
        self.assertTrue(att.store_fname or att.db_datas)

    def test_13_4_3_restore_updates_webhook_url(self):
        """Webhook URL reflects new domain after restore."""
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://restored.example.com',
        )
        self.livechat_channel.invalidate_recordset()
        url = self.livechat_channel.line_webhook_url
        self.assertIn('restored.example.com', url)


@tagged('post_install', '-at_install')
class TestCapacityPlanning(LineTransactionCase):
    """Phase 13.5: Capacity planning."""

    def test_13_5_1_storage_growth_queryable(self):
        """Attachment storage size queryable."""
        self.env.cr.execute(
            'SELECT COALESCE(SUM(file_size), 0) FROM ir_attachment',
        )
        total = self.env.cr.fetchone()[0]
        self.assertIsInstance(total, int)

    def test_13_5_2_rate_limits_documented(self):
        """LINE API rate limits documented."""
        self.skipTest('Documentation verification; not testable in code')

    def test_13_5_3_db_connection_pool_sizing(self):
        """DB connection pool configured."""
        self.skipTest('Infrastructure configuration test')
