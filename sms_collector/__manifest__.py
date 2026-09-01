{
    "name": "SMS Collector",
    "version": "17.0.2.1.0",
    "author": "Ross Golder",
    "website": "https://golder.org/",
    "license": "AGPL-3",
    "category": "Tools",
    "summary": "SMS message collection and archival with MinIO object storage.",
    "description": "Collect and archive SMS messages with MinIO-based object storage integration. Provides HTTP API endpoints for secure SMS ingestion with duplicate prevention and automated processing.",
    "depends": ["base", "mail"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
}
