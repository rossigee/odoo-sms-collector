# -*- coding: utf-8 -*-
"""
Pre-migration script for SMS Collector module version 16.0.2.0.2

This migration:
1. Adds the message_hash column if it doesn't exist
2. Calculates SHA256 hashes for all existing SMS messages
3. Identifies and removes duplicate messages (keeping the one with the lowest ID)
4. Prepares the data for the unique constraint that will be added

TO BE REMOVED: This migration can be removed in version 16.0.3.0.0 or later
"""

import hashlib
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migration script to handle duplicate SMS messages before applying unique constraint
    """
    if not version:
        return

    _logger.info("Starting SMS Collector pre-migration for duplicate removal...")

    # Step 1: Add message_hash column if it doesn't exist
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='sms_message' AND column_name='message_hash'
    """
    )

    if not cr.fetchone():
        _logger.info("Adding message_hash column to sms_message table...")
        cr.execute(
            """
            ALTER TABLE sms_message
            ADD COLUMN message_hash VARCHAR(64)
        """
        )
        cr.execute(
            """
            CREATE INDEX idx_sms_message_hash
            ON sms_message(message_hash)
        """
        )

    # Step 2: Calculate hashes for existing messages
    _logger.info("Calculating SHA256 hashes for existing SMS messages...")

    cr.execute(
        """
        SELECT id, address, date_sent, body, thread_id
        FROM sms_message
        WHERE message_hash IS NULL
        ORDER BY id
    """
    )

    messages = cr.fetchall()
    hash_to_ids = {}
    update_data = []

    for msg_id, address, date_sent, body, thread_id in messages:
        # Calculate hash using the same logic as in the model
        hash_data = {
            "address": address or "",
            "date_sent": str(date_sent) if date_sent else "",
            "body": body or "",
            "thread_id": thread_id or 0,
        }
        hash_string = json.dumps(hash_data, sort_keys=True)
        message_hash = hashlib.sha256(hash_string.encode("utf-8")).hexdigest()

        # Track duplicates
        if message_hash in hash_to_ids:
            hash_to_ids[message_hash].append(msg_id)
        else:
            hash_to_ids[message_hash] = [msg_id]

        update_data.append((message_hash, msg_id))

    # Step 3: Update all messages with their hashes
    if update_data:
        _logger.info(f"Updating {len(update_data)} messages with calculated hashes...")
        cr.executemany(
            """
            UPDATE sms_message
            SET message_hash = %s
            WHERE id = %s
        """,
            update_data,
        )

    # Step 4: Remove duplicates (keep the one with lowest ID)
    duplicate_count = 0
    ids_to_delete = []

    for message_hash, ids in hash_to_ids.items():
        if len(ids) > 1:
            # Keep the first (lowest ID), delete the rest
            ids_to_keep = ids[0]
            ids_to_remove = ids[1:]
            ids_to_delete.extend(ids_to_remove)
            duplicate_count += len(ids_to_remove)

            _logger.info(
                f"Found {len(ids)} messages with hash {message_hash}. "
                f"Keeping ID {ids_to_keep}, removing IDs: {ids_to_remove}"
            )

    # Step 5: Delete duplicate messages
    if ids_to_delete:
        _logger.warning(f"Removing {duplicate_count} duplicate SMS messages...")

        # Delete in batches to avoid issues with large datasets
        batch_size = 1000
        for i in range(0, len(ids_to_delete), batch_size):
            batch = ids_to_delete[i : i + batch_size]
            cr.execute(
                """
                DELETE FROM sms_message
                WHERE id IN %s
            """,
                (tuple(batch),),
            )

        _logger.info(f"Successfully removed {duplicate_count} duplicate messages")
    else:
        _logger.info("No duplicate messages found")

    # Step 6: Verify data integrity
    cr.execute(
        """
        SELECT COUNT(*) as total,
               COUNT(DISTINCT message_hash) as unique_hashes,
               COUNT(*) - COUNT(DISTINCT message_hash) as remaining_duplicates
        FROM sms_message
        WHERE message_hash IS NOT NULL
    """
    )

    result = cr.fetchone()
    _logger.info(
        f"Migration complete. Total messages: {result[0]}, "
        f"Unique hashes: {result[1]}, "
        f"Remaining duplicates: {result[2]}"
    )

    if result[2] > 0:
        _logger.error(
            "WARNING: Some duplicates remain. The unique constraint may fail!"
        )

    _logger.info("SMS Collector pre-migration completed successfully")
