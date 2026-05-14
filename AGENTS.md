# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SMS Collector is an Odoo 16 module that provides HTTP endpoints for mobile phones to upload SMS messages. It stores messages in PostgreSQL with optional MinIO/S3 archival.

## Key Architecture

- **API Endpoints**:
  - `POST /sms/upload` — single SMS upload
  - `POST /sms/upload/bulk` — batch upload (up to 1000 messages per request)
- **Authentication**: Bearer token validated against `res.users.apikeys` records (Odoo's built-in API key system)
- **Device Tracking**: `sms.device` model links API keys to named physical devices; auto-created on first upload per user
- **Storage**: Dual storage — PostgreSQL for active data, MinIO/S3 for archival under `{user}/{device}/{sha256}.json`
- **Filtering System**: Configurable rules for automatic SMS processing:
  - OTP detection and channel forwarding
  - Partner association and chatter posting
  - Transaction parsing from SMS content
- **Statistics**: Graph and pivot views accessible via SMS Collector → Statistics
- **Requeue**: `sms.message.requeue_from_minio()` re-ingests archived messages; duplicates skipped via hash check
- **Dependencies**: Requires `minio` Python package for object storage functionality

## Development Commands

### Running Tests
```bash
# Using Docker (recommended)
docker-compose up -d postgres
docker-compose run odoo-test bash /usr/local/bin/run-tests.sh

# Local installation
pip install minio
./run-tests.sh
```

### Installation
```bash
# Copy module to Odoo addons path
cp -r sms_collector /path/to/odoo/addons/

# Update module list and install via Odoo UI or CLI
```

## Code Structure

- `controllers/controllers.py` — REST API endpoint implementation (`upload`, `upload_bulk`)
- `models/sms_message.py` — SMS message model with MinIO integration, partner association, and requeue logic
- `models/sms_device.py` — Physical device model; auto-created per user on first upload
- `models/sms_filter_rule.py` — Configurable filtering rules for SMS processing
- `models/sms_collector_config.py` — Extends `res.config.settings` for MinIO configuration
- `security/sms_collector_security.xml` — Access control rules
- `views/` — Odoo UI views for messages, devices, filter rules, statistics, and settings
- `data/sms_filter_rule_data.xml` — Example filter rules (disabled by default)
- `migrations/16.0.2.0.2/` — Hash migration scripts (to be removed in 16.0.3.0.0)

## Important Implementation Details

1. **MinIO Integration**: The module gracefully handles MinIO failures — SMS messages are still stored in PostgreSQL even if MinIO storage fails. All MinIO operations are wrapped in try-catch blocks. The MinIO client is created fresh per call (no caching) so config changes take effect immediately.

2. **API Format**: Both endpoints share the same per-message schema:
   ```json
   {
     "_id": 12345,
     "thread_id": 67890,
     "address": "+1234567890",
     "date": 1704067200000,
     "date_sent": 1704067100000,
     "body": "SMS content",
     "service_center": "+1234567890"
   }
   ```
   The bulk endpoint wraps an array: `{"messages": [{...}, ...]}`.
   All fields are required and validated for type and format.

3. **Device tracking**: On every authenticated upload the controller calls `_find_or_create_device()`, which finds the most-recently-seen active `sms.device` for the user (or creates one named `{login}-device-1`). The device's `last_seen` is stamped. Users with multiple phones should pre-create named device records in the UI.

4. **Duplicate prevention**: SHA-256 hash of `(address, date_sent, body, thread_id)` — checked in `create()` before insert and enforced by a DB unique constraint. `create()` returns the existing record silently for duplicates.

5. **SMS Filtering**: Messages are automatically processed through active filter rules (ordered by `sequence`) that can:
   - Forward OTP messages to dedicated channels
   - Add SMS to partner chatter when phone numbers match
   - Parse transaction details using regex patterns
   - Stop processing on match or continue through all rules
   - All HTML content in posts is escaped to prevent XSS

6. **Security**:
   - API keys are managed by Odoo's `res.users.apikeys` (keys are stored hashed, not plain text)
   - Bearer token authentication via Authorization header
   - Comprehensive input validation on all fields
   - Regular users cannot delete SMS records (admin-only)
   - Always use HTTPS in production

7. **Testing**: Priority areas for testing:
   - API endpoint authentication (single and bulk)
   - SMS data validation edge cases
   - MinIO failure scenarios
   - Device auto-creation and last_seen update
   - Partner linking logic
   - Filter rule processing and stop-processing behaviour
   - `requeue_from_minio` deduplication

## Migration Notes

### Version 16.0.2.1.0
- Renames config parameter key `sms_collector.minio_bucket_name` → `sms_collector.bucket_name`
- **Migration script** in `migrations/16.0.2.1.0/`:
  - `pre-migration.py`: Renames the key in `ir_config_parameter` for existing installations

### Version 16.0.2.0.2
- Adds SHA256 hash-based duplicate prevention
- **Migration scripts** in `migrations/16.0.2.0.2/`:
  - `pre-migration.py`: Calculates hashes for existing messages and removes duplicates
  - `post-migration.py`: Verifies migration success
  - **TO BE REMOVED**: These scripts can be removed in version 16.0.3.0.0 or later

## Known Issues

- No rate limiting at the module level (handle at reverse proxy — see `docs/configuration.rst`)
