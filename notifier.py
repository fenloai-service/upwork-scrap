"""Email notification system for Upwork proposal monitoring.

Sends HTML email notifications via Gmail SMTP with proposal summaries.
Falls back to saving emails as HTML files if SMTP fails.

Usage:
    from notifier import send_notification

    send_notification(
        proposals=[...],
        monitor_stats={'jobs_matched': 10, 'proposals_generated': 5},
        dry_run=False
    )
"""

import json
import os
import smtplib
import yaml
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict, Optional

import config


def load_email_config() -> dict:
    """Load email configuration — tries DB first, falls back to YAML."""
    # Try database first
    try:
        from database.db import load_config_from_db
        db_data = load_config_from_db("email_config")
        if db_data is not None:
            return db_data.get('email', db_data)
    except Exception:
        pass

    # Fall back to YAML file
    config_path = config.CONFIG_DIR / "email_config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Email config not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return data.get('email', {})


def generate_proposal_html(proposals: List[Dict], monitor_stats: Dict) -> str:
    """Generate HTML email body with proposal summaries.

    Args:
        proposals: List of proposal dicts from database
        monitor_stats: Dict with keys: jobs_matched, proposals_generated, etc.

    Returns:
        HTML string for email body
    """
    jobs_matched = monitor_stats.get('jobs_matched', 0)
    proposals_generated = monitor_stats.get('proposals_generated', 0)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Limit proposals shown in email
    email_cfg = load_email_config()
    max_proposals = email_cfg.get('notifications', {}).get('max_proposals_per_email', 10)
    shown_proposals = proposals[:max_proposals]
    remaining = len(proposals) - len(shown_proposals)

    # Build proposal cards HTML
    proposal_cards = ""
    for prop in shown_proposals:
        job_uid = prop.get('job_uid', 'unknown')
        match_score = prop.get('match_score', 0)
        proposal_text = prop.get('proposal_text', '')

        # Get job details (would need to query DB, simplified here)
        job_title = f"Job {job_uid[:8]}"  # Simplified
        job_url = f"https://www.upwork.com/jobs/{job_uid}"

        # Truncate proposal for email
        proposal_preview = proposal_text[:300] + "..." if len(proposal_text) > 300 else proposal_text

        # Score color
        score_color = "#14a800" if match_score >= 70 else ("#f57c00" if match_score >= 40 else "#9e9e9e")

        proposal_cards += f"""
        <div style="border-left: 4px solid {score_color}; padding: 16px; margin-bottom: 20px;
                    background: #f8f9fa; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin: 0; font-size: 18px;">
                    <a href="{job_url}" style="color: #1976d2; text-decoration: none;">{job_title}</a>
                </h3>
                <div style="font-size: 24px; font-weight: bold; color: {score_color};">
                    🎯 {match_score:.0f}
                </div>
            </div>
            <div style="background: white; padding: 12px; border-radius: 6px; font-family: system-ui;
                        white-space: pre-wrap; font-size: 14px; color: #333;">
                {proposal_preview}
            </div>
            <div style="margin-top: 8px; font-size: 12px; color: #666;">
                💡 <a href="http://localhost:8501" style="color: #1976d2;">Open Dashboard to review and submit</a>
            </div>
        </div>
        """

    if remaining > 0:
        proposal_cards += f"""
        <div style="padding: 16px; background: #e3f2fd; border-radius: 8px; text-align: center;">
            <strong>+ {remaining} more proposal(s)</strong>
            <br>
            <a href="http://localhost:8501" style="color: #1976d2;">View all in Dashboard →</a>
        </div>
        """

    # Full HTML email
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                 background: #f5f5f5; margin: 0; padding: 20px;">
        <div style="max-width: 700px; margin: 0 auto; background: white; border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden;">

            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1976d2 0%, #14a800 100%);
                        padding: 30px; color: white; text-align: center;">
                <h1 style="margin: 0; font-size: 28px;">🎯 New Upwork Proposals Ready!</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.95; font-size: 14px;">
                    Monitor run completed at {timestamp}
                </p>
            </div>

            <!-- Stats -->
            <div style="padding: 20px; background: #fafafa; border-bottom: 1px solid #eee;">
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                    <div style="text-align: center; padding: 15px; background: white; border-radius: 8px;">
                        <div style="font-size: 32px; font-weight: bold; color: #1976d2;">
                            {jobs_matched}
                        </div>
                        <div style="color: #666; font-size: 14px; margin-top: 5px;">
                            Jobs Matched
                        </div>
                    </div>
                    <div style="text-align: center; padding: 15px; background: white; border-radius: 8px;">
                        <div style="font-size: 32px; font-weight: bold; color: #14a800;">
                            {proposals_generated}
                        </div>
                        <div style="color: #666; font-size: 14px; margin-top: 5px;">
                            Proposals Generated
                        </div>
                    </div>
                </div>
            </div>

            <!-- Proposals -->
            <div style="padding: 20px;">
                <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #333;">
                    📝 Generated Proposals
                </h2>
                {proposal_cards}
            </div>

            <!-- Footer -->
            <div style="padding: 20px; background: #fafafa; text-align: center; border-top: 1px solid #eee;">
                <p style="margin: 0; color: #666; font-size: 13px;">
                    Generated by <strong>Upwork Proposal Monitor</strong>
                    <br>
                    <a href="http://localhost:8501" style="color: #1976d2; text-decoration: none;">
                        Open Dashboard →
                    </a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return html


