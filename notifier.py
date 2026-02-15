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

import html
import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict, Optional

import config
from config_loader import load_config
from database.db import get_connection


def load_email_config() -> dict:
    """Load email configuration — tries DB first, falls back to YAML."""
    return load_config("email_config", top_level_key="email")


def generate_proposal_html(proposals: List[Dict], monitor_stats: Dict) -> str:
    """Generate HTML email body with proposal summaries and job details.

    Args:
        proposals: List of proposal dicts from database
        monitor_stats: Dict with keys: jobs_matched, proposals_generated, etc.

    Returns:
        HTML string for email body
    """
    jobs_matched = monitor_stats.get('jobs_matched', 0)
    proposals_generated = monitor_stats.get('proposals_generated', 0)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Get email config and dashboard URL
    email_cfg = load_email_config()
    dashboard_url = email_cfg.get('dashboard_url', 'https://upwork-scrap-fenloai.streamlit.app/')
    max_proposals = email_cfg.get('notifications', {}).get('max_proposals_per_email', 10)
    shown_proposals = proposals[:max_proposals]
    remaining = len(proposals) - len(shown_proposals)

    # Fetch job details from database for all proposals
    conn = get_connection()
    job_details_map = {}
    for prop in shown_proposals:
        job_uid = prop.get('job_uid')
        if job_uid:
            row = conn.execute("SELECT * FROM jobs WHERE uid = ?", (job_uid,)).fetchone()
            if row:
                job_details_map[job_uid] = dict(row)
    conn.close()

    # Build proposal cards HTML with job details
    proposal_cards = ""
    for prop in shown_proposals:
        job_uid = prop.get('job_uid', 'unknown')
        match_score = prop.get('match_score', 0)
        proposal_text = prop.get('proposal_text', '')

        # Get job details from fetched data
        job = job_details_map.get(job_uid, {})
        job_title = html.escape(job.get('title', f'Job {job_uid[:8]}'))
        job_url = job.get('url', f"https://www.upwork.com/jobs/{job_uid}")

        # Job description (truncated)
        description = job.get('description', '')
        description_preview = description[:200] + "..." if len(description) > 200 else description
        description_preview = html.escape(description_preview)

        # Budget/rate info
        budget_html = ""
        if job.get('job_type') == 'Hourly':
            hourly_min = job.get('hourly_rate_min', 0)
            hourly_max = job.get('hourly_rate_max', 0)
            if hourly_min or hourly_max:
                budget_html = f"💰 ${hourly_min:.0f}-${hourly_max:.0f}/hr"
        else:
            fixed_price = job.get('fixed_price', 0)
            if fixed_price:
                budget_html = f"💰 ${fixed_price:,.0f} fixed"

        # Skills
        skills_raw = job.get('skills', '')
        try:
            skills_list = json.loads(skills_raw) if skills_raw else []
        except (json.JSONDecodeError, TypeError):
            skills_list = []
        skills_html = ""
        if skills_list:
            skills_display = skills_list[:5]  # First 5 skills
            skills_tags = " ".join([f'<span style="background:#e3f2fd;padding:4px 8px;border-radius:4px;font-size:11px;display:inline-block;margin:2px;">{html.escape(s)}</span>' for s in skills_display])
            skills_html = f'<div style="margin-top:8px;">{skills_tags}</div>'

        # Client info
        client_html = ""
        client_country = job.get('client_country', '')
        client_spent = job.get('client_total_spent', '')
        client_rating = job.get('client_rating', '')
        if client_country or client_spent:
            client_info_parts = []
            if client_country:
                client_info_parts.append(f"📍 {html.escape(client_country)}")
            if client_spent:
                client_info_parts.append(f"💳 {html.escape(client_spent)} spent")
            if client_rating:
                client_info_parts.append(f"⭐ {html.escape(client_rating)}")
            client_html = f'<div style="margin-top:8px;font-size:12px;color:#666;">{" · ".join(client_info_parts)}</div>'

        # Truncate proposal for email
        proposal_preview = proposal_text[:250] + "..." if len(proposal_text) > 250 else proposal_text
        proposal_preview = html.escape(proposal_preview)

        # Score color
        score_color = "#14a800" if match_score >= 70 else ("#f57c00" if match_score >= 40 else "#9e9e9e")

        proposal_cards += f"""
        <div style="border-left: 4px solid {score_color}; padding: 16px; margin-bottom: 20px;
                    background: #f8f9fa; border-radius: 8px;">
            <!-- Header with title and score -->
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                <div style="flex: 1;">
                    <h3 style="margin: 0 0 6px 0; font-size: 18px;">
                        <a href="{job_url}" style="color: #1976d2; text-decoration: none;">{job_title}</a>
                    </h3>
                    {f'<div style="font-size:13px;color:#666;margin-bottom:4px;">{budget_html}</div>' if budget_html else ''}
                </div>
                <div style="font-size: 24px; font-weight: bold; color: {score_color}; margin-left: 12px;">
                    🎯 {match_score:.0f}
                </div>
            </div>

            <!-- Job description -->
            {f'<div style="background:#fff;padding:10px;border-radius:6px;font-size:13px;color:#555;margin-bottom:8px;border-left:3px solid #e0e0e0;">{description_preview}</div>' if description_preview else ''}

            <!-- Skills -->
            {skills_html}

            <!-- Client info -->
            {client_html}

            <!-- Proposal text -->
            <div style="background: white; padding: 12px; border-radius: 6px; font-family: system-ui;
                        white-space: pre-wrap; font-size: 14px; color: #333; margin-top: 12px; border: 1px solid #e0e0e0;">
                <strong style="color:#1976d2;">📝 Your Proposal:</strong><br><br>
                {proposal_preview}
            </div>

            <!-- Action button -->
            <div style="margin-top: 12px; text-align: center;">
                <a href="{dashboard_url}" style="display:inline-block;background:#1976d2;color:white;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
                    Review & Submit in Dashboard →
                </a>
            </div>
        </div>
        """

    if remaining > 0:
        proposal_cards += f"""
        <div style="padding: 16px; background: #e3f2fd; border-radius: 8px; text-align: center;">
            <strong>+ {remaining} more proposal(s)</strong>
            <br>
            <a href="{dashboard_url}" style="color: #1976d2; font-weight: 600; text-decoration: none;">View all in Dashboard →</a>
        </div>
        """

    # Full HTML email
    email_html = f"""
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
                    <a href="{dashboard_url}" style="color: #1976d2; text-decoration: none; font-weight: 600;">
                        🚀 Open Dashboard →
                    </a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return email_html


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
    except (smtplib.SMTPException, ConnectionError, TimeoutError, OSError) as e:
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
