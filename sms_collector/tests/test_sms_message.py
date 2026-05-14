# -*- coding: utf-8 -*-

import hashlib
import json
from datetime import datetime, timezone

from odoo.tests.common import TransactionCase


class TestSMSMessage(TransactionCase):
    def setUp(self):
        super(TestSMSMessage, self).setUp()

        # Create a test user for phone_user_id
        self.test_user = self.env["res.users"].create(
            {
                "name": "Test SMS User",
                "login": "test_sms_user",
                "email": "test@example.com",
            }
        )

        # Sample SMS data
        self.sample_sms_data = {
            "idx": 12345,
            "thread_id": 1,
            "phone_user_id": self.test_user.id,
            "address": "+1234567890",
            "date": 1640995200000,  # 2022-01-01 00:00:00 UTC in milliseconds
            "date_sent": 1640995000000,  # 2022-01-01 00:00:00 UTC in milliseconds
            "body": "Test SMS message",
            "service_center": "+1234567891",
        }

    def test_sms_message_creation(self):
        """Test basic SMS message creation"""
        sms = self.env["sms.message"].create(self.sample_sms_data)

        self.assertTrue(sms.id)
        self.assertEqual(sms.address, "+1234567890")
        self.assertEqual(sms.body, "Test SMS message")
        self.assertEqual(sms.phone_user_id, self.test_user)
        self.assertTrue(sms.message_hash)
        self.assertEqual(len(sms.message_hash), 64)  # SHA256 is 64 chars hex

    def test_sms_message_hash_calculation(self):
        """Test that message hash is calculated correctly"""
        sms = self.env["sms.message"].create(self.sample_sms_data)

        # Calculate expected hash manually
        expected_hash_data = {
            "address": sms.address,
            "date_sent": str(sms.date_sent),
            "body": sms.body,
            "thread_id": sms.thread_id,
        }
        expected_hash_string = json.dumps(expected_hash_data, sort_keys=True)
        expected_hash = hashlib.sha256(expected_hash_string.encode("utf-8")).hexdigest()

        self.assertEqual(sms.message_hash, expected_hash)

    def test_duplicate_prevention(self):
        """Test that duplicate messages are prevented"""
        # Create first message
        sms1 = self.env["sms.message"].create(self.sample_sms_data)
        original_id = sms1.id

        # Try to create the same message again
        sms2 = self.env["sms.message"].create(self.sample_sms_data)

        # Should return the existing record
        self.assertEqual(sms1.id, sms2.id)
        self.assertEqual(sms2.id, original_id)

        # Verify only one record exists with this hash
        all_with_hash = self.env["sms.message"].search(
            [("message_hash", "=", sms1.message_hash)]
        )
        self.assertEqual(len(all_with_hash), 1)

    def test_partner_association(self):
        """Test automatic partner association based on phone number"""
        # Create a partner with matching phone
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "mobile": "+1234567890",
            }
        )

        # Create SMS from that number
        sms = self.env["sms.message"].create(self.sample_sms_data)

        # Should be automatically associated
        self.assertEqual(sms.partner_id, partner)

    def test_partner_association_phone_variations(self):
        """Test partner association matches when SMS address has dashes (stripped for comparison)"""
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "mobile": "+1234567890",
            }
        )

        # Dashes are stripped before searching, so "1234567890" matches "+1234567890" via ilike
        sms_data = self.sample_sms_data.copy()
        sms_data["address"] = "+1-234-567-890"
        sms_data["idx"] = 12346

        sms = self.env["sms.message"].create(sms_data)

        self.assertEqual(sms.partner_id, partner)

    def test_date_conversion(self):
        """Test epoch millisecond to datetime conversion"""
        sms = self.env["sms.message"].create(self.sample_sms_data)

        # Check that epoch conversion worked correctly
        expected_date = datetime.fromtimestamp(
            self.sample_sms_data["date"] / 1000, tz=timezone.utc
        ).replace(tzinfo=None)

        self.assertEqual(sms.date_received, expected_date)

    def test_null_character_removal(self):
        """Test that null characters are removed from message body"""
        sms_data = self.sample_sms_data.copy()
        sms_data["body"] = "Test\x00message\x00with\x00nulls"
        sms_data["idx"] = 12347

        sms = self.env["sms.message"].create(sms_data)

        # Null characters should be removed
        self.assertEqual(sms.body, "Testmessagewithnulls")

    def test_different_messages_different_hashes(self):
        """Test that different messages produce different hashes"""
        sms1 = self.env["sms.message"].create(self.sample_sms_data)

        # Create slightly different message
        sms_data2 = self.sample_sms_data.copy()
        sms_data2["body"] = "Different message body"
        sms_data2["idx"] = 12348

        sms2 = self.env["sms.message"].create(sms_data2)

        self.assertNotEqual(sms1.message_hash, sms2.message_hash)
        self.assertNotEqual(sms1.id, sms2.id)

    def test_same_content_different_sender(self):
        """Test messages with same content but different sender get different hashes"""
        sms1 = self.env["sms.message"].create(self.sample_sms_data)

        sms_data2 = self.sample_sms_data.copy()
        sms_data2["address"] = "+9876543210"  # Different sender
        sms_data2["idx"] = 12349

        sms2 = self.env["sms.message"].create(sms_data2)

        self.assertNotEqual(sms1.message_hash, sms2.message_hash)
        self.assertEqual(sms1.body, sms2.body)  # Same content
        self.assertNotEqual(sms1.address, sms2.address)  # Different sender

    def test_device_id_stored(self):
        """Test that device_id is stored when provided"""
        device = self.env["sms.device"].create(
            {"name": "Test Phone", "user_id": self.test_user.id}
        )
        sms_data = dict(self.sample_sms_data, device_id=device.id)
        sms = self.env["sms.message"].create(sms_data)

        self.assertEqual(sms.device_id, device)

    def test_device_id_optional(self):
        """Test that device_id is not required (backward compatibility)"""
        sms = self.env["sms.message"].create(self.sample_sms_data)
        self.assertFalse(sms.device_id)

    def test_requeue_from_minio_not_configured(self):
        """requeue_from_minio returns an error dict when MinIO is not configured"""
        result = self.env["sms.message"].requeue_from_minio()
        self.assertIn("error", result)

    def test_requeue_from_minio_creates_and_skips(self):
        """requeue_from_minio creates new messages and skips duplicates"""
        from unittest.mock import MagicMock, patch

        existing_sms = self.env["sms.message"].create(self.sample_sms_data)

        # Build a second payload (different body/idx = new message)
        new_payload = dict(
            self.sample_sms_data,
            idx=99999,
            body="A brand new message",
        )

        # Two archived objects: one duplicate, one new
        archived = [self.sample_sms_data, new_payload]

        def fake_list_objects(bucket, recursive=False):
            objs = []
            for i, _ in enumerate(archived):
                o = MagicMock()
                o.object_name = f"user/device/{i}.json"
                objs.append(o)
            return objs

        def fake_get_object(bucket, key):
            idx = int(key.split("/")[2].split(".")[0])
            data = archived[idx]
            resp = MagicMock()
            resp.read.return_value = __import__("json").dumps(data).encode()
            resp.close = MagicMock()
            resp.release_conn = MagicMock()
            return resp

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_client.list_objects.side_effect = fake_list_objects
        mock_client.get_object.side_effect = fake_get_object

        with patch.object(
            self.env["sms.message"].__class__,
            "_get_minio_client",
            return_value=mock_client,
        ):
            # Also need bucket_name param
            self.env["ir.config_parameter"].sudo().set_param(
                "sms_collector.bucket_name", "test-bucket"
            )
            result = self.env["sms.message"].requeue_from_minio()

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["errors"], 0)
