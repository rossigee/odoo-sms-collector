# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SMSDevice(models.Model):
    _name = "sms.device"
    _description = "SMS Device"
    _order = "last_seen desc, id"

    name = fields.Char(string="Device Name", required=True)
    user_id = fields.Many2one("res.users", string="Owner", required=True, ondelete="cascade")
    platform = fields.Selection(
        [("android", "Android"), ("ios", "iOS"), ("other", "Other")],
        string="Platform",
        default="android",
    )
    last_seen = fields.Datetime(string="Last Seen", readonly=True)
    message_count = fields.Integer(
        string="Messages", compute="_compute_message_count", store=False
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "unique_name_per_user",
            "unique(user_id, name)",
            "Each device name must be unique per user",
        )
    ]

    @api.depends("user_id")
    def _compute_message_count(self):
        for device in self:
            device.message_count = self.env["sms.message"].search_count(
                [("device_id", "=", device.id)]
            )

    def action_view_messages(self):
        return {
            "type": "ir.actions.act_window",
            "name": f"Messages from {self.name}",
            "res_model": "sms.message",
            "view_mode": "tree,form",
            "domain": [("device_id", "=", self.id)],
            "context": {"default_device_id": self.id},
        }
