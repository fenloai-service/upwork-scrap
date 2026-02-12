# Resend Email Setup (5 Minutes)

## Step 1: Get Free Resend Account
1. Go to: https://resend.com/signup
2. Sign up (free - 3,000 emails/month)
3. Verify your email

## Step 2: Get API Key
1. Go to: https://resend.com/api-keys
2. Click "Create API Key"
3. Copy the key (starts with `re_...`)

## Step 3: Update .env
Add these lines to your .env file:

```bash
# Resend Email (instead of Gmail)
RESEND_API_KEY=re_your_api_key_here
RESEND_FROM_EMAIL=onboarding@resend.dev
RESEND_TO_EMAIL=your-email@gmail.com
```

## Step 4: Install Package
```bash
source .venv/bin/activate
pip install resend
```

## Step 5: Update main.py (Simple)
In main.py, change the email import from:
```python
from notifier import send_notification
```

To:
```python
from notifier_resend import send_notification_resend as send_notification
```

Done! Much simpler than Gmail SMTP.
