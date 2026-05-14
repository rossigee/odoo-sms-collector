# -*- coding: utf-8 -*-

import hashlib
import io
import json
import logging
from datetime import datetime, timezone

from minio import Minio
from minio.error import S3Error
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SMSMessage(models.Model):
    _name = "sms.message"
    _inherit = ["mail.thread"]
    _description = "SMS Message"

    idx = fields.Integer(string="Internal index")
    thread_id = fields.Integer(string="Thread ID")
    address = fields.Char(string="Sender/Recipient")
    date_received = fields.Datetime(string="Date Received")
    date_sent = fields.Datetime(string="Date Sent")
    body = fields.Text(string="Message Body")
    service_center = fields.Char(string="Service Center")
    phone_user_id = fields.Many2one("res.users", string="Phone user")
    device_id = fields.Many2one("sms.device", string="Device", ondelete="set null")
    partner_id = fields.Many2one("res.partner", string="Partner")
    message_hash = fields.Char(
        string="Message Hash", size=64, index=True, readonly=True
    )

    _sql_constraints = [
        (
            "unique_message_hash",
            "unique(message_hash)",
            "This SMS message already exists (duplicate hash)",
        )
    ]

    @staticmethod
    def _epoch_to_dt(ms):
        d = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
        return d.replace(tzinfo=None)

    @staticmethod
    def _compute_hash(address, date_sent_dt, body, thread_id):
        """Compute the deduplication hash from already-converted field values."""
        hash_data = {
            "address": address,
            "date_sent": str(date_sent_dt),
            "body": body,
            "thread_id": thread_id,
        }
        return hashlib.sha256(
            json.dumps(hash_data, sort_keys=True).encode("utf-8")
        ).hexdigest()

    @api.model
    def create(self, vals_list):
        body = (vals_list.get("body") or "").translate({ord(c): None for c in " "})
        date_sent_dt = self._epoch_to_dt(vals_list["date_sent"])

        real_vals = {
            "idx": vals_list["idx"],
            "thread_id": vals_list["thread_id"],
            "phone_user_id": vals_list["phone_user_id"],
            "address": vals_list["address"],
            "date_received": self._epoch_to_dt(vals_list["date"]),
            "date_sent": date_sent_dt,
            "body": body,
            "service_center": vals_list["service_center"],
        }

        if vals_list.get("device_id"):
            real_vals["device_id"] = vals_list["device_id"]

        message_hash = self._compute_hash(
            real_vals["address"], date_sent_dt, body, real_vals["thread_id"]
        )
        real_vals["message_hash"] = message_hash

        existing = self.search([("message_hash", "=", message_hash)], limit=1)
        if existing:
            _logger.info(
                f"Duplicate SMS detected with hash {message_hash}, skipping creation"
            )
            return existing

        new_record = super(SMSMessage, self).create(real_vals)

        new_record._store_message_as_object(vals_list)
        new_record._find_and_associate_partner()
        self.env["sms.filter.rule"].process_sms_message(new_record)

        return new_record

    @staticmethod
    def _get_minio_client(params):
        minio_endpoint = params.get_param("sms_collector.minio_endpoint", "")
        minio_secure_str = params.get_param("sms_collector.minio_secure", "True")
        minio_secure = minio_secure_str not in ("False", "0", "")
        minio_access_key = params.get_param("sms_collector.minio_access_key", "")
        minio_secret_key = params.get_param("sms_collector.minio_secret_key", "")
        bucket_name = params.get_param("sms_collector.bucket_name", "")

        if not all([minio_endpoint, minio_access_key, minio_secret_key, bucket_name]):
            _logger.warning(
                "MinIO configuration incomplete. Required: endpoint, access_key, secret_key, bucket_name"
            )
            return None

        try:
            return Minio(
                minio_endpoint,
                access_key=minio_access_key,
                secret_key=minio_secret_key,
                secure=minio_secure,
            )
        except Exception as e:
            _logger.error(f"Failed to create MinIO client: {str(e)}")
            return None

    def _store_message_as_object(self, data):
        params = self.env["ir.config_parameter"].sudo()

        try:
            client = self._get_minio_client(params)
            if client is None:
                _logger.warning("MinIO client not configured, skipping object storage")
                return

            user_login = self.phone_user_id.login if self.phone_user_id else "unknown"
            device_name = self.device_id.name if self.device_id else "default"
            device_slug = "".join(
                c if c.isalnum() or c in "-_." else "_" for c in device_name
            )

            jsondata = json.dumps(data).encode("utf-8")
            sha256_hash = hashlib.sha256(jsondata).hexdigest()
            object_key = f"{user_login}/{device_slug}/{sha256_hash}.json"

            bucket_name = params.get_param("sms_collector.bucket_name")

            try:
                if not client.bucket_exists(bucket_name):
                    _logger.error(
                        f"Bucket does not exist or cannot be found: {bucket_name}"
                    )
                    return
            except S3Error as e:
                _logger.error(f"MinIO connection error while checking bucket: {str(e)}")
                return
            except Exception as e:
                _logger.error(f"Unexpected error checking MinIO bucket: {str(e)}")
                return

            try:
                client.put_object(
                    bucket_name,
                    object_key,
                    io.BytesIO(jsondata),
                    len(jsondata),
                    content_type="application/json",
                )
                _logger.info(f"Uploaded SMS to '{bucket_name}': {object_key}")
            except S3Error as e:
                _logger.error(f"MinIO S3 error uploading SMS: {str(e)}")
            except Exception as e:
                _logger.error(f"Unexpected error uploading SMS to MinIO: {str(e)}")

        except Exception as e:
            _logger.error(f"Failed to store message in MinIO: {str(e)}")

    def _find_and_associate_partner(self):
        if self.partner_id or not self.address:
            return

        phone_clean = self.address.replace(" ", "").replace("-", "").replace("+", "")

        partner = self.env["res.partner"].search(
            [
                "|",
                "|",
                ("phone", "ilike", phone_clean),
                ("mobile", "ilike", phone_clean),
                ("phone", "ilike", self.address),
                ("mobile", "ilike", self.address),
            ],
            limit=1,
        )

        if partner:
            self.partner_id = partner
            _logger.info(
                f"Associated SMS from {self.address} with partner {partner.name}"
            )

    @api.model
    def requeue_from_minio(self):
        """Re-ingest all archived messages from MinIO. Already-stored messages are skipped."""
        params = self.env["ir.config_parameter"].sudo()
        client = self._get_minio_client(params)
        if client is None:
            return {"error": "MinIO not configured"}

        bucket_name = params.get_param("sms_collector.bucket_name")

        try:
            if not client.bucket_exists(bucket_name):
                return {"error": f"Bucket '{bucket_name}' does not exist"}
        except S3Error as e:
            return {"error": f"MinIO error: {str(e)}"}

        created = 0
        skipped = 0
        errors = 0

        try:
            objects = list(client.list_objects(bucket_name, recursive=True))
        except Exception as e:
            _logger.error(f"Failed to list MinIO objects: {str(e)}")
            return {"error": f"Failed to list objects: {str(e)}"}

        for obj in objects:
            if not obj.object_name.endswith(".json"):
                continue
            try:
                response = client.get_object(bucket_name, obj.object_name)
                raw = response.read()
                response.close()
                response.release_conn()

                data = json.loads(raw.decode("utf-8"))

                # Determine the expected hash without calling create
                body = (data.get("body") or "").translate({ord(c): None for c in " "})
                date_sent_dt = self._epoch_to_dt(data["date_sent"])
                expected_hash = self._compute_hash(
                    data["address"], date_sent_dt, body, data["thread_id"]
                )

                if self.search([("message_hash", "=", expected_hash)], limit=1):
                    skipped += 1
                else:
                    self.create(data)
                    created += 1

            except Exception as e:
                _logger.error(
                    f"Failed to requeue object '{obj.object_name}': {str(e)}"
                )
                errors += 1

        _logger.info(
            f"MinIO requeue complete: {created} created, {skipped} skipped, {errors} errors"
        )
        return {"created": created, "skipped": skipped, "errors": errors}
