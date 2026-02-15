#!/bin/bash
# Show which configuration will be used

echo "========================================="
echo "Active Configuration Check"
echo "========================================="
echo ""

# Check if DATABASE_URL is set (from .env)
if grep -q "^DATABASE_URL=" .env 2>/dev/null; then
    echo "✅ DATABASE_URL configured in .env"
    echo "📦 Will use: CLOUD SETTINGS (PostgreSQL)"
    echo ""
    python -m dotenv run python test_cloud_config.py 2>/dev/null | grep -A 20 "CURRENT CLOUD SETTINGS"
else
    echo "❌ DATABASE_URL not in .env"
    echo "📄 Will use: LOCAL YAML (SQLite)"
fi
