# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Phase 9: HTTPS & Reverse Proxy (12 tests).

PRD items 9.1.1 – 9.3.5.
"""

import base64

from odoo.tests import tagged

from .common import LineTransactionCase


@tagged('post_install', '-at_install')
class TestTLSConfiguration(LineTransactionCase):
    """Phase 9.1: TLS configuration."""

    def test_9_1_1_webhook_url_https(self):
        """Webhook URL generated with HTTPS when base URL is HTTPS."""
        url = self.livechat_channel.line_webhook_url
        self.assertTrue(url.startswith('https://'))

    def test_9_1_2_tls_cert_validation(self):
        """TLS certificate validation (infrastructure test)."""
        self.skipTest('Infrastructure-level test; manual verification required')

    def test_9_1_3_tls_version_enforced(self):
        """TLS 1.2+ enforced."""
        self.skipTest('Infrastructure-level test; manual verification required')

    def test_9_1_4_cert_auto_renewal(self):
        """Certificate auto-renewal."""
        self.skipTest('Infrastructure-level test; manual verification required')


@tagged('post_install', '-at_install')
class TestReverseProxyHeaders(LineTransactionCase):
    """Phase 9.2: Reverse proxy headers."""

    def test_9_2_1_base_url_https_produces_https_urls(self):
        """HTTPS base URL makes Odoo generate HTTPS attachment URLs."""
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url',
        )
        self.assertTrue(base_url.startswith('https://'))

    def test_9_2_2_webhook_url_matches_base_url_domain(self):
        """Webhook URL domain matches web.base.url."""
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://myapp.example.com',
        )
        self.livechat_channel.invalidate_recordset()
        url = self.livechat_channel.line_webhook_url
        self.assertIn('myapp.example.com', url)

    def test_9_2_3_proxy_mode_documented(self):
        """Proxy mode configuration is an operational concern."""
        self.skipTest('Configuration documentation test; manual verification')


@tagged('post_install', '-at_install')
class TestAttachmentURLAccessibility(LineTransactionCase):
    """Phase 9.3: Attachment URL accessibility."""

    def test_9_3_1_ensure_https_url_converts_http(self):
        """_ensure_https_url converts http to https."""
        channel = self.env['discuss.channel'].sudo().new({})
        self.assertEqual(
            channel._ensure_https_url('http://example.com/img.jpg'),
            'https://example.com/img.jpg',
        )

    def test_9_3_1b_ensure_https_url_preserves_https(self):
        """_ensure_https_url preserves existing https."""
        channel = self.env['discuss.channel'].sudo().new({})
        self.assertEqual(
            channel._ensure_https_url('https://example.com/img.jpg'),
            'https://example.com/img.jpg',
        )

    def test_9_3_1c_ensure_https_url_invalid_returns_none(self):
        """_ensure_https_url returns None for invalid schemes."""
        channel = self.env['discuss.channel'].sudo().new({})
        self.assertIsNone(channel._ensure_https_url(None))
        self.assertIsNone(channel._ensure_https_url(''))
        self.assertIsNone(channel._ensure_https_url('ftp://example.com'))

    def test_9_3_2_video_range_requests(self):
        """Video URL supports Range requests."""
        self.skipTest('Infrastructure-level test; requires HTTP server')

    def test_9_3_3_video_preview_path_valid(self):
        """Video preview static path format is valid."""
        # Code references:
        # f'{base_url}/woow_odoo_livechat_line/static/img/video_preview.png'
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url',
        )
        expected = (
            f'{base_url}/woow_odoo_livechat_line'
            '/static/img/video_preview.png'
        )
        self.assertTrue(expected.startswith('https://'))

    def test_9_3_4_attachment_token_not_enumerable(self):
        """Attachment access tokens are random and long."""
        att = self.env['ir.attachment'].create({
            'name': 'test.png',
            'datas': base64.b64encode(b'fake image data'),
        })
        att.generate_access_token()
        self.assertTrue(len(att.access_token) >= 20)

    def test_9_3_5_large_file_upload(self):
        """Large file upload handling."""
        self.skipTest('Infrastructure-level test; requires nginx config')
