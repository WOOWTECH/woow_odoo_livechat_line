{
    'name': 'LiveChat LINE Integration',
    'version': '18.0.1.0.0',
    'category': 'Website/Live Chat',
    'summary': 'Integrate LINE Messaging API with Odoo LiveChat',
    'description': """
        This module integrates LINE Messaging API with Odoo LiveChat,
        allowing customer service agents to handle LINE messages
        through the standard Odoo Discuss interface.

        Features:
        - LINE channel configuration in LiveChat settings
        - Automatic conversation creation from LINE messages
        - Support for text, image, video, audio, file, sticker, and location messages
        - Guest to Partner linking capability
    """,
    'author': 'WoowTech',
    'website': 'https://woowtech.com',
    'license': 'LGPL-3',
    'depends': [
        'im_livechat',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/line_guest_link_partner_wizard_views.xml',
        'views/im_livechat_channel_views.xml',
    ],
    'assets': {},
    'installable': True,
    'application': False,
    'auto_install': False,
}
