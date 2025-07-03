# SMS Collector Tests

This directory contains comprehensive tests for the SMS Collector module following Odoo testing best practices.

## Test Structure

### `test_sms_message.py`
Tests for the core SMS message model:
- **Message Creation**: Basic SMS message creation and field validation
- **Hash Calculation**: SHA256 hash generation for duplicate prevention
- **Duplicate Prevention**: Ensuring duplicate messages return existing records
- **Partner Association**: Automatic linking of SMS to partners based on phone numbers
- **Date Conversion**: Epoch millisecond to datetime conversion
- **Data Sanitization**: Null character removal from message bodies
- **Hash Uniqueness**: Different messages produce different hashes

### `test_sms_filter_rule.py`
Tests for the SMS filtering system:
- **Rule Creation**: Basic filter rule creation and configuration
- **Matching Logic**:
  - Contains text matching (case sensitive/insensitive)
  - Regular expression matching
  - Sender phone number matching
  - Partner association matching
- **Actions**:
  - Channel posting (with auto-creation)
  - Partner chatter integration
  - Transaction parsing
- **Rule Processing**: Sequence order and stop_processing behavior

### `test_sms_api.py`
Tests for the REST API endpoint:
- **Authentication**: API key validation and authorization
- **Error Handling**: Missing headers, invalid keys, malformed data
- **SMS Processing**: Successful uploads and duplicate handling
- **Data Validation**: Required fields and null character removal
- **Integration**: Filter rule processing after SMS creation

## Running Tests

### Using Docker (Recommended)
```bash
docker-compose up -d postgres
docker-compose run odoo-test bash /usr/local/bin/run-tests.sh
```

### Manual Execution
```bash
# Install dependencies
pip install minio coverage

# Run specific test file
odoo -d test_db --test-enable --test-tags=/sms_collector/test_sms_message --stop-after-init

# Run all module tests
odoo -d test_db --test-enable --test-tags=/sms_collector --stop-after-init

# Run with coverage
coverage run --source=sms_collector $(which odoo) -d test_db --init=sms_collector --stop-after-init --test-enable --test-tags=/sms_collector
coverage report -m
```

## Test Data

Tests use realistic SMS data:
- Phone numbers in international format
- Epoch timestamps (milliseconds) as received from mobile apps
- Various message types (OTP, banking, general)
- Different partner scenarios

## Mocking

Tests use appropriate mocking for:
- MinIO storage operations (avoid actual S3 calls)
- External service dependencies
- Heavy operations during testing

## Coverage Areas

The tests cover:
- ✅ Model creation and validation
- ✅ Duplicate prevention logic
- ✅ Partner association algorithms
- ✅ Filter rule matching and actions
- ✅ API endpoint authentication
- ✅ Error handling and edge cases
- ✅ Data transformation and sanitization

## Adding New Tests

When adding new functionality:
1. Create test methods in the appropriate test file
2. Follow Odoo naming conventions (`test_*`)
3. Use TransactionCase for model tests, HttpCase for API tests
4. Mock external dependencies
5. Test both success and failure scenarios
6. Add docstrings explaining test purpose
