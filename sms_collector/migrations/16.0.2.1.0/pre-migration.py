# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Rename config parameter key: sms_collector.minio_bucket_name → sms_collector.bucket_name"""
    if not version:
        return

    cr.execute(
        """
        UPDATE ir_config_parameter
        SET key = 'sms_collector.bucket_name'
        WHERE key = 'sms_collector.minio_bucket_name'
        """,
    )
    if cr.rowcount:
        _logger.info(
            "Renamed ir.config_parameter key sms_collector.minio_bucket_name "
            "→ sms_collector.bucket_name"
        )
