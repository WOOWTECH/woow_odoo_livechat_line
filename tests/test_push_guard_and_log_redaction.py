# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""LINE conversation fields are not writable by ordinary employees, and the
outbound attachment path does not write bearer URLs or file names to the log.
"""

import base64
import logging
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

FAKE_UID = 'Uvictim000000000000000000000001'


@tagged('post_install', '-at_install', 'line_ci')
class TestLineFieldGuard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['res.users'].create({
            'name': 'Plain Employee', 'login': 'plain.employee.line@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.manager = cls.env['res.users'].create({
            'name': 'Livechat Manager', 'login': 'lc.manager.line@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('im_livechat.im_livechat_group_manager').id])],
        })

    def test_employee_cannot_create_line_channel(self):
        with self.assertRaises(AccessError):
            self.env['discuss.channel'].with_user(self.employee).create(
                {'name': 'forged', 'line_user_id': FAKE_UID})

    def test_employee_cannot_write_line_user_id(self):
        channel = self.env['discuss.channel'].with_user(self.employee).create({'name': 'mine'})
        with self.assertRaises(AccessError):
            channel.write({'line_user_id': FAKE_UID})

    def test_employee_cannot_retarget_existing_line_channel(self):
        channel = self.env['discuss.channel'].sudo().create({'name': 'real', 'line_user_id': 'Ureal'})
        channel.with_user(self.manager).write({'name': 'renamed'})
        with self.assertRaises(AccessError):
            channel.with_user(self.employee).write({'line_user_id': FAKE_UID})
        self.assertEqual(channel.line_user_id, 'Ureal')

    def test_manager_and_sudo_can_set_fields(self):
        channel = self.env['discuss.channel'].with_user(self.manager).create(
            {'name': 'managed', 'line_user_id': 'Umanaged'})
        self.assertEqual(channel.line_user_id, 'Umanaged')
        channel.sudo().write({'line_display_name': 'x'})
        self.assertEqual(channel.line_display_name, 'x')

    def test_employee_message_does_not_push_to_forged_uid(self):
        channel = self.env['discuss.channel'].with_user(self.employee).create({'name': 'no push'})
        with patch.object(type(self.env['line.api.service']), '_push_message_raw') as push:
            try:
                channel.write({'line_user_id': FAKE_UID})
            except AccessError:
                pass
            channel.message_post(body='hello', message_type='comment')
        push.assert_not_called()


@tagged('post_install', '-at_install', 'line_ci')
class TestAttachmentLogRedaction(TransactionCase):

    def test_no_token_url_or_filename_in_info_log(self):
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://tenant.example.com')
        livechat = self.env['im_livechat.channel'].create({'name': 'log fixture'})
        livechat.sudo().write({'line_channel_id': '1234567890',
                               'line_channel_secret': 'secret-for-tests', 'line_enabled': True})
        channel = self.env['discuss.channel'].create({'name': 'log path'})
        channel.write({'line_user_id': 'Ulogtest', 'livechat_channel_id': livechat.id})
        attachment = self.env['ir.attachment'].create({
            'name': 'secret-customer-contract.pdf', 'mimetype': 'application/pdf',
            'datas': base64.b64encode(b'x'),
            'res_model': 'discuss.channel', 'res_id': channel.id,
        })
        message = self.env['mail.message'].with_context(from_line_webhook=True).create({
            'model': 'discuss.channel', 'res_id': channel.id, 'body': '<p>hi</p>',
            'message_type': 'comment',
        })
        message.write({'attachment_ids': [(4, attachment.id)]})
        line_cls = type(self.env['line.api.service'])
        records = []

        class _Collect(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        logger = logging.getLogger('odoo.addons.woow_odoo_livechat_line.models.discuss_channel')
        handler = _Collect(level=logging.INFO)
        old_level = logger.level
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        try:
            with patch.object(line_cls, 'get_access_token', return_value='tok'), \
                    patch.object(line_cls, '_push_message_raw', return_value=(True, 200, 'ok')):
                channel._notify_line_user(message)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)
        self.assertTrue(records, 'the outbound path should log something')
        text = '\n'.join(records)
        self.assertNotIn('access_token=', text)
        self.assertNotIn('secret-customer-contract', text)
        self.assertNotIn('/web/content/', text)
        self.assertNotIn(attachment.access_token or 'NOTOKEN', text)
