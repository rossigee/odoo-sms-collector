=============
SMS Collector
=============

.. contents:: Table of Contents
   :local:

Overview
========

SMS Collector is an Odoo 16 module that provides an HTTP POST endpoint for mobile phones to upload SMS messages. The module features:

* RESTful API endpoint for SMS upload
* Bearer token authentication via Odoo API keys
* Dual storage system (PostgreSQL + MinIO/S3)
* Configurable SMS filtering and processing rules
* Automatic partner association based on phone numbers
* Duplicate message prevention using SHA256 hashing

Configuration
=============

MinIO/S3 Storage
----------------

To enable object storage for SMS archival:

1. Navigate to Settings → Technical → System Parameters
2. Configure the following parameters:

   * ``sms_collector.minio_endpoint``: MinIO server endpoint (e.g., ``minio.example.com:9000``)
   * ``sms_collector.minio_secure``: Use HTTPS (True/False)
   * ``sms_collector.minio_access_key``: MinIO access key
   * ``sms_collector.minio_secret_key``: MinIO secret key
   * ``sms_collector.bucket_name``: Bucket name for SMS storage

API Authentication
------------------

Users need an API key to upload SMS messages:

1. Go to Settings → Users & Companies → Users
2. Select a user and go to the "API Keys" tab
3. Create a new API key with scope "RPC"
4. Use this key as a Bearer token in API requests

Usage
=====

API Endpoint
------------

**URL**: ``/sms/upload``

**Method**: ``POST``

**Headers**:
  * ``Content-Type: application/json``
  * ``Authorization: Bearer YOUR_API_KEY``

**Request Body**::

    {
        "_id": 12345,
        "thread_id": 67890,
        "address": "+1234567890",
        "date": 1704067200000,
        "date_sent": 1704067100000,
        "body": "SMS message content",
        "service_center": "+1234567890"
    }

**Response**::

    {
        "success": "true",
        "message_id": 123
    }

SMS Filter Rules
----------------

Create rules to automatically process incoming SMS messages:

1. Navigate to SMS Collector → Filter Rules
2. Create a new rule with:

   * **Name**: Rule description
   * **Pattern**: Regular expression to match
   * **Action**: What to do when matched (e.g., forward to channel, post to chatter)
   * **Priority**: Order of rule execution
   * **Stop Processing**: Whether to stop checking other rules after match

Partner Association
-------------------

SMS messages are automatically linked to partners when phone numbers match. The system searches in both ``phone`` and ``mobile`` fields of partners.

Known Issues and Limitations
============================

* API keys are stored in plain text (this is standard Odoo behavior - ensure HTTPS is used in production)
* MinIO connection failures are logged but don't prevent SMS storage in PostgreSQL
* No rate limiting on the API endpoint
* Maximum SMS body length is 160,000 characters

Security Considerations
=======================

1. **API Authentication**: Always use HTTPS in production to protect API keys (Odoo stores API keys in plain text)
2. **Access Control**: Only users with proper permissions can view SMS messages
3. **Data Privacy**: Consider encryption for sensitive SMS content
4. **Rate Limiting**: Implement rate limiting at the reverse proxy level
5. **API Key Management**: Regularly rotate API keys and limit their scope to necessary permissions only

Migration Notes
===============

Version 16.0.2.0.2
------------------

* Added SHA256 hash-based duplicate prevention
* Migration scripts in ``migrations/16.0.2.0.2/`` can be removed in version 16.0.3.0.0

Development
===========

Running Tests
-------------

Using Docker::

    docker-compose up -d postgres
    docker-compose run odoo-test bash /usr/local/bin/run-tests.sh

Local installation::

    pip install minio
    ./run-tests.sh

Contributing
------------

1. Follow OCA coding standards
2. Add tests for new features
3. Update documentation as needed
4. Ensure all existing tests pass

License
=======

This module is licensed under AGPL-3.0 or later.

Credits
=======

Authors
-------

* Ross Golder <ross@golder.org>

Maintainers
-----------

This module is maintained by Ross Golder.