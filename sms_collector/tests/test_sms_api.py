# -*- coding: utf-8 -*-

import json
from unittest.mock import patch

from odoo.tests.common import HttpCase


class TestSMSAPI(HttpCase):
    def setUp(self):
        super(TestSMSAPI, self).setUp()

        # Create test user with API key
        self.test_user = self.env["res.users"].create(
            {
                "name": "Test API User",
                "login": "test_api_user",
                "email": "test_api@example.com",
            }
        )

        # Create API key for testing
        self.api_key = (
            self.env["res.users.apikeys"]
            .sudo()
            .create(
                {
                    "user_id": self.test_user.id,
                    "name": "Test SMS API Key",
                    "key": "test_api_key_12345",
                    "scope": "rpc",
                }
            )
        )

        # Sample SMS payload
        self.sample_payload = {
            "_id": 12345,
            "thread_id": 1,
            "address": "+1234567890",
            "date": 1640995200000,
            "date_sent": 1640995000000,
            "body": "Test SMS message",
            "service_center": "+1234567891",
        }

    def test_api_endpoint_exists(self):
        """Test that the SMS upload endpoint exists"""
        response = self.url_open("/sms/upload", data=json.dumps({}))
        # Should not return 404
        self.assertNotEqual(response.status_code, 404)

    def test_missing_authorization_header(self):
        """Test API returns 401 when Authorization header is missing"""
        response = self.url_open(
            "/sms/upload",
            data=json.dumps(self.sample_payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertIn("No Authorization header", response_data["error"])

    def test_invalid_authorization_format(self):
        """Test API returns 401 for invalid Authorization format"""
        response = self.url_open(
            "/sms/upload",
            data=json.dumps(self.sample_payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": "InvalidFormat test_key",
            },
        )

        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertIn("Invalid Authorization format", response_data["error"])

    def test_invalid_api_key(self):
        """Test API returns 401 for invalid API key"""
        response = self.url_open(
            "/sms/upload",
            data=json.dumps(self.sample_payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer invalid_key_123",
            },
        )

        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertIn("Invalid API key", response_data["error"])

    @patch("sms_collector.models.sms_message.SMSMessage._store_message_as_object")
    def test_successful_sms_upload(self, mock_store):
        """Test successful SMS upload with valid API key"""
        # Mock MinIO to avoid actual storage during tests
        mock_store.return_value = None

        response = self.url_open(
            "/sms/upload",
            data=json.dumps(self.sample_payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key.key}",
            },
        )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data["success"], "true")
        self.assertIn("message_id", response_data)

        # Verify SMS was created in database
        sms = self.env["sms.message"].search(
            [("address", "=", "+1234567890"), ("body", "=", "Test SMS message")]
        )
        self.assertEqual(len(sms), 1)
        self.assertEqual(sms.phone_user_id, self.test_user)

    @patch("sms_collector.models.sms_message.SMSMessage._store_message_as_object")
    def test_duplicate_sms_handling(self, mock_store):
        """Test that duplicate SMS uploads are handled gracefully"""
        mock_store.return_value = None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key.key}",
        }

        # Upload first SMS
        response1 = self.url_open(
            "/sms/upload", data=json.dumps(self.sample_payload), headers=headers
        )
        self.assertEqual(response1.status_code, 200)
        response1_data = response1.json()
        message_id_1 = response1_data["message_id"]

        # Upload same SMS again
        response2 = self.url_open(
            "/sms/upload", data=json.dumps(self.sample_payload), headers=headers
        )
        self.assertEqual(response2.status_code, 200)
        response2_data = response2.json()

        # Should return same message ID (duplicate detection)
        self.assertEqual(response2_data["message_id"], message_id_1)

        # Verify only one SMS exists in database
        sms_count = self.env["sms.message"].search_count(
            [("address", "=", "+1234567890"), ("body", "=", "Test SMS message")]
        )
        self.assertEqual(sms_count, 1)

    @patch("sms_collector.models.sms_message.SMSMessage._store_message_as_object")
    def test_null_character_removal(self, mock_store):
        """Test that null characters are removed from SMS body"""
        mock_store.return_value = None

        payload = self.sample_payload.copy()
        payload["body"] = "Test\x00message\x00with\x00nulls"
        payload["_id"] = 12346  # Different ID to avoid duplicate

        response = self.url_open(
            "/sms/upload",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key.key}",
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify null characters were removed
        sms = self.env["sms.message"].search([("idx", "=", 12346)])
        self.assertEqual(sms.body, "Testmessagewithnulls")

    def test_malformed_json_handling(self):
        """Test API handles malformed JSON gracefully"""
        response = self.url_open(
            "/sms/upload",
            data='{"invalid": json malformed',
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key.key}",
            },
        )

        # Should return an error, not crash
        self.assertNotEqual(response.status_code, 200)

    @patch("sms_collector.models.sms_message.SMSMessage._store_message_as_object")
    def test_missing_required_fields(self, mock_store):
        """Test API handles missing required fields"""
        mock_store.return_value = None

        # Payload missing required _id field
        incomplete_payload = {
            "thread_id": 1,
            "address": "+1234567890",
            "body": "Test message",
        }

        response = self.url_open(
            "/sms/upload",
            data=json.dumps(incomplete_payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key.key}",
            },
        )

        # Should return an error
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("error", response_data)

    @patch("sms_collector.models.sms_message.SMSMessage._store_message_as_object")
    @patch("sms_collector.models.sms_filter_rule.SMSFilterRule.process_sms_message")
    def test_filter_processing_triggered(self, mock_filter, mock_store):
        """Test that filter rules are processed after SMS creation"""
        mock_store.return_value = None

        response = self.url_open(
            "/sms/upload",
            data=json.dumps(self.sample_payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key.key}",
            },
        )

        self.assertEqual(response.status_code, 200)

        # Filter processing should have been called
        mock_filter.assert_called_once()

    def test_api_key_scope_validation(self):
        """Test that API key must have correct scope"""
        # Create API key with wrong scope
        wrong_scope_key = (
            self.env["res.users.apikeys"]
            .sudo()
            .create(
                {
                    "user_id": self.test_user.id,
                    "name": "Wrong Scope Key",
                    "key": "wrong_scope_key_123",
                    "scope": "read",  # Not 'rpc'
                }
            )
        )

        response = self.url_open(
            "/sms/upload",
            data=json.dumps(self.sample_payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {wrong_scope_key.key}",
            },
        )

        # Should be rejected due to wrong scope
        self.assertEqual(response.status_code, 401)


