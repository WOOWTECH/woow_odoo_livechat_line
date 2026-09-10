# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Outbound attachment conversion: what an operator's file actually becomes.

_notify_line_user dispatches on mimetype into four different LINE message
shapes, and every branch builds its own URL. None of that was covered, and it
is not the kind of code that fails loudly — a wrong URL or a malformed message
is rejected by LINE's servers, logged, and never seen by the operator, who has
already been shown their message as sent.

These tests mock only the two network boundaries (token fetch and the HTTP
push) and let the real dispatch run, so the assertions are about the message
objects that would genuinely go to LINE.
"""

import base64
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

HTTPS_BASE = 'https://tenant.example.com'


@tagged('post_install', '-at_install', 'line_ci')
class TestOutboundAttachmentConversion(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('web.base.url', HTTPS_BASE)
        cls.livechat = cls.env['im_livechat.channel'].create({'name': 'attachment fixture'})
        cls.livechat.sudo().write({
            'line_channel_id': '1234567890',
            'line_channel_secret': 'secret-for-tests',
            'line_enabled': True,
        })
        cls.channel = cls.env['discuss.channel'].create({'name': 'attachment path'})
        cls.channel.write({
            'line_user_id': 'Uattachmenttest',
            'livechat_channel_id': cls.livechat.id,
        })

    def _convert(self, mimetype, filename, body='<p>hi</p>'):
        """Run the real dispatch for one attachment, return the LINE messages."""
        message = self.env['mail.message'].create({
            'model': 'discuss.channel', 'res_id': self.channel.id,
            'body': body, 'message_type': 'comment',
        })
        attachment = self.env['ir.attachment'].create({
            'name': filename, 'mimetype': mimetype,
            'datas': base64.b64encode(b'not-a-real-media-file'),
            'res_model': 'mail.message', 'res_id': message.id,
        })
        # attachment_ids is a many2many; res_model/res_id alone does not link
        # the attachment to the message, it only records what it belongs to.
        message.write({'attachment_ids': [(4, attachment.id)]})

        api = type(self.env['line.api.service'])
        captured = []

        def fake_push(self_api, token, uid, messages):
            captured.extend(messages)
            return True, 200, 'ok'

        with patch.object(api, 'get_access_token', return_value='tok'), \
             patch.object(api, '_push_message_raw', fake_push):
            self.channel._notify_line_user(message)
        return captured

    def _of_type(self, messages, kind):
        found = [m for m in messages if m.get('type') == kind]
        self.assertTrue(found, f'no {kind!r} message was produced: {messages}')
        return found[0]

    # ---- per-mimetype dispatch -------------------------------------------

    def test_image_becomes_an_image_message_over_https(self):
        msg = self._of_type(self._convert('image/png', 'shot.png'), 'image')
        for key in ('originalContentUrl', 'previewImageUrl'):
            url = msg[key]
            self.assertTrue(url.startswith('https://'),
                            f'{key} must be https — LINE refuses to fetch plain http: {url}')
            self.assertIn('access_token=', url,
                          f'{key} has no access token, so LINE fetches it anonymously '
                          f'and gets a login page instead of the image')

    def test_video_carries_a_preview_that_exists_in_this_module(self):
        msg = self._of_type(self._convert('video/mp4', 'clip.mp4'), 'video')
        self.assertTrue(msg['originalContentUrl'].startswith('https://'))
        preview = msg['previewImageUrl']
        self.assertTrue(preview.startswith('https://'))
        # The preview points at a static asset shipped by this module. If that
        # file is ever renamed or dropped, LINE gets a 404 for the thumbnail
        # and the video renders as a broken tile — with nothing in any log.
        if 'static/img/' in preview:
            import os
            here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            asset = preview.split('/woow_odoo_livechat_line/', 1)[1].split('?')[0]
            self.assertTrue(
                os.path.exists(os.path.join(here, asset)),
                f'video preview points at {asset}, which is not in this module')

    def test_audio_duration_is_a_fixed_guess_not_the_real_length(self):
        """Characterisation test for a known limitation, not an endorsement.

        LINE requires `duration` on an audio message and the code has no way to
        measure it, so it always sends 60000 ms. A 5-second voice note is shown
        to the customer as a 60-second track that stops a twelfth of the way
        in. Reading the real duration needs an audio library (mutagen/ffprobe)
        that this module does not depend on today, so the value is pinned here
        to keep the behaviour visible rather than surprising.
        """
        msg = self._of_type(self._convert('audio/mpeg', 'voice.mp3'), 'audio')
        self.assertEqual(
            msg['duration'], 60000,
            'the hardcoded duration changed — if this is now measured from the '
            'file, delete this test and assert the real value instead')

    def test_other_files_become_a_flex_card_carrying_the_filename(self):
        messages = self._convert('application/pdf', 'quotation.pdf')
        msg = self._of_type(messages, 'flex')
        self.assertIn('quotation.pdf', str(msg),
                      'the file card does not name the file, so the customer '
                      'sees an unlabelled bubble')

    def test_the_operator_text_is_sent_alongside_the_attachment(self):
        messages = self._convert('image/png', 'shot.png', body='<p>看一下這張</p>')
        text = self._of_type(messages, 'text')
        self.assertIn('看一下這張', text['text'])

    # ---- https enforcement ----------------------------------------------

    def test_ensure_https_url_upgrades_http_and_rejects_the_rest(self):
        ch = self.channel
        self.assertEqual(ch._ensure_https_url('https://x/y'), 'https://x/y')
        self.assertEqual(ch._ensure_https_url('http://x/y'), 'https://x/y')
        for bad in ('', None, 'ftp://x/y', '/relative/path'):
            self.assertIsNone(
                ch._ensure_https_url(bad),
                f'{bad!r} should be refused — LINE only fetches https, and a '
                f'silent pass-through here produces a message it drops')

    def test_plain_http_base_url_degrades_to_text_instead_of_a_dead_media_message(self):
        """A tenant whose web.base.url is http would otherwise emit media
        messages LINE cannot fetch. The fallback should send a usable text
        line rather than a broken image bubble."""
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', 'ftp://tenant.example.com')
        try:
            messages = self._convert('image/png', 'shot.png')
            self.assertFalse([m for m in messages if m.get('type') == 'image'],
                             'an unfetchable image message was still emitted')
            self.assertTrue([m for m in messages if m.get('type') == 'text'],
                            'no text fallback was produced')
        finally:
            self.env['ir.config_parameter'].sudo().set_param('web.base.url', HTTPS_BASE)
