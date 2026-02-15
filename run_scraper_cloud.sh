#!/bin/bash
# Run scraper with cloud database settings

echo "========================================="
echo "Running Scraper with Cloud Settings"
echo "========================================="
echo ""

# Load .env and run scraper
python -m dotenv run python main.py "$@"
