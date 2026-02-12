#!/usr/bin/env python3
"""Test email sending with real Gmail credentials."""
import sys
sys.path.insert(0, '/Users/mohammadshoaib/Codes/upwork-scrap')

from dotenv import load_dotenv
load_dotenv()

from notifier import send_notification

print("📧 Testing Email Notification\n" + "="*60)

# Create test data
test_proposals = [
    {
        'job_uid': '1234567890',
        'title': 'AI Chatbot Development for E-commerce',
        'match_score': 85.5,
        'status': 'pending_review',
        'proposal_text': 'This is a test proposal to verify email functionality...'
    },
    {
        'job_uid': '0987654321', 
        'title': 'Machine Learning Model for Data Analysis',
        'match_score': 72.3,
        'status': 'pending_review',
        'proposal_text': 'Another test proposal for the email notification system...'
    }
]

test_stats = {
    'jobs_matched': 15,
    'proposals_generated': 2,
    'proposals_failed': 0,
    'timestamp': '2026-02-11 23:00:00'
}

print("Sending test email to: shoaib6174@gmail.com")
print("Content: 2 test proposals\n")

try:
    result = send_notification(test_proposals, test_stats, dry_run=False)
    
    if result:
        print("✅ SUCCESS! Email sent successfully!")
        print("\nCheck your inbox at: shoaib6174@gmail.com")
        print("(Check spam folder if you don't see it)")
    else:
        print("❌ Email failed to send. Check the error above.")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
