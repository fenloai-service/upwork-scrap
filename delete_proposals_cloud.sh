#!/bin/bash
# Delete proposals from cloud database

echo "Deleting proposals from CLOUD database (PostgreSQL)..."
python -m dotenv run python delete_proposals.py
