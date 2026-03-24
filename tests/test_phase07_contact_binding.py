# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Phase 7: Contact Identification & Binding (18 tests).

PRD items 7.1.1 – 7.4.4.
"""

from unittest.mock import patch, MagicMock

from odoo.tests import tagged

from .common import (
    FAKE_LINE_ACCESS_TOKEN,
    FAKE_LINE_CHANNEL_ID,
    FAKE_LINE_CHANNEL_SECRET,
    FAKE_LINE_DISPLAY_NAME,
    FAKE_LINE_USER_ID,
    LineTransactionCase,
    make_webhook_event,
    mock_line_profile_response,
    mock_line_token_response,
    mock_line_content_response,
    route_mock_get,
    route_mock_post,
)

MOCK_POST = 'odoo.addons.woow_odoo_livechat_line.models.line_api.requests.post'
MOCK_GET = 'odoo.addons.woow_odoo_livechat_line.models.line_api.requests.get'


@tagged('post_install', '-at_install')
class TestProfileAPI(LineTransactionCase):
    """Phase 7.1: LINE Profile API integration."""

    @patch(MOCK_GET, side_effect=route_mock_get)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_1_1_first_message_calls_profile_api(self, mock_post, mock_get):
        """First message from new LINE user calls Profile API."""
        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id='U' + 'a' * 32)],
        )
        # Profile GET should have been called
        profile_calls = [
            c for c in mock_get.call_args_list
            if '/bot/profile/' in str(c)
        ]
        self.assertTrue(
            len(profile_calls) >= 1,
            'Profile API should be called for new user',
        )

    @patch(MOCK_GET, side_effect=route_mock_get)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_1_2_profile_display_name_updates_guest(self, mock_post, mock_get):
        """Profile API displayName sets guest name."""
        uid = 'U' + 'b' * 32
        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id=uid)],
        )
        guest = self.env['mail.guest'].sudo().search([
            ('line_user_id', '=', uid),
        ])
        self.assertEqual(guest.name, FAKE_LINE_DISPLAY_NAME)

    @patch(MOCK_GET, side_effect=route_mock_get)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_1_3_profile_api_creates_partner(self, mock_post, mock_get):
        """Profile API call also auto-creates res.partner."""
        uid = 'U' + 'c' * 32
        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id=uid)],
        )
        partner = self.env['res.partner'].sudo().search([
            ('line_user_id', '=', uid),
        ])
        self.assertTrue(partner.exists())
        self.assertEqual(partner.name, FAKE_LINE_DISPLAY_NAME)

    @patch(MOCK_GET, side_effect=route_mock_get)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_1_4_profile_api_not_called_for_existing(self, mock_post, mock_get):
        """Second message from same user does NOT call Profile API."""
        uid = 'U' + 'd' * 32
        # Create existing guest with partner (complete record)
        guest = self._create_line_guest(line_user_id=uid, name='Known User')
        partner = self.env['res.partner'].create({
            'name': 'Known User', 'line_user_id': uid,
        })
        guest.write({'line_partner_id': partner.id})

        mock_get.reset_mock()
        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id=uid)],
        )
        profile_calls = [
            c for c in mock_get.call_args_list
            if '/bot/profile/' in str(c)
        ]
        self.assertEqual(
            len(profile_calls), 0,
            'Profile API should NOT be called for complete existing guest',
        )

    @patch(MOCK_GET)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_1_5_profile_api_timeout_fallback(self, mock_post, mock_get):
        """Profile API timeout falls back to 'LINE User' name."""
        from requests.exceptions import Timeout
        mock_get.side_effect = Timeout('Connection timed out')

        uid = 'U' + 'e' * 32
        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id=uid)],
        )
        guest = self.env['mail.guest'].sudo().search([
            ('line_user_id', '=', uid),
        ])
        self.assertTrue(guest.exists())
        self.assertEqual(guest.name, 'LINE User')

    @patch(MOCK_GET)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_1_6_profile_api_404_graceful(self, mock_post, mock_get):
        """Profile API 404 (user blocked bot) handled gracefully."""
        from requests.exceptions import HTTPError
        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_404.text = '{"message":"Not found"}'
        resp_404.raise_for_status.side_effect = HTTPError(response=resp_404)
        mock_get.return_value = resp_404

        uid = 'U' + 'f' * 32
        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id=uid)],
        )
        guest = self.env['mail.guest'].sudo().search([
            ('line_user_id', '=', uid),
        ])
        self.assertTrue(guest.exists())


@tagged('post_install', '-at_install')
class TestAutoPartnerCreation(LineTransactionCase):
    """Phase 7.2: Auto partner creation."""

    @patch(MOCK_GET, side_effect=route_mock_get)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_2_1_new_guest_creates_partner(self, mock_post, mock_get):
        """New guest auto-creates res.partner with line_user_id."""
        uid = 'U' + '1' * 32
        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id=uid)],
        )
        partner = self.env['res.partner'].sudo().search([
            ('line_user_id', '=', uid),
        ])
        self.assertTrue(partner.exists())
        self.assertEqual(partner.name, FAKE_LINE_DISPLAY_NAME)

    @patch(MOCK_GET, side_effect=route_mock_get)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_2_2_legacy_guest_gets_partner(self, mock_post, mock_get):
        """Existing guest without partner gets partner on next message."""
        uid = 'U' + '2' * 32
        guest = self._create_line_guest(line_user_id=uid, name='LINE User')
        self.assertFalse(guest.line_partner_id)

        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id=uid)],
        )
        guest.invalidate_recordset()
        self.assertTrue(guest.line_partner_id)

    def test_7_2_3_partner_line_user_id_unique(self):
        """Partner line_user_id unique constraint enforced."""
        self.env['res.partner'].create({
            'name': 'A', 'line_user_id': 'U_unique_p_001',
        })
        with self.assertRaises(Exception):
            self.env['res.partner'].create({
                'name': 'B', 'line_user_id': 'U_unique_p_001',
            })

    @patch(MOCK_GET, side_effect=route_mock_get)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_2_4_guest_partner_id_linked(self, mock_post, mock_get):
        """Guest partner_id points to auto-created partner."""
        uid = 'U' + '3' * 32
        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id=uid)],
        )
        guest = self.env['mail.guest'].sudo().search([
            ('line_user_id', '=', uid),
        ])
        self.assertTrue(guest.line_partner_id)
        self.assertEqual(guest.line_partner_id.line_user_id, uid)


@tagged('post_install', '-at_install')
class TestManualBindingWizard(LineTransactionCase):
    """Phase 7.3: Manual binding wizard."""

    def test_7_3_1_open_wizard_from_guest(self):
        """action_link_to_partner returns correct wizard action."""
        guest = self._create_line_guest()
        action = guest.action_link_to_partner()
        self.assertEqual(action['res_model'], 'line.guest.link.partner.wizard')
        self.assertEqual(action['view_mode'], 'form')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_guest_id'], guest.id)

    def test_7_3_2_link_guest_to_partner(self):
        """Wizard links guest to partner; syncs line_user_id."""
        guest = self._create_line_guest()
        partner = self.env['res.partner'].create({'name': 'Customer A'})
        wizard = self.env['line.guest.link.partner.wizard'].create({
            'guest_id': guest.id,
            'partner_id': partner.id,
        })
        result = wizard.action_link()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        self.assertEqual(guest.line_partner_id, partner)
        self.assertEqual(guest.name, 'Customer A')
        self.assertEqual(partner.line_user_id, FAKE_LINE_USER_ID)

    def test_7_3_3_link_partner_with_existing_line_id(self):
        """Wizard does not overwrite existing partner line_user_id."""
        guest = self._create_line_guest()
        partner = self.env['res.partner'].create({
            'name': 'Has LINE', 'line_user_id': 'U_existing_id',
        })
        wizard = self.env['line.guest.link.partner.wizard'].create({
            'guest_id': guest.id,
            'partner_id': partner.id,
        })
        wizard.action_link()
        # Partner already had a line_user_id; wizard should not overwrite
        self.assertEqual(partner.line_user_id, 'U_existing_id')

    def test_7_3_4_unlink_guest_partner(self):
        """Clearing guest.line_partner_id disconnects the link."""
        guest = self._create_line_guest()
        partner = self.env['res.partner'].create({'name': 'To Unlink'})
        guest.write({'line_partner_id': partner.id})
        self.assertEqual(guest.line_partner_id, partner)
        guest.write({'line_partner_id': False})
        self.assertFalse(guest.line_partner_id)


@tagged('post_install', '-at_install')
class TestContactEdgeCases(LineTransactionCase):
    """Phase 7.4: Edge cases."""

    @patch(MOCK_GET)
    @patch(MOCK_POST, side_effect=route_mock_post)
    def test_7_4_1_display_name_change(self, mock_post, mock_get):
        """Legacy guest with generic name gets updated on next message."""
        uid = 'U' + '4' * 32
        guest = self._create_line_guest(line_user_id=uid, name='LINE User')
        partner = self.env['res.partner'].create({
            'name': 'LINE User', 'line_user_id': uid,
        })
        guest.write({'line_partner_id': partner.id})

        # Profile returns new name
        mock_get.return_value = mock_line_profile_response(
            display_name='New Name',
        )

        self._call_controller_directly(
            self.livechat_channel.id,
            [make_webhook_event(line_user_id=uid)],
        )
        guest.invalidate_recordset()
        self.assertEqual(guest.name, 'New Name')

    def test_7_4_2_identical_display_names(self):
        """Two LINE users with same name create separate guests."""
        g1 = self._create_line_guest(line_user_id='U' + 'a' * 32, name='Same')
        g2 = self._create_line_guest(line_user_id='U' + 'b' * 32, name='Same')
        self.assertNotEqual(g1.id, g2.id)
        self.assertEqual(g1.name, g2.name)
        self.assertNotEqual(g1.line_user_id, g2.line_user_id)

    def test_7_4_3_line_user_id_stored_as_is(self):
        """LINE user ID stored without format validation."""
        guest = self._create_line_guest(line_user_id='U0123456789abcdef0123456789abcdef')
        self.assertEqual(guest.line_user_id, 'U0123456789abcdef0123456789abcdef')

    def test_7_4_4_partner_merge_conflict(self):
        """Two partners with different LINE IDs remain distinct."""
        p1 = self.env['res.partner'].create({
            'name': 'P1', 'line_user_id': 'U_merge_001',
        })
        p2 = self.env['res.partner'].create({
            'name': 'P2', 'line_user_id': 'U_merge_002',
        })
        self.assertNotEqual(p1.line_user_id, p2.line_user_id)
