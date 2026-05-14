# SMS Collector for Odoo

A powerful SMS collection and processing module that provides an HTTP API endpoint for mobile phones to upload SMS messages, with intelligent filtering, duplicate prevention, and automated processing capabilities.

## 📱 Key Features

- **HTTP API Endpoint**: Secure `/sms/upload` endpoint with Bearer token authentication
- **Input Validation**: Comprehensive validation for all API fields with detailed error messages
- **Duplicate Prevention**: SHA256-based deduplication ensures no duplicate messages
- **Smart Filtering**: Configurable rules for automatic SMS processing
- **OTP Detection**: Automatically route verification codes to dedicated channels
- **Partner Integration**: Link SMS messages to existing contacts in your database
- **Transaction Parsing**: Extract and process bank transfer details from SMS
- **MinIO/S3 Storage**: Archive messages in object storage with graceful error handling
- **Comprehensive Testing**: Full test suite with 30+ test methods

## 🚀 Quick Start

### 1. Install the Module

```bash
# Install Python dependencies
pip install minio

# Place the module in your Odoo addons directory
cp -r sms_collector /path/to/odoo/addons/

# Update module list and install through Odoo UI
```

### 2. Configure MinIO/S3 Storage (Optional)

Go to Settings > Technical > System Parameters and configure:
- `sms_collector.minio_endpoint`: Your MinIO/S3 endpoint
- `sms_collector.minio_access_key`: Access key
- `sms_collector.minio_secret_key`: Secret key
- `sms_collector.bucket_name`: Bucket name for SMS storage

### 3. Create API Keys for Mobile Apps

Generate API keys for users who will upload SMS:
1. Go to user preferences
2. Create a new API key with "RPC" scope
3. Use this key in the Authorization header

### 4. Configure SMS Filter Rules

Navigate to SMS Collector > Filter Rules to set up automatic processing:

```python
# Example OTP rule (built-in but disabled by default)
Name: OTP Messages
Match Type: Regular Expression
Match Value: \b(OTP|verification code|verify|code)\b
Action: Post to Channel
Channel Name: #otp
```

## 📋 Requirements

- **Odoo**: 16.0 or later
- **Python**: `minio` library for object storage
- **Mobile App**: Any SMS backup app that supports HTTP POST
- **Network**: HTTPS connectivity from mobile devices

## 🛡️ Security

- **API Authentication**: Bearer token authentication (API keys stored in plain text - use HTTPS)
- **Input Validation**: Comprehensive field validation with type checking and sanitization
- **Duplicate Prevention**: SHA256 hashing prevents duplicate messages
- **Access Control**: Role-based permissions for viewing and managing SMS
- **Data Protection**: Null character sanitization and SQL injection protection
- **Storage Security**: Optional MinIO/S3 archival with failure resilience

## 📖 API Documentation

### Upload Endpoint

```bash
POST /sms/upload
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json

{
  "_id": 12345,              # Required: integer
  "thread_id": 1,            # Required: integer
  "address": "+1234567890",  # Required: phone number or short code
  "date": 1640995200000,     # Required: epoch milliseconds
  "date_sent": 1640995000000,# Required: epoch milliseconds
  "body": "Your message text",# Required: string (max 160,000 chars)
  "service_center": "+1234567891" # Required: string
}
```

### Response

```json
# Success
{
  "success": "true",
  "message_id": 123
}

# Duplicate (still returns 200 OK)
{
  "success": "true",
  "message": "Duplicate message, skipped"
}

# Validation Error (400)
{
  "error": "Missing required fields: _id, body"
}
```

## 🧪 Testing

Run the test suite using Docker:

```bash
docker-compose up -d postgres
docker-compose run odoo-test bash /usr/local/bin/run-tests.sh
```

The test suite includes:
- SMS message creation and duplicate prevention
- Filter rule matching and execution
- API endpoint authentication and security
- Partner association and chatter integration
- Transaction parsing from SMS content

## 🔧 Configuration Examples

### Filter Rule for Bank Transfers
```
Name: Bank Transfers
Match Type: Regular Expression  
Match Value: (received|sent|transfer|deposited)
Action: Multiple Actions
- Post to Channel: #banking
- Parse Transaction: Yes
- Transaction Regex: (?P<amount>[\d,]+\.?\d*)\s*(?P<currency>[A-Z]{3}).*?from\s*(?P<partner_name>[\w\s]+)
```

### Auto-Partner Association
```
Name: Known Partners
Match Type: Has Associated Partner
Action: Add to Partner Chatter
Partner Search Field: Mobile
```

## 📄 License

This module is licensed under AGPL-3.0 or later.

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run pre-commit hooks: `pre-commit run --all-files`
5. Ensure all tests pass
6. Submit a pull request

## 📚 Documentation

- **[API Reference](sms_collector/docs/api.rst)**: Complete API documentation with examples
- **[Configuration Guide](sms_collector/docs/configuration.rst)**: Detailed setup instructions
- **[Development Guide](CLAUDE.md)**: Guidelines for contributors and developers

## 📞 Support

- **Issues**: Report bugs and feature requests on GitHub
- **Documentation**: See docs folder for comprehensive guides
- **Security**: Use GitHub's security tab for vulnerability reports

---

**💡 Pro Tips**: 
- Enable example filter rules in SMS Collector > Filter Rules
- Use MinIO/S3 for long-term SMS archival (failures won't block SMS storage)
- Always use HTTPS in production to protect API keys
- Set up channels before enabling OTP forwarding rules
- Test filter rules with the built-in message browser
- Rotate API keys regularly for better security
