# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Attack-surface tests: perform the attack, assert it fails.

Deliberately different from tests/test_security_fixes.py. That file asserts the
*fix is present* (the field carries groups=). This file asserts the *hole is
closed* (a Portal user genuinely cannot obtain the value).

The distinction is not pedantic. Field-level `groups=`, model ACLs and record
rules are three separate mechanisms, and a `search_read` that silently omits a
restricted field looks identical to one that was never restricted. Reading
`fields_get()` proves the registry knows about the restriction; it proves
nothing about what an RPC hands back.

The regression being guarded against is concrete: someone removes `groups=`
later so the settings form can display the field again, and nothing catches it.
That is exactly how this hole came to exist.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

SECRET = 'SECRET-MUST-NOT-LEAK-4f2b'
CHANNEL_ID = 'CHANNELID-MUST-NOT-LEAK-9a1c'


@tagged('post_install', '-at_install', 'line_ci')
class TestCredentialExposure(TransactionCase):
    """B-1: the LINE credentials sit on im_livechat.channel, a model Portal and
    Public users can read. LIFF hands a Portal account to every follower who
    taps a link, so "an authenticated user" means "any follower"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # line_enabled stays False: _check_line_config would otherwise demand
        # both credentials at create time, which is not what is under test.
        cls.channel = cls.env['im_livechat.channel'].create({
            'name': 'attack surface fixture',
        })
        cls.channel.sudo().write({
            'line_channel_id': CHANNEL_ID,
            'line_channel_secret': SECRET,
        })
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.portal = Users.create({
            'name': 'portal attacker',
            'login': 'attacker_portal_b1',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def _leaked(self, rows):
        for row in rows:
            for value in row.values():
                if value in (SECRET, CHANNEL_ID):
                    return True
        return False

    def test_portal_asking_for_every_field_never_receives_the_secret(self):
        """The realistic attack: request everything and see what comes back.

        An attacker does not politely name only the restricted field — they
        call search_read with no field list and read whatever arrives.
        """
        try:
            rows = self.env['im_livechat.channel'].with_user(
                self.portal).search_read([], [])
        except AccessError:
            return  # record unreachable entirely — also an acceptable outcome
        self.assertFalse(
            self._leaked(rows),
            'a Portal user received the LINE channel credentials from a '
            'search_read of all fields')

    def test_portal_naming_the_secret_explicitly_is_refused(self):
        with self.assertRaises(AccessError):
            self.channel.with_user(self.portal).read(['line_channel_secret'])

    def test_portal_cannot_filter_the_secret_out_of_the_database(self):
        """A blind oracle: even without reading the value, being able to
        *search* on it leaks it one character at a time."""
        try:
            hits = self.env['im_livechat.channel'].with_user(self.portal).search(
                [('line_channel_secret', '=', SECRET)])
        except AccessError:
            return
        self.assertFalse(
            hits, 'a Portal user could confirm the secret value via search()')

    def test_public_user_never_receives_the_secret(self):
        public = self.env.ref('base.public_user', raise_if_not_found=False)
        if not public:
            self.skipTest('base.public_user not present')
        try:
            rows = self.env['im_livechat.channel'].with_user(
                public).search_read([], [])
        except AccessError:
            return
        self.assertFalse(
            self._leaked(rows), 'the Public user received the LINE credentials')

    def test_manager_can_still_read_it(self):
        """Guard the other direction. Over-restricting breaks the admin UI, and
        the fix is only correct if the people who configure LINE can still see
        what they are configuring."""
        manager = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'livechat manager',
                'login': 'legit_manager_b1',
                'groups_id': [(6, 0, [
                    self.env.ref('base.group_user').id,
                    self.env.ref('im_livechat.im_livechat_group_manager').id,
                ])],
            })
        row = self.channel.with_user(manager).read(
            ['line_channel_id', 'line_channel_secret'])[0]
        self.assertEqual(row['line_channel_secret'], SECRET)
        self.assertEqual(row['line_channel_id'], CHANNEL_ID)

    def test_operator_reply_path_still_reads_the_credentials(self):
        """The restriction must not lock out the people who use the feature.

        _notify_line_user reads the credentials while running as a Live Chat /
        User, so it needs sudo(). Without it every operator reply silently
        fails to reach the customer — which is worse than the original bug,
        because it looks like nothing is wrong.
        """
        operator = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'livechat operator',
                'login': 'legit_operator_b1',
                'groups_id': [(6, 0, [
                    self.env.ref('base.group_user').id,
                    self.env.ref('im_livechat.im_livechat_group_user').id,
                ])],
            })
        channel = self.env['discuss.channel'].create({'name': 'operator path'})
        channel.write({
            'line_user_id': 'Uattacksurfacetest',
            'livechat_channel_id': self.channel.id,
        })
        message = self.env['mail.message'].create({
            'model': 'discuss.channel', 'res_id': channel.id,
            'body': '<p>x</p>', 'message_type': 'comment',
        })
        # line_enabled is False on the fixture, so this returns before any HTTP
        # call. What is asserted is that reading the credentials on the way
        # there does not raise for a non-manager.
        channel.with_user(operator)._notify_line_user(message)
