=======================
SMS Collector API Guide
=======================

.. contents:: Table of Contents
   :local:

Authentication
==============

The SMS Collector API uses Bearer token authentication with Odoo API keys.

Obtaining an API Key
--------------------

1. Log in to Odoo with administrator privileges
2. Navigate to Settings → Users & Companies → Users
3. Select the user who will upload SMS messages
4. Go to the "API Keys" tab
5. Click "New API Key"
6. Set scope to "RPC"
7. Save the generated key securely

Using the API Key
-----------------

Include the API key in the Authorization header::

    Authorization: Bearer YOUR_API_KEY_HERE

API Endpoints
=============

Upload SMS Message
------------------

Uploads a single SMS message to the system.

**Endpoint**: ``POST /sms/upload``

**Headers**::

    Content-Type: application/json
    Authorization: Bearer YOUR_API_KEY

**Request Schema**::

    {
        "_id": integer,          // Required: Internal message ID from phone
        "thread_id": integer,    // Required: Thread/conversation ID
        "address": string,       // Required: Phone number (sender/recipient)
        "date": integer,         // Required: Received timestamp (epoch milliseconds)
        "date_sent": integer,    // Required: Sent timestamp (epoch milliseconds)
        "body": string,          // Required: Message content
        "service_center": string // Required: SMS service center number
    }

**Field Validations**:

* ``_id``: Must be a positive integer
* ``thread_id``: Must be a positive integer
* ``address``: Non-empty string, valid phone number or short code
* ``date``: Positive integer (epoch milliseconds)
* ``date_sent``: Positive integer (epoch milliseconds)
* ``body``: String, max 160,000 characters
* ``service_center``: String (can be empty)

**Success Response**::

    HTTP/1.1 200 OK
    Content-Type: application/json

    {
        "success": "true",
        "message_id": 123
    }

**Error Responses**::

    // Missing Authorization
    HTTP/1.1 401 Unauthorized
    {
        "error": "No Authorization header provided"
    }

    // Invalid API Key
    HTTP/1.1 401 Unauthorized
    {
        "error": "Invalid API key"
    }

    // Missing Required Fields
    HTTP/1.1 400 Bad Request
    {
        "error": "Missing required fields: _id, body"
    }

    // Invalid Field Type
    HTTP/1.1 400 Bad Request
    {
        "error": "_id must be an integer"
    }

    // Duplicate Message (not an error)
    HTTP/1.1 200 OK
    {
        "success": "true",
        "message": "Duplicate message, skipped"
    }

Examples
========

Python Example
--------------

.. code-block:: python

    import requests
    import json
    from datetime import datetime

    # Configuration
    API_KEY = "your_api_key_here"
    ODOO_URL = "https://your-odoo-instance.com"

    # SMS data
    sms_data = {
        "_id": 12345,
        "thread_id": 1,
        "address": "+1234567890",
        "date": int(datetime.now().timestamp() * 1000),
        "date_sent": int(datetime.now().timestamp() * 1000),
        "body": "Hello, this is a test SMS",
        "service_center": "+1234567890"
    }

    # Send request
    response = requests.post(
        f"{ODOO_URL}/sms/upload",
        json=sms_data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
    )

    # Check response
    if response.status_code == 200:
        result = response.json()
        print(f"SMS uploaded successfully. ID: {result.get('message_id')}")
    else:
        print(f"Error: {response.json()}")

cURL Example
------------

.. code-block:: bash

    curl -X POST https://your-odoo-instance.com/sms/upload \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "_id": 12345,
        "thread_id": 1,
        "address": "+1234567890",
        "date": 1704067200000,
        "date_sent": 1704067100000,
        "body": "Test SMS message",
        "service_center": "+1234567890"
      }'

JavaScript Example
------------------

.. code-block:: javascript

    const uploadSMS = async (smsData, apiKey) => {
        const response = await fetch('https://your-odoo-instance.com/sms/upload', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(smsData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    };

    // Usage
    const sms = {
        _id: 12345,
        thread_id: 1,
        address: "+1234567890",
        date: Date.now(),
        date_sent: Date.now() - 1000,
        body: "Test message",
        service_center: "+1234567890"
    };

    uploadSMS(sms, 'YOUR_API_KEY')
        .then(result => console.log('SMS uploaded:', result))
        .catch(error => console.error('Error:', error));

Best Practices
==============

1. **Batch Processing**: For multiple messages, send them individually but in quick succession
2. **Error Handling**: Implement retry logic for network failures
3. **Duplicate Prevention**: The API automatically prevents duplicates based on message hash
4. **Rate Limiting**: Implement client-side rate limiting to avoid overwhelming the server
5. **Timestamp Accuracy**: Ensure timestamps are in milliseconds, not seconds
6. **Phone Number Format**: Use E.164 format when possible (e.g., +1234567890)

Troubleshooting
===============

Common Issues
-------------

**401 Unauthorized**
  * Verify API key is correct
  * Check if API key has "RPC" scope
  * Ensure Bearer prefix is included

**400 Bad Request**
  * Check all required fields are present
  * Verify field types match schema
  * Ensure timestamps are in milliseconds

**500 Internal Server Error**
  * Check Odoo logs for detailed error
  * Verify database connectivity
  * Check MinIO configuration if enabled

**Duplicate Messages**
  The API returns 200 OK for duplicates to ensure idempotency. Check the response message to identify duplicates.