def send_via_smtp(subject: str, html_body: str, email_cfg: dict) -> bool:
    """Send email via Gmail SMTP.

    Args:
        subject: Email subject line
        html_body: HTML email body
        email_cfg: Email configuration dict from email_config.yaml

    Returns:
        True if sent successfully, False otherwise
    """
    smtp_cfg = email_cfg.get('smtp', {})
    notifications_cfg = email_cfg.get('notifications', {})

    # Get credentials
    smtp_host = smtp_cfg.get('host', 'smtp.gmail.com')
    smtp_port = smtp_cfg.get('port', 587)
    smtp_username = smtp_cfg.get('username')
    smtp_password = os.getenv('GMAIL_APP_PASSWORD')

    recipient = notifications_cfg.get('recipient')

    # Validate
    if not smtp_username or not recipient:
        print("❌ SMTP username or recipient not configured in config/email_config.yaml")
        return False

    if not smtp_password:
        print("⚠️  GMAIL_APP_PASSWORD env var not set. Set it to enable email sending.")
        print("   Generate app password at: https://myaccount.google.com/apppasswords")
        return False

    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_username
        msg['To'] = recipient

        # Attach HTML body
        msg.attach(MIMEText(html_body, 'html'))

        # Send via SMTP
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)

        print(f"✅ Email sent successfully to {recipient}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("❌ SMTP authentication failed. Check GMAIL_APP_PASSWORD env var.")
        return False
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def save_email_fallback(subject: str, html_body: str, proposals: List[Dict], monitor_stats: Dict) -> str:
    """Save email as HTML file if SMTP fails (fallback).

    Args:
        subject: Email subject
        html_body: HTML email body
        proposals: Proposal list
        monitor_stats: Monitor statistics

    Returns:
        Path to saved HTML file
    """
    # Create emails directory
    emails_dir = config.DATA_DIR / "emails"
    emails_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_file = emails_dir / f"proposal_notification_{timestamp}.html"
    status_file = emails_dir / f"proposal_notification_{timestamp}_status.json"

    # Save HTML email
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_body)

    # Save status JSON
    status_data = {
        'timestamp': datetime.now().isoformat(),
        'subject': subject,
        'proposals_count': len(proposals),
        'monitor_stats': monitor_stats,
        'delivery_status': 'fallback_file_saved',
        'html_file': str(html_file),
        'reason': 'SMTP unavailable or failed'
    }

    with open(status_file, 'w', encoding='utf-8') as f:
        json.dump(status_data, f, indent=2)

    print(f"📧 Email saved to file (SMTP unavailable): {html_file}")
    print(f"📄 Status JSON saved: {status_file}")

    return str(html_file)


def send_notification(
    proposals: List[Dict],
    monitor_stats: Dict,
    dry_run: bool = False
) -> bool:
    """Send email notification with proposal summary.

    Args:
        proposals: List of proposals to include in notification
        monitor_stats: Dict with monitor run statistics
        dry_run: If True, skip actual sending (testing mode)

    Returns:
        True if notification sent/saved successfully
    """
    if dry_run:
        print("🔇 DRY RUN - Email notification skipped")
        return True

    try:
        email_cfg = load_email_config()
    except FileNotFoundError as e:
        print(f"❌ Email config error: {e}")
        return False

    # Check if email is enabled
    if not email_cfg.get('enabled', False):
        print("📧 Email notifications disabled in config/email_config.yaml")
        return True  # Not an error, just disabled

    # Check minimum proposals threshold
    min_proposals = email_cfg.get('notifications', {}).get('min_proposals_to_send', 1)
    if len(proposals) < min_proposals:
        print(f"📧 Not sending email: {len(proposals)} proposals < minimum {min_proposals}")
        return True

    # Generate email content
    subject = f"🎯 {len(proposals)} New Upwork Proposal(s) Ready for Review"
    html_body = generate_proposal_html(proposals, monitor_stats)

    # Try SMTP first
    smtp_success = send_via_smtp(subject, html_body, email_cfg)

    # Fallback to file save if SMTP fails
    if not smtp_success:
        save_email_fallback(subject, html_body, proposals, monitor_stats)
        print("⚠️  Email sent via fallback (saved to file)")
        return True  # Fallback succeeded

    return True


if __name__ == "__main__":
    # Test the notifier with sample data
    print("Testing email notifier...")

    sample_proposals = [
        {
            'job_uid': '~test001',
            'proposal_text': 'Sample proposal text for testing the email notification system.',
            'match_score': 85,
        }
    ]

    sample_stats = {
        'jobs_matched': 5,
        'proposals_generated': 3,
        'timestamp': datetime.now().isoformat()
    }

    # Test with dry_run=True (won't actually send)
    result = send_notification(sample_proposals, sample_stats, dry_run=True)
    print(f"\nTest result: {'✅ Success' if result else '❌ Failed'}")
