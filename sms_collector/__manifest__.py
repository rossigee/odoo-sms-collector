# Copyright 2025 Ross Golder (https://golder.org)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "SMS Collector",
    "version": "16.0.2.1.0",
    "author": "Ross Golder",
    "website": "https://golder.org/",
    "license": "AGPL-3",
    "category": "Tools",
    "summary": "An HTTP POST endpoint for mobile phones to upload SMS messages to.",
    "description": """
        Provides a simple HTTP POST endpoint for mobile phones to upload copies of their SMS messages to for further processing.
    """,
    "depends": [
        "base",
        "mail",
    ],
    "data": [
        "security/sms_collector_security.xml",
        "data/sms_filter_rule_data.xml",
        "views/res_config_settings_views.xml",
        "views/sms_message.xml",
        "views/sms_device.xml",
        "views/sms_filter_rule.xml",
        "views/sms_stats.xml",
    ],
    "installable": True,
}
