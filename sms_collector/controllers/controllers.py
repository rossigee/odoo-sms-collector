# -*- coding: utf-8 -*-

import json
import logging

from odoo import fields
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = [
    "_id",
    "thread_id",
    "address",
    "date",
    "date_sent",
    "body",
    "service_center",
]

_MAX_BULK = 1000


def _json_response(data, status=200):
    return request.make_json_response(data, status=status)


def _validate_payload(data):
    """Validate and sanitize a single SMS payload dict.

    Returns (cleaned_data, error_string). On success error_string is None.
    Does not mutate the input dict.
    """
    if not isinstance(data, dict):
        return None, "message must be a JSON object"

    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        return None, f"Missing required fields: {', '.join(missing)}"

    try:
        if not isinstance(data["_id"], int):
            return None, "_id must be an integer"

        if not isinstance(data["thread_id"], int):
            return None, "thread_id must be an integer"

        if not isinstance(data["address"], str) or not data["address"].strip():
            return None, "address must be a non-empty string"

        if not isinstance(data["date"], int) or data["date"] < 0:
            return None, "date must be a positive integer (epoch milliseconds)"

        if not isinstance(data["date_sent"], int) or data["date_sent"] < 0:
            return None, "date_sent must be a positive integer (epoch milliseconds)"

        if not isinstance(data["body"], str):
            return None, "body must be a string"

        if not isinstance(data["service_center"], str):
            return None, "service_center must be a string"

        body = data["body"].translate({ord(c): None for c in "\x00"})

        if len(body) > 160000:
            return None, "body exceeds maximum length of 160000 characters"

        address_clean = (
            data["address"]
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )
        if not address_clean:
            return None, "address is empty after cleaning"

        if (
            not (address_clean.startswith("+") and address_clean[1:].isdigit())
            and not address_clean.isdigit()
        ):
            if not address_clean.replace("+", "").replace("_", "").isalnum():
                return None, "address must be a valid phone number or short code"

    except Exception as e:
        _logger.error(f"Error validating input data: {str(e)}")
        return None, f"Invalid input data: {str(e)}"

    cleaned = dict(data)
    cleaned["body"] = body
    return cleaned, None


def _authenticate():
    """Validate the Bearer token and return (user_id, user, device_id, error_response).

    On failure the first three values are None and error_response is a Response object.
    On success, error_response is None.
    """
    auth_header = request.httprequest.headers.get("Authorization")
    if not auth_header:
        return None, None, None, _json_response({"error": "No Authorization header provided"}, 401)
    if not auth_header.startswith("Bearer "):
        return None, None, None, _json_response({"error": "Invalid Authorization format"}, 401)
    api_key = auth_header.split(" ")[1]
    user_id = request.env["res.users.apikeys"]._check_credentials(
        scope="rpc", key=api_key
    )
    if not user_id:
        return None, None, None, _json_response({"error": "Invalid API key"}, 401)
    user = request.env["res.users"].sudo().browse(user_id)
    if not user.exists():
        return None, None, None, _json_response({"error": "Invalid API key"}, 401)

    device = _find_or_create_device(user)

    return user_id, user, device.id, None


def _find_or_create_device(user):
    """Return the active sms.device for this user, creating one if none exists."""
    Device = user.env["sms.device"].sudo()
    device = Device.search(
        [("user_id", "=", user.id), ("active", "=", True)],
        order="last_seen desc",
        limit=1,
    )
    if not device:
        device = Device.create({"name": f"{user.login}-device-1", "user_id": user.id})

    device.write({"last_seen": fields.Datetime.now()})
    return device


def _parse_json_body():
    """Parse the request body as JSON; return (data, error_response)."""
    try:
        data = json.loads(request.httprequest.data or b"{}")
    except (ValueError, TypeError) as e:
        return None, _json_response({"error": f"Invalid JSON: {str(e)}"}, 400)
    return data, None


class SMSUploadController(Controller):
    @route("/sms/upload", methods=["POST"], auth="public", type="http", csrf=False)
    def upload(self, **kw):
        user_id, user, device_id, err = _authenticate()
        if err:
            return err

        data, err = _parse_json_body()
        if err:
            return err

        if not isinstance(data, dict):
            return _json_response({"error": "Request body must be a JSON object"}, 400)

        cleaned, error = _validate_payload(data)
        if error:
            return _json_response({"error": error}, 400)

        _logger.info(json.dumps(cleaned))

        cleaned["idx"] = cleaned.pop("_id")
        cleaned["phone_user_id"] = user_id
        cleaned["device_id"] = device_id

        try:
            sms_record = request.env["sms.message"].with_user(user).create(cleaned)
            if sms_record:
                return _json_response({"success": "true", "message_id": sms_record.id})
            else:
                return _json_response({"error": "Failed to create SMS message"}, 500)
        except Exception as e:
            _logger.error(f"Error creating SMS message: {str(e)}")
            if "unique_message_hash" in str(e):
                return _json_response({"success": "true", "message": "Duplicate message, skipped"})
            return _json_response({"error": str(e)}, 500)

    @route("/sms/upload/bulk", methods=["POST"], auth="public", type="http", csrf=False)
    def upload_bulk(self, **kw):
        user_id, user, device_id, err = _authenticate()
        if err:
            return err

        data, err = _parse_json_body()
        if err:
            return err

        if not isinstance(data, dict):
            return _json_response({"error": "Request body must be a JSON object"}, 400)

        messages = data.get("messages")
        if not isinstance(messages, list) or not messages:
            return _json_response({"error": "messages must be a non-empty array"}, 400)

        if len(messages) > _MAX_BULK:
            return _json_response({"error": f"Batch size exceeds maximum of {_MAX_BULK}"}, 400)

        results = []
        accepted = 0
        errors = 0

        for i, msg in enumerate(messages):
            cleaned, error = _validate_payload(msg)
            if error:
                results.append({"index": i, "error": error})
                errors += 1
                continue

            _logger.info(json.dumps(cleaned))

            cleaned["idx"] = cleaned.pop("_id")
            cleaned["phone_user_id"] = user_id
            cleaned["device_id"] = device_id

            try:
                sms_record = request.env["sms.message"].with_user(user).create(cleaned)
                results.append({"index": i, "message_id": sms_record.id})
                accepted += 1
            except Exception as e:
                _logger.error(f"Error creating SMS message at index {i}: {str(e)}")
                if "unique_message_hash" in str(e):
                    results.append({"index": i, "error": "Duplicate message, skipped"})
                else:
                    results.append({"index": i, "error": str(e)})
                errors += 1

        return _json_response({
            "results": results,
            "summary": {
                "total": len(messages),
                "accepted": accepted,
                "errors": errors,
            },
        })
