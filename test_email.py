#!/usr/bin/env python3
"""Test Gmail email sending."""
import sys
sys.path.insert(0, '/Users/mohammadshoaib/Codes/upwork-scrap')

from dotenv import load_dotenv
load_dotenv()

import os

# Check if password is set
gmail_password = os.getenv('GMAIL_APP_PASSWORD')
print(f"📧 Testing Gmail Email Setup\n{'='*60}")
print(f"✅ GMAIL_APP_PASSWORD: {'Set' if gmail_password else 'Not set'}")

if gmail_password:
    print(f"   Password: {gmail_password[:4]}...{gmail_password[-4:]}")
    print(f"\n✅ Gmail is configured!")
    print(f"\nNext: Update config/email_config.yaml with your email address")
else:
    print("\n❌ GMAIL_APP_PASSWORD not set in .env")
