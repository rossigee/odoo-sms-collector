#!/bin/bash
set -e

# Export PostgreSQL environment variables
export PGHOST=postgres
export PGPORT=5432
export PGUSER=odoo
export PGPASSWORD=odoo

# Install additional dependencies
pip install minio coverage

# Initialize database
odoo -d test_db --init=base --stop-after-init

# Install module and run tests
odoo -d test_db --init=sms_collector --stop-after-init --test-enable --test-tags=/sms_collector --log-level=info

# Alternative: run tests with coverage
# coverage run --source=sms_collector $(which odoo) -d test_db --init=sms_collector --stop-after-init --test-enable --test-tags=/sms_collector --log-level=info
# coverage report -m

echo "Tests completed successfully!"