class TestSMSBulkAPI(HttpCase):
    def setUp(self):
        super(TestSMSBulkAPI, self).setUp()

        self.test_user = self.env["res.users"].create(
            {
                "name": "Bulk API User",
                "login": "bulk_api_user",
                "email": "bulk_api@example.com",
            }
        )

        self.api_key = (
            self.env["res.users.apikeys"]
            .sudo()
            .create(
                {
                    "user_id": self.test_user.id,
                    "name": "Bulk SMS API Key",
                    "key": "bulk_api_key_12345",
                    "scope": "rpc",
                }
            )
        )

        self.auth_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key.key}",
        }

        self.sample_message = {
            "_id": 10001,
            "thread_id": 1,
            "address": "+1234567890",
            "date": 1640995200000,
            "date_sent": 1640995000000,
            "body": "Bulk test message",
            "service_center": "+1234567891",
        }

    def _bulk_payload(self, messages):
        return json.dumps({"messages": messages})

    @patch("sms_collector.models.sms_message.SMSMessage._store_message_as_object")
    def test_bulk_upload_single_message(self, mock_store):
        """Bulk endpoint accepts a single-element batch"""
        mock_store.return_value = None

        response = self.url_open(
            "/sms/upload/bulk",
            data=self._bulk_payload([self.sample_message]),
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["total"], 1)
        self.assertEqual(body["summary"]["accepted"], 1)
        self.assertEqual(body["summary"]["errors"], 0)
        self.assertIn("message_id", body["results"][0])

    @patch("sms_collector.models.sms_message.SMSMessage._store_message_as_object")
    def test_bulk_upload_multiple_messages(self, mock_store):
        """Bulk endpoint stores all messages and returns correct summary"""
        mock_store.return_value = None

        messages = [
            dict(self.sample_message, **{"_id": 10001 + i, "body": f"Message {i}"})
            for i in range(5)
        ]

        response = self.url_open(
            "/sms/upload/bulk",
            data=self._bulk_payload(messages),
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["total"], 5)
        self.assertEqual(body["summary"]["accepted"], 5)
        self.assertEqual(body["summary"]["errors"], 0)
        self.assertEqual(len(body["results"]), 5)

        # Verify all stored
        count = self.env["sms.message"].search_count(
            [("phone_user_id", "=", self.test_user.id)]
        )
        self.assertEqual(count, 5)

    @patch("sms_collector.models.sms_message.SMSMessage._store_message_as_object")
    def test_bulk_upload_partial_errors(self, mock_store):
        """Invalid messages in a batch are reported individually; valid ones are stored"""
        mock_store.return_value = None

        messages = [
            self.sample_message,
            {"_id": "not-an-int", "body": "bad"},  # invalid
            dict(self.sample_message, **{"_id": 10002, "body": "Good message 2"}),
        ]

        response = self.url_open(
            "/sms/upload/bulk",
            data=self._bulk_payload(messages),
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["total"], 3)
        self.assertEqual(body["summary"]["accepted"], 2)
        self.assertEqual(body["summary"]["errors"], 1)

        # Index 1 should be the error
        error_results = [r for r in body["results"] if "error" in r]
        self.assertEqual(len(error_results), 1)
        self.assertEqual(error_results[0]["index"], 1)

    @patch("sms_collector.models.sms_message.SMSMessage._store_message_as_object")
    def test_bulk_upload_duplicates_counted(self, mock_store):
        """Duplicate messages within a batch do not raise errors"""
        mock_store.return_value = None

        messages = [self.sample_message, self.sample_message]

        response = self.url_open(
            "/sms/upload/bulk",
            data=self._bulk_payload(messages),
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        # Both should succeed (second returns existing record)
        self.assertEqual(body["summary"]["errors"], 0)
        self.assertEqual(len(body["results"]), 2)
        # Both results point to the same message_id
        ids = [r["message_id"] for r in body["results"]]
        self.assertEqual(ids[0], ids[1])

        # Only one record should exist
        count = self.env["sms.message"].search_count(
            [("address", "=", "+1234567890"), ("body", "=", "Bulk test message")]
        )
        self.assertEqual(count, 1)

    def test_bulk_upload_missing_messages_key(self):
        """Request without messages key returns 400"""
        response = self.url_open(
            "/sms/upload/bulk",
            data=json.dumps({"data": []}),
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("messages", response.json()["error"])

    def test_bulk_upload_empty_array(self):
        """Empty messages array returns 400"""
        response = self.url_open(
            "/sms/upload/bulk",
            data=self._bulk_payload([]),
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_bulk_upload_exceeds_max(self):
        """Batch larger than the 1000-message limit returns 400"""
        messages = [
            dict(self.sample_message, **{"_id": i})
            for i in range(1001)
        ]
        response = self.url_open(
            "/sms/upload/bulk",
            data=self._bulk_payload(messages),
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("1000", response.json()["error"])

    def test_bulk_upload_requires_auth(self):
        """Bulk endpoint rejects unauthenticated requests"""
        response = self.url_open(
            "/sms/upload/bulk",
            data=self._bulk_payload([self.sample_message]),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 401)
