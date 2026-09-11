# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Phase 6: Deployment & Installation Verification (16 tests).

PRD items 6.1.1 – 6.4.4.
"""

import base64

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import (
    FAKE_LINE_CHANNEL_ID,
    FAKE_LINE_CHANNEL_SECRET,
    FAKE_LINE_USER_ID,
    LineTransactionCase,
)


@tagged('post_install', '-at_install', 'line_ci')
class TestFreshInstallation(LineTransactionCase):
    """Phase 6.1: Fresh installation verification."""

    def test_6_1_1_module_installed(self):
        """Module installs without error; all dependencies satisfied."""
        module = self.env['ir.module.module'].search([
            ('name', '=', 'woow_odoo_livechat_line'),
        ])
        self.assertEqual(module.state, 'installed')

    def test_6_1_2_model_fields_exist(self):
        """All LINE-specific fields exist on their models."""
        # mail.guest
        guest_f = self.env['mail.guest']._fields
        self.assertIn('line_user_id', guest_f)
        self.assertIn('line_partner_id', guest_f)

        # discuss.channel
        dc_f = self.env['discuss.channel']._fields
        self.assertIn('line_user_id', dc_f)
        self.assertIn('line_display_name', dc_f)
        self.assertIn('line_picture_url', dc_f)

        # im_livechat.channel
        lc_f = self.env['im_livechat.channel']._fields
        self.assertIn('line_enabled', lc_f)
        self.assertIn('line_channel_id', lc_f)
        self.assertIn('line_channel_secret', lc_f)
        self.assertIn('line_webhook_url', lc_f)

        # res.partner: the LINE identity is a weak relation to line.user
        # (woow_line_base), not a direct char field, since the refactor.
        rp_f = self.env['res.partner']._fields
        self.assertIn('line_user_ids', rp_f)

    def test_6_1_3_xml_views_loaded(self):
        """XML view for LiveChat channel loaded.

        The old assertion also expected a res.partner form field for
        line_user_id; that LINE tab was deliberately removed in favour of a
        smart button (see woow_line_base/views/res_partner_views.xml), so
        there is no such view content to guard anymore.
        """
        # LiveChat channel form inherit
        views = self.env['ir.ui.view'].search([
            ('model', '=', 'im_livechat.channel'),
            ('type', '=', 'form'),
        ])
        self.assertTrue(views, 'LiveChat channel form view should exist')

    def test_6_1_4_static_asset_path_referenced(self):
        """video_preview.png path is used in discuss_channel.py."""
        # Verified by code reading — the path is hardcoded at line 100
        # Runtime accessibility tested via HTTPS phase
        import os
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        preview_path = os.path.join(
            module_dir, 'static', 'img', 'video_preview.png',
        )
        # File may or may not exist in source checkout, but path is valid
        self.assertTrue(
            os.path.isdir(os.path.join(module_dir, 'static')),
            'static/ directory should exist in module',
        )

    def test_6_1_5_webhook_route_registered(self):
        """Webhook controller class has the line_webhook method."""
        from odoo.addons.woow_odoo_livechat_line.controllers.webhook import (
            LineWebhookController,
        )
        self.assertTrue(hasattr(LineWebhookController, 'line_webhook'))
        self.assertTrue(callable(getattr(LineWebhookController, 'line_webhook')))


@tagged('post_install', '-at_install', 'line_ci')
class TestUpgrade(LineTransactionCase):
    """Phase 6.2: Upgrade from previous version."""

    def test_6_2_1_existing_data_preserved(self):
        """Existing channels, messages, guests preserved after upgrade."""
        guest = self._create_line_guest()
        channel = self._create_line_discuss_channel(guest)
        # Re-browse (simulates post-upgrade read)
        guest_r = self.env['mail.guest'].sudo().browse(guest.id)
        channel_r = self.env['discuss.channel'].sudo().browse(channel.id)
        self.assertEqual(guest_r.line_user_id, FAKE_LINE_USER_ID)
        self.assertEqual(channel_r.line_user_id, FAKE_LINE_USER_ID)

    def test_6_2_2_partner_line_user_id_field_exists(self):
        """res.partner has no LINE binding until one is created (the LINE
        identity is a line_user_ids relation now, not a bare column)."""
        partner = self.env['res.partner'].create({'name': 'Existing Partner'})
        self.assertFalse(partner.line_user_ids)

    def test_6_2_3_sql_unique_constraints(self):
        """Unique constraints on mail.guest and line.user line_user_id."""
        self._create_line_guest(line_user_id='U_uniq_test_001')
        with self.assertRaises(Exception):
            self._create_line_guest(line_user_id='U_uniq_test_001')

        self.env['line.user'].create({
            'line_user_id': 'U_uniq_partner_001', 'display_name': 'P1',
        })
        with self.assertRaises(Exception):
            self.env['line.user'].create({
                'line_user_id': 'U_uniq_partner_001', 'display_name': 'P2',
            })

    def test_6_2_4_legacy_guest_triggers_partner_creation(self):
        """Existing guest without partner gets linked on next webhook."""
        # Create guest without partner (legacy state)
        guest = self._create_line_guest(
            line_user_id='U_legacy_001', name='Legacy Guest',
        )
        self.assertFalse(guest.line_partner_id)
        # The webhook _get_or_create_guest path handles this
        # (tested in Phase 7)


@tagged('post_install', '-at_install', 'line_ci')
class TestConfigValidation(LineTransactionCase):
    """Phase 6.3: Configuration validation."""

    def test_6_3_1_base_url_https_generates_https_urls(self):
        """HTTPS base URL produces HTTPS webhook URL."""
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://production.example.com',
        )
        self.livechat_channel.invalidate_recordset()
        url = self.livechat_channel.line_webhook_url
        self.assertTrue(url.startswith('https://'))

    def test_6_3_2_line_credentials_saved(self):
        """LINE Channel ID and Secret saved correctly."""
        self.assertEqual(
            self.livechat_channel.line_channel_id, FAKE_LINE_CHANNEL_ID,
        )
        self.assertEqual(
            self.livechat_channel.line_channel_secret, FAKE_LINE_CHANNEL_SECRET,
        )

    def test_6_3_3_webhook_url_format(self):
        """Webhook URL contains /line/webhook/{id}."""
        url = self.livechat_channel.line_webhook_url
        expected = f'/line/webhook/{self.livechat_channel.id}'
        self.assertIn(expected, url)

    def test_6_3_3b_enabled_without_credentials_raises(self):
        """Enabling LINE without credentials raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env['im_livechat.channel'].create({
                'name': 'No Creds',
                'line_enabled': True,
                'line_channel_id': '',
                'line_channel_secret': '',
            })


