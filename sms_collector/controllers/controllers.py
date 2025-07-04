# -*- coding: utf-8 -*-

import hashlib
import io
import json
import logging
from datetime import datetime

from minio import Minio
from minio.error import S3Error
from odoo import api, fields, http, models
from odoo.http import Controller, request, route
from werkzeug.wrappers import Response

_logger = logging.getLogger(__name__)

headers = {"Content-Type": "application/json"}


class SMSUploadController(Controller):
    @route("/sms/upload", methods=["POST"], auth="public", type="json")
    def index(self, **kw):
        # Authorize the request (not sure why Odoo auth parameter couldn't handle this)
        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header:
            return {"error": "No Authorization header provided"}, 401
        if not auth_header.startswith("Bearer "):
            return {"error": "Invalid Authorization format"}, 401
        api_key = auth_header.split(" ")[1]
        user_id = request.env["res.users.apikeys"]._check_credentials(
            scope="rpc", key=api_key
        )
        if not user_id:
            return {"error": "Invalid API key"}, 401
        user = request.env["res.users"].sudo().browse([user_id])[0]

        # Log parseably to the log file, for subsequent parsing and notifications by Fluentbit etc
        data = request.get_json_data()
        _logger.info(json.dumps(data))

        # Validate required fields
        required_fields = [
            "_id",
            "thread_id",
            "address",
            "date",
            "date_sent",
            "body",
            "service_center",
        ]
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)

        if missing_fields:
            return {
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }, 400

        # Validate field types and formats
        try:
            # Validate _id is an integer
            if not isinstance(data["_id"], int):
                return {"error": "_id must be an integer"}, 400

            # Validate thread_id is an integer
            if not isinstance(data["thread_id"], int):
                return {"error": "thread_id must be an integer"}, 400

            # Validate address is a non-empty string
            if not isinstance(data["address"], str) or not data["address"].strip():
                return {"error": "address must be a non-empty string"}, 400

            # Validate date fields are integers (epoch milliseconds)
            if not isinstance(data["date"], int) or data["date"] < 0:
                return {
                    "error": "date must be a positive integer (epoch milliseconds)"
                }, 400

            if not isinstance(data["date_sent"], int) or data["date_sent"] < 0:
                return {
                    "error": "date_sent must be a positive integer (epoch milliseconds)"
                }, 400

            # Validate body is a string
            if not isinstance(data["body"], str):
                return {"error": "body must be a string"}, 400

            # Validate service_center is a string (can be empty)
            if not isinstance(data["service_center"], str):
                return {"error": "service_center must be a string"}, 400

            # Sanitize body for null characters
            data["body"] = data["body"].translate({ord(c): None for c in "\u0000"})

            # Validate body length (reasonable SMS limit)
            if (
                len(data["body"]) > 160000
            ):  # Allow concatenated SMS but with reasonable limit
                return {
                    "error": "body exceeds maximum length of 160000 characters"
                }, 400

            # Validate address format (basic phone number validation)
            # Allow various phone formats but ensure it's not obviously invalid
            address_clean = (
                data["address"]
                .replace(" ", "")
                .replace("-", "")
                .replace("(", "")
                .replace(")", "")
            )
            if not address_clean:
                return {"error": "address is empty after cleaning"}, 400

            # Check if it starts with + and digits, or just digits
            if (
                not (address_clean.startswith("+") and address_clean[1:].isdigit())
                and not address_clean.isdigit()
            ):
                # Also allow alphanumeric for short codes
                if (
                    not address_clean.replace("+", "")
                    .replace("-", "")
                    .replace("_", "")
                    .isalnum()
                ):
                    return {
                        "error": "address must be a valid phone number or short code"
                    }, 400

        except Exception as e:
            _logger.error(f"Error validating input data: {str(e)}")
            return {"error": f"Invalid input data: {str(e)}"}, 400

        # Handle message appropriately within Odoo (renaming underscore-prefixed id field)
        data["idx"] = data.pop("_id")
        data["phone_user_id"] = user_id

        try:
            # Create will return existing record if duplicate is detected
            sms_record = request.env["sms.message"].with_user(user).create([data])
            if sms_record:
                return {"success": "true", "message_id": sms_record.id}, 200
            else:
                return {"error": "Failed to create SMS message"}, 500
        except Exception as e:
            _logger.error(f"Error creating SMS message: {str(e)}")
            # Check if it's a duplicate constraint error
            if "unique_message_hash" in str(e):
                return {"success": "true", "message": "Duplicate message, skipped"}, 200
            return {"error": str(e)}, 500
