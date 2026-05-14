# -*- coding: utf-8 -*-

import logging
import re

from markupsafe import Markup, escape

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SMSFilterRule(models.Model):
    _name = "sms.filter.rule"
    _description = "SMS Filter Rule"
    _order = "sequence, id"

    name = fields.Char(string="Rule Name", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    match_type = fields.Selection(
        [
            ("contains", "Contains Text"),
            ("regex", "Regular Expression"),
            ("sender", "From Specific Sender"),
            ("partner", "Has Associated Partner"),
        ],
        string="Match Type",
        required=True,
        default="contains",
    )

    match_value = fields.Char(
        string="Match Value", help="Text to search for, regex pattern, or sender number"
    )
    case_sensitive = fields.Boolean(string="Case Sensitive", default=False)

    action_type = fields.Selection(
        [
            ("channel", "Post to Channel"),
            ("partner_chatter", "Add to Partner Chatter"),
            ("create_transaction", "Create Transaction"),
            ("multi", "Multiple Actions"),
        ],
        string="Action Type",
        required=True,
    )

    channel_id = fields.Many2one("mail.channel", string="Target Channel")
    auto_create_channel = fields.Boolean(string="Auto-create Channel", default=True)
    channel_name = fields.Char(string="Channel Name (if auto-create)")

    parse_transaction = fields.Boolean(string="Parse as Transaction")
    transaction_regex = fields.Text(
        string="Transaction Parser Regex",
        help="Regex with named groups: amount, currency, reference, partner_name",
        default=r"(?P<amount>[\d,]+\.?\d*)\s*(?P<currency>[A-Z]{3}).*?(?:from|to)\s*(?P<partner_name>[\w\s]+)",
    )

    stop_processing = fields.Boolean(
        string="Stop Processing Further Rules", default=False
    )
    partner_search_field = fields.Selection(
        [
            ("name", "Name"),
            ("phone", "Phone"),
            ("mobile", "Mobile"),
            ("email", "Email"),
            ("ref", "Reference"),
        ],
        string="Partner Search Field",
        default="mobile",
    )

    @api.model
    def process_sms_message(self, sms_record):
        rules = self.search([("active", "=", True)], order="sequence")

        for rule in rules:
            if rule._match_sms(sms_record):
                rule._execute_action(sms_record)
                if rule.stop_processing:
                    break

    def _match_sms(self, sms_record):
        if self.match_type == "contains":
            if not self.match_value:
                return False
            body = sms_record.body or ""
            text = body if self.case_sensitive else body.lower()
            search_text = (
                self.match_value if self.case_sensitive else self.match_value.lower()
            )
            return search_text in text

        elif self.match_type == "regex":
            if not self.match_value:
                return False
            flags = 0 if self.case_sensitive else re.IGNORECASE
            try:
                return bool(re.search(self.match_value, sms_record.body or "", flags))
            except re.error:
                _logger.error(f"Invalid regex in rule {self.name}: {self.match_value}")
                return False

        elif self.match_type == "sender":
            return bool(self.match_value) and self.match_value in (sms_record.address or "")

        elif self.match_type == "partner":
            return bool(sms_record.partner_id)

        return False

    def _execute_action(self, sms_record):
        if self.action_type == "channel":
            self._post_to_channel(sms_record)
        elif self.action_type == "partner_chatter":
            self._add_to_partner_chatter(sms_record)
        elif self.action_type == "create_transaction":
            self._create_transaction(sms_record)
        elif self.action_type == "multi":
            if self.channel_id or self.channel_name:
                self._post_to_channel(sms_record)
            if sms_record.partner_id:
                self._add_to_partner_chatter(sms_record)
            if self.parse_transaction:
                self._create_transaction(sms_record)

    def _post_to_channel(self, sms_record):
        channel = self.channel_id

        if not channel and self.auto_create_channel and self.channel_name:
            channel = (
                self.env["mail.channel"]
                .sudo()
                .search([("name", "=", self.channel_name)], limit=1)
            )

            if not channel:
                channel = (
                    self.env["mail.channel"]
                    .sudo()
                    .create(
                        {
                            "name": self.channel_name,
                            "channel_type": "channel",
                        }
                    )
                )
                self.channel_id = channel

        if channel:
            body = Markup(
                "<div>"
                "<strong>SMS from {address}</strong><br/>"
                "<em>Received: {date_received}</em><br/>"
                "<br/>"
                "{body}"
                "</div>"
            ).format(
                address=escape(sms_record.address or ""),
                date_received=escape(str(sms_record.date_received)),
                body=escape(sms_record.body or ""),
            )

            channel.message_post(
                body=body,
                message_type="comment",
                author_id=sms_record.phone_user_id.partner_id.id
                if sms_record.phone_user_id
                else False,
            )

    def _add_to_partner_chatter(self, sms_record):
        partner = sms_record.partner_id

        if not partner and self.partner_search_field:
            search_value = sms_record.address
            if search_value:
                search_value = search_value.replace(" ", "").replace("-", "")
                domain = [(self.partner_search_field, "ilike", search_value)]
                partner = self.env["res.partner"].search(domain, limit=1)

                if partner:
                    sms_record.partner_id = partner

        if partner:
            direction = "from" if sms_record.phone_user_id else "to"
            body = Markup(
                "<div>"
                "<strong>SMS {direction} {address}</strong><br/>"
                "<em>{date_received}</em><br/>"
                "<br/>"
                "{body}"
                "</div>"
            ).format(
                direction=direction,
                address=escape(sms_record.address or ""),
                date_received=escape(str(sms_record.date_received)),
                body=escape(sms_record.body or ""),
            )

            partner.message_post(
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def _create_transaction(self, sms_record):
        if not self.transaction_regex:
            return

        try:
            match = re.search(self.transaction_regex, sms_record.body or "", re.IGNORECASE)
            if match:
                data = match.groupdict()

                amount_str = data.get("amount", "0").replace(",", "")
                try:
                    amount = float(amount_str)
                except ValueError:
                    _logger.error(f"Could not parse amount: {amount_str}")
                    return

                partner_name = data.get("partner_name", "").strip()
                partner = None
                if partner_name:
                    partner = self.env["res.partner"].search(
                        [("name", "ilike", partner_name)], limit=1
                    )

                    if not partner:
                        _logger.warning(
                            f"Transaction SMS from {sms_record.address} references unknown partner "
                            f"'{partner_name}' — skipping partner creation"
                        )

                _logger.info(
                    f"Parsed transaction: {amount} {data.get('currency', 'USD')} - {partner_name}"
                )

                if self.channel_id:
                    body = Markup(
                        "<div>"
                        "<strong>Transaction Detected</strong><br/>"
                        "Amount: {amount} {currency}<br/>"
                        "Partner: {partner_name}<br/>"
                        "Reference: {reference}<br/>"
                        "<br/>"
                        "Original SMS: {body}"
                        "</div>"
                    ).format(
                        amount=escape(str(amount)),
                        currency=escape(data.get("currency", "USD")),
                        partner_name=escape(partner_name),
                        reference=escape(data.get("reference", "N/A")),
                        body=escape(sms_record.body or ""),
                    )

                    self.channel_id.message_post(
                        body=body,
                        message_type="comment",
                    )

        except Exception as e:
            _logger.error(f"Error parsing transaction from SMS: {e}")
