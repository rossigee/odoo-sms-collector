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

        # Handle message appropriately within Odoo (renaming underscore-prefixed id field)
        data["idx"] = data.pop("_id")
        data["phone_user_id"] = user_id
        data["body"] = data["body"].translate({ord(c): None for c in "\u0000"})

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
