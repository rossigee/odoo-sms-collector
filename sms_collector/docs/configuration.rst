============================
SMS Collector Configuration
============================

.. contents:: Table of Contents
   :local:

Initial Setup
=============

Installation
------------

1. Copy the module to your Odoo addons directory::

    cp -r sms_collector /path/to/odoo/addons/

2. Update the module list:

   * Go to Apps → Update Apps List
   * Search for "SMS Collector"
   * Click Install

3. Install required Python dependencies::

    pip install minio

Dependencies
------------

The module requires:

* Odoo 16.0
* Python packages: ``minio``
* Odoo modules: ``base``, ``account``, ``mail``

User Configuration
==================

Creating API Users
------------------

It's recommended to create dedicated users for SMS upload:

1. Go to Settings → Users & Companies → Users
2. Click "Create"
3. Set user details:

   * Name: "SMS Upload User"
   * Email: sms-upload@example.com
   * Access Rights: User (minimum required)

4. Save and create API key:

   * Go to "API Keys" tab
   * Click "New API Key"
   * Description: "SMS Upload"
   * Scope: "RPC"
   * Save the generated key

User Permissions
----------------

Minimum permissions required:

* Read/Write/Create on SMS Messages
* Read on SMS Filter Rules
* Read on Partners (for association)

Storage Configuration
=====================

PostgreSQL Storage
------------------

SMS messages are always stored in PostgreSQL. No additional configuration required.

MinIO/S3 Storage (Optional)
---------------------------

For archival storage, configure MinIO:

1. Go to Settings → Technical → System Parameters
2. Create/update the following parameters:

.. list-table:: MinIO Configuration Parameters
   :header-rows: 1

   * - Parameter
     - Description
     - Example
   * - sms_collector.minio_endpoint
     - MinIO server endpoint
     - minio.example.com:9000
   * - sms_collector.minio_secure
     - Use HTTPS
     - True
   * - sms_collector.minio_access_key
     - Access key
     - minioadmin
   * - sms_collector.minio_secret_key
     - Secret key
     - minioadmin123
   * - sms_collector.minio_bucket_name
     - Bucket for SMS storage
     - sms-archive

3. Create the bucket in MinIO::

    mc mb myminio/sms-archive

SMS Filter Rules
================

Creating Filter Rules
---------------------

1. Navigate to SMS Collector → Filter Rules
2. Click "Create"
3. Configure the rule:

**Basic Settings**:

* **Name**: Descriptive name
* **Active**: Enable/disable rule
* **Sequence**: Order of execution (lower = higher priority)
* **Stop Processing**: Stop checking other rules after match

**Pattern Matching**:

* **Pattern**: Regular expression
* **Pattern Type**: What to match against

  * ``body``: Message content
  * ``address``: Phone number
  * ``combined``: Both body and address

**Actions**:

* **Action Type**:

  * ``otp_forward``: Forward OTP to channel
  * ``partner_chatter``: Post to partner's chatter
  * ``transaction``: Parse transaction details
  * ``custom``: Custom processing

Example Rules
-------------

**OTP Detection**::

    Name: OTP Messages
    Pattern: \b\d{4,8}\b.*\b(OTP|code|PIN)\b
    Pattern Type: body
    Action Type: otp_forward
    OTP Channel: general
    Stop Processing: True

**Bank Transaction**::

    Name: Bank Transactions
    Pattern: (received|sent|debited|credited).*\$?[\d,]+\.?\d*
    Pattern Type: body
    Action Type: transaction
    Transaction Pattern: \$?([\d,]+\.?\d*)
    Partner Field: name

**Partner Messages**::

    Name: Partner SMS
    Pattern: .*
    Pattern Type: address
    Action Type: partner_chatter
    Stop Processing: False

System Settings
===============

Via Odoo Interface
------------------

Go to Settings → General Settings → SMS Collector:

* **MinIO Endpoint**: Your MinIO server
* **MinIO Secure**: Enable HTTPS
* **MinIO Access Key**: Access credentials
* **MinIO Secret Key**: Secret credentials
* **MinIO Bucket**: Storage bucket

Via Configuration File
----------------------

Add to your Odoo configuration file::

    [options]
    # SMS Collector settings
    sms_collector_minio_endpoint = minio.example.com:9000
    sms_collector_minio_secure = True
    sms_collector_minio_bucket_name = sms-archive

Security Configuration
======================

HTTPS Setup
-----------

Always use HTTPS in production:

1. Configure your reverse proxy (nginx/Apache)
2. Enable SSL/TLS certificates
3. Redirect HTTP to HTTPS

Rate Limiting
-------------

Implement at reverse proxy level::

    # nginx example
    limit_req_zone $binary_remote_addr zone=sms_upload:10m rate=10r/s;
    
    location /sms/upload {
        limit_req zone=sms_upload burst=20 nodelay;
        proxy_pass http://odoo;
    }

IP Whitelisting
---------------

Restrict access to known SMS gateways::

    # nginx example
    location /sms/upload {
        allow 192.168.1.0/24;
        allow 10.0.0.0/8;
        deny all;
        proxy_pass http://odoo;
    }

Monitoring
==========

Logging
-------

SMS uploads are logged to Odoo logs. Monitor for:

* Failed authentications
* Validation errors
* MinIO connection failures
* Duplicate messages

Log Parsing
-----------

Example Fluentbit configuration::

    [FILTER]
        Name    grep
        Match   *
        Regex   message SMS.*upload

Performance Tuning
==================

Database Indexes
----------------

The module creates indexes on:

* ``message_hash`` (unique constraint)
* ``address`` (for partner matching)
* ``date_received`` (for queries)

Regular Maintenance
-------------------

1. Archive old messages to MinIO
2. Clean up duplicate detection hashes
3. Monitor database growth
4. Review and optimize filter rules

Troubleshooting
===============

Common Issues
-------------

**MinIO Connection Failed**
  * Check endpoint URL and port
  * Verify credentials
  * Test network connectivity
  * Check bucket exists

**API Authentication Failed**
  * Verify API key is active
  * Check user has permissions
  * Ensure Bearer format is correct

**Messages Not Associated with Partners**
  * Check phone number format
  * Verify partner has phone/mobile set
  * Review phone number cleaning logic

**Filter Rules Not Working**
  * Check rule is active
  * Verify regex pattern
  * Check sequence/priority
  * Enable debug logging