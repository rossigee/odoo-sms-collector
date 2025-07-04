# -*- coding: utf-8 -*-

import hashlib
import io
import json
import logging
from datetime import datetime, timezone

from minio import Minio
from minio.error import S3Error
from odoo import api, fields, http, models
from odoo.http import Controller, request, route
from werkzeug.wrappers import Response

_logger = logging.getLogger(__name__)


class SMSMessage(models.Model):
    _name = "sms.message"
    _inherit = ["mail.thread"]
    _description = "SMS Message"

    # Fields based on the JSON structure
    idx = fields.Integer(string="Internal index")
    thread_id = fields.Integer(string="Thread ID")
    address = fields.Char(string="Sender/Recipient")
    date_received = fields.Datetime(string="Date Received")
    date_sent = fields.Datetime(string="Date Sent")
    body = fields.Text(string="Message Body")
    service_center = fields.Char(string="Service Center")
    phone_user_id = fields.Many2one("res.users", string="Phone user")
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

    @api.model
    def create(self, vals_list):
        def _epoch_date(ms):
            d = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
            return d.replace(tzinfo=None)

        # Create the internal representation
        real_vals_list = {
            "idx": vals_list["idx"],
            "thread_id": vals_list["thread_id"],
            "phone_user_id": vals_list["phone_user_id"],
            "address": vals_list["address"],
            "date_received": _epoch_date(vals_list["date"]),
            "date_sent": _epoch_date(vals_list["date_sent"]),
            "body": vals_list["body"],
            "service_center": vals_list["service_center"],
        }

        # Calculate message hash to prevent duplicates
        hash_data = {
            "address": real_vals_list["address"],
            "date_sent": str(real_vals_list["date_sent"]),
            "body": real_vals_list["body"],
            "thread_id": real_vals_list["thread_id"],
        }
        hash_string = json.dumps(hash_data, sort_keys=True)
        message_hash = hashlib.sha256(hash_string.encode("utf-8")).hexdigest()
        real_vals_list["message_hash"] = message_hash

        # Check if message already exists
        existing = self.search([("message_hash", "=", message_hash)], limit=1)
        if existing:
            _logger.info(
                f"Duplicate SMS detected with hash {message_hash}, skipping creation"
            )
            return existing

        # Handle multiple records creation
        new_records = super(SMSMessage, self).create(real_vals_list)

        for record, vals in zip(
            new_records, vals_list if isinstance(vals_list, list) else [vals_list]
        ):
            # Store a copy in SMS archive object store for re-ingestion later if necessary
            record._store_message_as_object(vals)

            # Try to associate with partner based on phone number
            record._find_and_associate_partner()

            # Process through filter rules
            self.env["sms.filter.rule"].process_sms_message(record)

        return new_records

    def read(self, fields=None, load="_classic_read"):
        return super(SMSMessage, self).read(fields, load)

    @staticmethod
    def _get_minio_client(params):
        if not hasattr(SMSMessage, "_minio_client"):
            minio_endpoint = params.get_param("sms_collector.minio_endpoint", "")
            minio_secure = params.get_param("sms_collector.minio_secure", True)
            minio_access_key = params.get_param("sms_collector.minio_access_key", "")
            minio_secret_key = params.get_param("sms_collector.minio_secret_key", "")
            bucket_name = params.get_param("sms_collector.minio_bucket_name", "")
            
            # Check if MinIO is configured
            if not all([minio_endpoint, minio_access_key, minio_secret_key, bucket_name]):
                _logger.warning(
                    "MinIO configuration incomplete. Required: endpoint, access_key, secret_key, bucket_name"
                )
                return None

            try:
                SMSMessage._minio_client = Minio(
                    minio_endpoint,
                    access_key=minio_access_key,
                    secret_key=minio_secret_key,
                    secure=minio_secure,
                )
            except Exception as e:
                _logger.error(f"Failed to create MinIO client: {str(e)}")
                return None
                
        return SMSMessage._minio_client

    def _store_message_as_object(self, data):
        params = self.env["ir.config_parameter"].sudo()
        
        try:
            client = self._get_minio_client(params)
            if client is None:
                _logger.warning("MinIO client not configured, skipping object storage")
                return

            # Get user details
            user = self.env["res.users"].browse([self.env.uid])

            # Calculate SHA256 hash of the data for the object key
            jsondata = json.dumps(data).encode("utf-8")
            sha256_hash = hashlib.sha256(jsondata).hexdigest()
            object_key = f"{user.login}/{sha256_hash}.json"

            # Check if the bucket exists, create it if it doesn't
            bucket_name = params.get_param("sms_collector.minio_bucket_name")
            
            try:
                if not client.bucket_exists(bucket_name):
                    _logger.error(f"Bucket does not exist or cannot be found: {bucket_name}")
                    return
            except S3Error as e:
                _logger.error(f"MinIO connection error while checking bucket: {str(e)}")
                return
            except Exception as e:
                _logger.error(f"Unexpected error checking MinIO bucket: {str(e)}")
                return

            # Upload the data to the bucket
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
            # Don't fail SMS creation just because MinIO storage failed

    def _find_and_associate_partner(self):
        """Try to find and associate a partner based on the phone number"""
        if self.partner_id or not self.address:
            return

        # Clean phone number for search
        phone_clean = self.address.replace(" ", "").replace("-", "").replace("+", "")

        # Search in both phone and mobile fields
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
