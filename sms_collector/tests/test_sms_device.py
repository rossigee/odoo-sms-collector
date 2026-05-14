# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase


class TestSMSDevice(TransactionCase):
    def setUp(self):
        super(TestSMSDevice, self).setUp()

        self.test_user = self.env["res.users"].create(
            {
                "name": "Device Test User",
                "login": "device_test_user",
                "email": "device_test@example.com",
            }
        )

        self.sample_sms_data = {
            "idx": 20001,
            "thread_id": 1,
            "phone_user_id": self.test_user.id,
            "address": "+1234567890",
            "date": 1640995200000,
            "date_sent": 1640995000000,
            "body": "Device test message",
            "service_center": "+1234567891",
        }

    def test_device_creation(self):
        """Test basic device creation"""
        device = self.env["sms.device"].create(
            {
                "name": "Alice's Pixel 9",
                "user_id": self.test_user.id,
                "platform": "android",
            }
        )
        self.assertTrue(device.id)
        self.assertEqual(device.name, "Alice's Pixel 9")
        self.assertEqual(device.user_id, self.test_user)
        self.assertTrue(device.active)

    def test_unique_name_per_user(self):
        """Two devices with the same name for the same user are rejected"""
        self.env["sms.device"].create(
            {"name": "My Phone", "user_id": self.test_user.id}
        )
        with self.assertRaises(Exception):
            self.env["sms.device"].create(
                {"name": "My Phone", "user_id": self.test_user.id}
            )

    def test_same_name_different_users_allowed(self):
        """Two users can each have a device with the same name"""
        other_user = self.env["res.users"].create(
            {"name": "Other User", "login": "other_user_dev", "email": "other@example.com"}
        )
        self.env["sms.device"].create(
            {"name": "My Phone", "user_id": self.test_user.id}
        )
        device2 = self.env["sms.device"].create(
            {"name": "My Phone", "user_id": other_user.id}
        )
        self.assertTrue(device2.id)

    def test_message_count(self):
        """message_count reflects number of SMS linked to the device"""
        device = self.env["sms.device"].create(
            {"name": "Counter Phone", "user_id": self.test_user.id}
        )
        self.assertEqual(device.message_count, 0)

        self.env["sms.message"].create(
            dict(self.sample_sms_data, device_id=device.id)
        )
        self.assertEqual(device.message_count, 1)

        self.env["sms.message"].create(
            dict(self.sample_sms_data, idx=20002, body="Second message", device_id=device.id)
        )
        self.assertEqual(device.message_count, 2)

    def test_action_view_messages(self):
        """action_view_messages returns a window action filtered to this device"""
        device = self.env["sms.device"].create(
            {"name": "Action Phone", "user_id": self.test_user.id}
        )
        action = device.action_view_messages()

        self.assertEqual(action["res_model"], "sms.message")
        self.assertIn(("device_id", "=", device.id), action["domain"])

    def test_archiving_device(self):
        """Archiving a device hides it from default searches"""
        device = self.env["sms.device"].create(
            {"name": "Old Phone", "user_id": self.test_user.id}
        )
        device.active = False

        active_devices = self.env["sms.device"].search(
            [("user_id", "=", self.test_user.id)]
        )
        self.assertNotIn(device, active_devices)

    def test_messages_survive_device_archive(self):
        """SMS messages are preserved when their device is archived (ondelete=set null)"""
        device = self.env["sms.device"].create(
            {"name": "Ephemeral Phone", "user_id": self.test_user.id}
        )
        sms = self.env["sms.message"].create(
            dict(self.sample_sms_data, device_id=device.id)
        )
        device.unlink()

        sms_still_exists = self.env["sms.message"].search([("id", "=", sms.id)])
        self.assertEqual(len(sms_still_exists), 1)
        self.assertFalse(sms_still_exists.device_id)
