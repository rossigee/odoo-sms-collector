# -*- coding: utf-8 -*-

from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestSMSFilterRule(TransactionCase):
    def setUp(self):
        super(TestSMSFilterRule, self).setUp()

        # Create test user
        self.test_user = self.env["res.users"].create(
            {
                "name": "Test SMS User",
                "login": "test_sms_user",
                "email": "test@example.com",
            }
        )

        # Create test partner
        self.test_partner = self.env["res.partner"].create(
            {
                "name": "Test Bank",
                "mobile": "+1234567890",
            }
        )

        # Create test channel
        self.test_channel = self.env["mail.channel"].create(
            {
                "name": "Test OTP Channel",
                "channel_type": "channel",
            }
        )

        # Sample SMS message data
        self.sample_sms_data = {
            "idx": 12345,
            "thread_id": 1,
            "phone_user_id": self.test_user.id,
            "address": "+1234567890",
            "date": 1640995200000,
            "date_sent": 1640995000000,
            "body": "Your OTP code is 123456",
            "service_center": "+1234567891",
        }

    def test_filter_rule_creation(self):
        """Test basic filter rule creation"""
        rule = self.env["sms.filter.rule"].create(
            {
                "name": "Test OTP Rule",
                "match_type": "contains",
                "match_value": "OTP",
                "action_type": "channel",
                "channel_id": self.test_channel.id,
            }
        )

        self.assertTrue(rule.id)
        self.assertEqual(rule.name, "Test OTP Rule")
        self.assertEqual(rule.match_type, "contains")
        self.assertEqual(rule.action_type, "channel")

    def test_contains_matching(self):
        """Test contains text matching"""
        rule = self.env["sms.filter.rule"].create(
            {
                "name": "OTP Rule",
                "match_type": "contains",
                "match_value": "OTP",
                "action_type": "channel",
                "channel_id": self.test_channel.id,
            }
        )

        # Create SMS with OTP
        sms = self.env["sms.message"].create(self.sample_sms_data)

        # Should match
        self.assertTrue(rule._match_sms(sms))

        # Create SMS without OTP
        sms_data2 = self.sample_sms_data.copy()
        sms_data2["body"] = "Regular message"
        sms_data2["idx"] = 12346
        sms2 = self.env["sms.message"].create(sms_data2)

        # Should not match
        self.assertFalse(rule._match_sms(sms2))

    def test_case_sensitive_matching(self):
        """Test case sensitive/insensitive matching"""
        rule = self.env["sms.filter.rule"].create(
            {
                "name": "Case Sensitive Rule",
                "match_type": "contains",
                "match_value": "OTP",
                "case_sensitive": True,
                "action_type": "channel",
                "channel_id": self.test_channel.id,
            }
        )

        # Test with exact case
        sms_data1 = self.sample_sms_data.copy()
        sms_data1["body"] = "Your OTP is 123456"
        sms1 = self.env["sms.message"].create(sms_data1)
        self.assertTrue(rule._match_sms(sms1))

        # Test with different case
        sms_data2 = self.sample_sms_data.copy()
        sms_data2["body"] = "Your otp is 123456"
        sms_data2["idx"] = 12347
        sms2 = self.env["sms.message"].create(sms_data2)
        self.assertFalse(rule._match_sms(sms2))

        # Test case insensitive
        rule.case_sensitive = False
        self.assertTrue(rule._match_sms(sms2))

    def test_regex_matching(self):
        """Test regular expression matching"""
        rule = self.env["sms.filter.rule"].create(
            {
                "name": "Regex Rule",
                "match_type": "regex",
                "match_value": r"\b\d{6}\b",  # 6-digit number
                "action_type": "channel",
                "channel_id": self.test_channel.id,
            }
        )

        # Should match 6-digit code
        sms_data1 = self.sample_sms_data.copy()
        sms_data1["body"] = "Your code is 123456"
        sms1 = self.env["sms.message"].create(sms_data1)
        self.assertTrue(rule._match_sms(sms1))

        # Should not match 5-digit code
        sms_data2 = self.sample_sms_data.copy()
        sms_data2["body"] = "Your code is 12345"
        sms_data2["idx"] = 12347
        sms2 = self.env["sms.message"].create(sms_data2)
        self.assertFalse(rule._match_sms(sms2))

    def test_sender_matching(self):
        """Test sender phone number matching"""
        rule = self.env["sms.filter.rule"].create(
            {
                "name": "Sender Rule",
                "match_type": "sender",
                "match_value": "+1234567890",
                "action_type": "channel",
                "channel_id": self.test_channel.id,
            }
        )

        # Should match exact sender
        sms = self.env["sms.message"].create(self.sample_sms_data)
        self.assertTrue(rule._match_sms(sms))

        # Should not match different sender
        sms_data2 = self.sample_sms_data.copy()
        sms_data2["address"] = "+9876543210"
        sms_data2["idx"] = 12347
        sms2 = self.env["sms.message"].create(sms_data2)
        self.assertFalse(rule._match_sms(sms2))

    def test_partner_matching(self):
        """Test partner association matching"""
        rule = self.env["sms.filter.rule"].create(
            {
                "name": "Partner Rule",
                "match_type": "partner",
                "action_type": "partner_chatter",
            }
        )

        # SMS with partner should match
        sms = self.env["sms.message"].create(self.sample_sms_data)
        sms.partner_id = self.test_partner
        self.assertTrue(rule._match_sms(sms))

        # SMS without partner should not match
        sms_data2 = self.sample_sms_data.copy()
        sms_data2["address"] = "+9999999999"  # Different number
        sms_data2["idx"] = 12347
        sms2 = self.env["sms.message"].create(sms_data2)
        self.assertFalse(rule._match_sms(sms2))

    @patch("odoo.addons.sms_collector.models.sms_filter_rule.SMSFilterRule._post_to_channel")
    def test_channel_action(self, mock_post):
        """Test posting to channel action"""
        # Create SMS before rule so process_sms_message doesn't auto-fire during create
        sms = self.env["sms.message"].create(self.sample_sms_data)

        rule = self.env["sms.filter.rule"].create(
            {
                "name": "Channel Rule",
                "match_type": "contains",
                "match_value": "OTP",
                "action_type": "channel",
                "channel_id": self.test_channel.id,
            }
        )

        rule._execute_action(sms)

        mock_post.assert_called_once_with(sms)

    def test_auto_channel_creation(self):
        """Test automatic channel creation"""
        # Create SMS first so process_sms_message doesn't fire the rule during create
        sms = self.env["sms.message"].create(self.sample_sms_data)

        rule = self.env["sms.filter.rule"].create(
            {
                "name": "Auto Channel Rule",
                "match_type": "contains",
                "match_value": "OTP",
                "action_type": "channel",
                "auto_create_channel": True,
                "channel_name": "Auto Created OTP Channel",
            }
        )

        # Channel shouldn't exist yet
        channel = self.env["mail.channel"].search(
            [("name", "=", "Auto Created OTP Channel")]
        )
        self.assertEqual(len(channel), 0)

        # Execute action should create channel
        rule._execute_action(sms)

        # Channel should now exist
        channel = self.env["mail.channel"].search(
            [("name", "=", "Auto Created OTP Channel")]
        )
        self.assertEqual(len(channel), 1)
        self.assertEqual(rule.channel_id, channel)

    def test_transaction_parsing(self):
        """Test transaction parsing posts to channel when channel_id is set"""
        # Create SMS before rule to avoid auto-firing during create
        sms_data = self.sample_sms_data.copy()
        sms_data["body"] = "Transfer of 1,250.00 USD received from John Smith"
        sms_data["idx"] = 12347
        sms = self.env["sms.message"].create(sms_data)

        rule = self.env["sms.filter.rule"].create(
            {
                "name": "Transaction Rule",
                "match_type": "contains",
                "match_value": "transfer",
                "action_type": "create_transaction",
                "parse_transaction": True,
                "channel_id": self.test_channel.id,
                "transaction_regex": (
                    r"(?P<amount>[\d,]+\.?\d*)\s*(?P<currency>[A-Z]{3})"
                    r".*?from\s*(?P<partner_name>[\w\s]+)"
                ),
            }
        )

        msgs_before = len(self.test_channel.message_ids)
        rule._execute_action(sms)
        # A transaction notification should have been posted to the channel
        self.assertGreater(len(self.test_channel.message_ids), msgs_before)

    def test_rule_sequence_processing(self):
        """Test that stop_processing on the first matching rule prevents further rule execution"""
        # Two separate channels so we can count posts per rule
        channel1 = self.env["mail.channel"].create(
            {"name": "Sequence Channel 1", "channel_type": "channel"}
        )
        channel2 = self.env["mail.channel"].create(
            {"name": "Sequence Channel 2", "channel_type": "channel"}
        )

        self.env["sms.filter.rule"].create(
            {
                "name": "First Rule",
                "sequence": 10,
                "match_type": "contains",
                "match_value": "test",
                "action_type": "channel",
                "channel_id": channel1.id,
                "stop_processing": True,
            }
        )

        self.env["sms.filter.rule"].create(
            {
                "name": "Second Rule",
                "sequence": 20,
                "match_type": "contains",
                "match_value": "test",
                "action_type": "channel",
                "channel_id": channel2.id,
            }
        )

        sms_data = self.sample_sms_data.copy()
        sms_data["body"] = "test message"
        sms_data["idx"] = 12347
        sms = self.env["sms.message"].create(sms_data)

        msgs_before_1 = len(channel1.message_ids)
        msgs_before_2 = len(channel2.message_ids)

        self.env["sms.filter.rule"].process_sms_message(sms)

        # First rule should have posted; second rule should not (stopped)
        self.assertEqual(len(channel1.message_ids), msgs_before_1 + 1)
        self.assertEqual(len(channel2.message_ids), msgs_before_2)

    def test_stop_processing_flag(self):
        """Test stop_processing flag prevents further rule execution"""
        channel1 = self.env["mail.channel"].create(
            {"name": "Stop Channel 1", "channel_type": "channel"}
        )
        channel2 = self.env["mail.channel"].create(
            {"name": "Stop Channel 2", "channel_type": "channel"}
        )

        self.env["sms.filter.rule"].create(
            {
                "name": "Stop Rule",
                "sequence": 10,
                "match_type": "contains",
                "match_value": "OTP",
                "action_type": "channel",
                "channel_id": channel1.id,
                "stop_processing": True,
            }
        )

        self.env["sms.filter.rule"].create(
            {
                "name": "Continue Rule",
                "sequence": 20,
                "match_type": "contains",
                "match_value": "OTP",
                "action_type": "channel",
                "channel_id": channel2.id,
                "stop_processing": False,
            }
        )

        sms = self.env["sms.message"].create(self.sample_sms_data)

        msgs_before_1 = len(channel1.message_ids)
        msgs_before_2 = len(channel2.message_ids)

        self.env["sms.filter.rule"].process_sms_message(sms)

        # Only first rule should have posted
        self.assertEqual(len(channel1.message_ids), msgs_before_1 + 1)
        self.assertEqual(len(channel2.message_ids), msgs_before_2)
