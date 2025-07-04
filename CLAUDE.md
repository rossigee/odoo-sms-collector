# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SMS Collector is an Odoo 16 module that provides an HTTP endpoint for mobile phones to upload SMS messages. It stores messages in PostgreSQL with optional MinIO/S3 archival.

## Key Architecture

- **API Endpoint**: `/sms/upload` - POST endpoint accepting JSON with SMS data
- **Authentication**: Bearer token validation against `sms.api.key` records
- **Storage**: Dual storage system - PostgreSQL for active data, MinIO/S3 for archival
- **Filtering System**: Configurable rules for automatic SMS processing:
  - OTP detection and channel forwarding
  - Partner association and chatter posting
  - Transaction parsing from SMS content
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

- `controllers/main.py` - REST API endpoint implementation
- `models/sms_message.py` - SMS message model with MinIO integration and partner association
- `models/sms_filter_rule.py` - Configurable filtering rules for SMS processing
- `security/sms_collector_security.xml` - Access control rules
- `views/` - Odoo UI views for message browsing and filter management
- `data/sms_filter_rule_data.xml` - Example filter rules (disabled by default)

## Important Implementation Details

1. **MinIO Integration**: The module gracefully handles MinIO failures - SMS messages are still stored in PostgreSQL even if MinIO storage fails. All MinIO operations are wrapped in try-catch blocks with appropriate logging.

2. **API Format**: The `/sms/upload` endpoint expects:
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
   All fields are required and validated for type and format.

3. **SMS Filtering**: Messages are automatically processed through filter rules that can:
   - Forward OTP messages to dedicated channels
   - Add SMS to partner chatter when phone numbers match
   - Parse transaction details using regex patterns
   - Stop processing on match or continue through all rules

4. **Security**: 
   - API keys are stored in plain text (standard Odoo behavior)
   - Bearer token authentication via Authorization header
   - Comprehensive input validation on all fields
   - Always use HTTPS in production

5. **Testing**: Priority areas for testing:
   - API endpoint authentication
   - SMS data validation edge cases
   - MinIO failure scenarios
   - Partner linking logic
   - Filter rule processing

## Migration Notes

### Version 16.0.2.0.2
- Adds SHA256 hash-based duplicate prevention
- **Migration scripts** in `migrations/16.0.2.0.2/`:
  - `pre-migration.py`: Calculates hashes for existing messages and removes duplicates
  - `post-migration.py`: Verifies migration success
  - **TO BE REMOVED**: These scripts can be removed in version 16.0.3.0.0 or later

## Known Issues

- API keys stored in plain text (standard Odoo behavior - documented in security considerations)
- No rate limiting implemented (should be done at reverse proxy level)
