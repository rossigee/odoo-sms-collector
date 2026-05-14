from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sms_collector_minio_endpoint = fields.Char(
        string="Minio Endpoint", config_parameter="sms_collector.minio_endpoint"
    )
    sms_collector_minio_secure = fields.Boolean(
        string="Minio uses TLS", config_parameter="sms_collector.minio_secure"
    )
    sms_collector_minio_access_key = fields.Char(
        string="Minio Access Key", config_parameter="sms_collector.minio_access_key"
    )
    sms_collector_minio_secret_key = fields.Char(
        string="Minio Secret Key", config_parameter="sms_collector.minio_secret_key"
    )
    sms_collector_bucket_name = fields.Char(
        string="Bucket Name", config_parameter="sms_collector.bucket_name"
    )
