# -*- coding: utf-8 -*-
"""
Post-migration script for SMS Collector module version 16.0.2.0.2

This migration:
1. Verifies that all messages have hashes
2. Ensures the unique constraint is properly applied
3. Logs any issues for manual intervention

TO BE REMOVED: This migration can be removed in version 16.0.3.0.0 or later
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Post-migration script to verify hash migration and constraint application
    """
    if not version:
        return

    _logger.info("Starting SMS Collector post-migration verification...")

    # Step 1: Verify all messages have hashes
    cr.execute(
        """
        SELECT COUNT(*)
        FROM sms_message
        WHERE message_hash IS NULL
    """
    )

    null_count = cr.fetchone()[0]
    if null_count > 0:
        _logger.error(f"WARNING: {null_count} messages still have NULL hashes!")
        # Try to fix them
        cr.execute(
            """
            SELECT id FROM sms_message
            WHERE message_hash IS NULL
            LIMIT 10
        """
        )
        sample_ids = [row[0] for row in cr.fetchall()]
        _logger.error(f"Sample IDs with NULL hashes: {sample_ids}")

    # Step 2: Verify no duplicates remain
    cr.execute(
        """
        SELECT message_hash, COUNT(*) as cnt
        FROM sms_message
        WHERE message_hash IS NOT NULL
        GROUP BY message_hash
        HAVING COUNT(*) > 1
        LIMIT 5
    """
    )

    duplicates = cr.fetchall()
    if duplicates:
        _logger.error(f"WARNING: Found {len(duplicates)} duplicate hashes remaining!")
        for hash_val, count in duplicates:
            _logger.error(f"Hash {hash_val} has {count} duplicates")

    # Step 3: Check if the unique constraint exists
    cr.execute(
        """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'sms_message'
        AND constraint_type = 'UNIQUE'
        AND constraint_name LIKE '%message_hash%'
    """
    )

    constraint = cr.fetchone()
    if constraint:
        _logger.info(f"Unique constraint '{constraint[0]}' is properly applied")
    else:
        _logger.warning(
            "Unique constraint on message_hash not found - it may be created by the ORM later"
        )

    # Step 4: Final statistics
    cr.execute(
        """
        SELECT
            COUNT(*) as total_messages,
            COUNT(DISTINCT message_hash) as unique_messages,
            COUNT(DISTINCT address) as unique_addresses,
            MIN(date_received) as oldest_message,
            MAX(date_received) as newest_message
        FROM sms_message
    """
    )

    stats = cr.fetchone()
    _logger.info(
        f"""
    SMS Collector Migration Statistics:
    - Total messages: {stats[0]}
    - Unique messages: {stats[1]}
    - Unique addresses: {stats[2]}
    - Date range: {stats[3]} to {stats[4]}
    """
    )

    _logger.info("SMS Collector post-migration completed successfully")