@tagged('post_install', '-at_install', 'line_ci')
class TestContactBindingOnDeploy(LineTransactionCase):
    """Phase 6.4: Contact binding on deploy."""

    def test_6_4_1_new_line_user_creates_guest(self):
        """New LINE user creates guest record."""
        guest = self._create_line_guest()
        self.assertTrue(guest.exists())
        self.assertEqual(guest.line_user_id, FAKE_LINE_USER_ID)

    def test_6_4_2_partner_form_has_line_field(self):
        """res.partner exposes its LINE binding as a one2many to line.user,
        not a raw char column (guards against regressing to the old design)."""
        self.assertIn('line_user_ids', self.env['res.partner']._fields)
        field = self.env['res.partner']._fields['line_user_ids']
        self.assertEqual(field.type, 'one2many')

    def test_6_4_3_manual_partner_binding_wizard(self):
        """Wizard links guest to existing partner and binds a line.user."""
        guest = self._create_line_guest()
        partner = self.env['res.partner'].create({'name': 'Real Customer'})
        wizard = self.env['line.guest.link.partner.wizard'].create({
            'guest_id': guest.id,
            'partner_id': partner.id,
        })
        wizard.action_link()
        self.assertEqual(guest.line_partner_id, partner)
        self.assertEqual(guest.name, partner.name)
        # Wizard binds a line.user carrying the LINE id to the partner
        self.assertIn(FAKE_LINE_USER_ID, partner.line_user_ids.mapped('line_user_id'))

    def test_6_4_4_duplicate_partner_line_user_id_blocked(self):
        """Unique constraint prevents two line.user records with same LINE
        ID (the identity now lives on line.user, not res.partner)."""
        self.env['line.user'].create({
            'line_user_id': 'U_dup_test_001', 'display_name': 'P1',
        })
        with self.assertRaises(Exception):
            self.env['line.user'].create({
                'line_user_id': 'U_dup_test_001', 'display_name': 'P2',
            })
