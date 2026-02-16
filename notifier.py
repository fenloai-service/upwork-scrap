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
    # Extract stats - focus on NEW items from this run
    jobs_scraped = monitor_stats.get('jobs_scraped', 0)
    jobs_new = monitor_stats.get('jobs_new', 0)
    jobs_classified = monitor_stats.get('jobs_classified', 0)
    jobs_matched = monitor_stats.get('jobs_matched', 0)  # NEW matched jobs in this run
    proposals_generated = monitor_stats.get('proposals_generated', 0)  # NEW proposals in this run
    duration_seconds = monitor_stats.get('duration_seconds', 0)
    duration_str = f"{int(duration_seconds // 60)}m {int(duration_seconds % 60)}s" if duration_seconds else "N/A"
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

        # Get job details from fetched data
        job = job_details_map.get(job_uid, {})
        job_title = html.escape(job.get('title', f'Job {job_uid[:8]}'))
        job_url = html.escape(job.get('url', f"https://www.upwork.com/jobs/{job_uid}"))

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
            skills_display = skills_list[:6]  # First 6 skills
            skills_tags = " ".join([f'<span style="background:#f3f4f6;padding:5px 10px;border-radius:4px;font-size:11px;display:inline-block;margin:3px 4px 3px 0;color:#374151;">{html.escape(s)}</span>' for s in skills_display])
            skills_html = f'<div style="margin-top:10px;">{skills_tags}</div>'

        # Client info
        client_html = ""
        client_country = job.get('client_country', '')
        client_spent = job.get('client_total_spent', '')
        client_rating = job.get('client_rating', '')
        if client_country or client_spent or client_rating:
            client_info_parts = []
            if client_country:
                client_info_parts.append(f"📍 {html.escape(client_country)}")
            if client_spent:
                client_info_parts.append(f"${html.escape(client_spent)}")
            if client_rating:
                client_info_parts.append(f"⭐ {html.escape(client_rating)}")
            client_html = f'<div style="margin-top:10px;font-size:12px;color:#6b7280;">{" · ".join(client_info_parts)}</div>'

        # AI summary (most important content)
        ai_summary = job.get('ai_summary', '')
        ai_summary_html = ""
        if ai_summary:
            ai_summary_escaped = html.escape(ai_summary)
            ai_summary_html = f'''<div style="background:#f9fafb;padding:14px;border-radius:6px;font-size:13px;color:#374151;margin-top:12px;line-height:1.6;">
                {ai_summary_escaped}
            </div>'''

        # Job metadata (experience, duration, competition)
        job_meta_parts = []
        experience = job.get('experience_level', '')
        if experience:
            job_meta_parts.append(html.escape(experience))
        est_time = job.get('est_time', '')
        if est_time:
            job_meta_parts.append(html.escape(est_time))
        proposals_count = job.get('proposals', '')
        if proposals_count:
            job_meta_parts.append(f"{html.escape(proposals_count)} proposals")
        posted_text = job.get('posted_text', '')
        if posted_text:
            job_meta_parts.append(html.escape(posted_text))
        job_meta_html = ""
        if job_meta_parts:
            job_meta_html = f'<div style="font-size:12px;color:#6b7280;">{" · ".join(job_meta_parts)}</div>'

        # Key tools from AI classification
        key_tools_raw = job.get('key_tools', '')
        try:
            key_tools_list = json.loads(key_tools_raw) if key_tools_raw else []
        except (json.JSONDecodeError, TypeError):
            key_tools_list = []
        key_tools_html = ""
        if key_tools_list:
            tools_display = key_tools_list[:5]
            tools_tags = " ".join([f'<span style="background:#fef3c7;padding:5px 10px;border-radius:4px;font-size:11px;display:inline-block;margin:3px 4px 3px 0;color:#92400e;font-weight:500;">{html.escape(t)}</span>' for t in tools_display])
            key_tools_html = f'<div style="margin-top:10px;">{tools_tags}</div>'

        # Score badge color
        score_color = "#14a800" if match_score >= 70 else ("#f59e0b" if match_score >= 40 else "#6b7280")
        score_bg = "#ecfdf5" if match_score >= 70 else ("#fef3c7" if match_score >= 40 else "#f3f4f6")

        proposal_cards += f"""
        <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 16px;
                    background: white;">
            <!-- Header -->
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                <div style="flex: 1;">
                    <h3 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600; line-height: 1.4;">
                        <a href="{job_url}" style="color: #111827; text-decoration: none;">{job_title}</a>
                    </h3>
                    {f'<div style="font-size:14px;color:#1976d2;font-weight:500;">{budget_html}</div>' if budget_html else ''}
                </div>
                <div style="background: {score_bg}; color: {score_color}; padding: 6px 12px; border-radius: 6px;
                           font-size: 14px; font-weight: 600; margin-left: 16px; white-space: nowrap;">
                    {match_score:.0f}% Match
                </div>
            </div>

            <!-- Job metadata -->
            {job_meta_html}

            <!-- AI Summary (most important) -->
            {ai_summary_html}

            <!-- Skills (condensed) -->
            {skills_html}

            <!-- Key tools (condensed) -->
            {key_tools_html}

            <!-- Client info -->
            {client_html}

            <!-- Action - just a link, no big button in card -->
            <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #f3f4f6;">
                <a href="{job_url}" style="color: #1976d2; text-decoration: none; font-weight: 500; font-size: 13px;">
                    View Job on Upwork →
                </a>
            </div>
        </div>
        """

    if remaining > 0:
        proposal_cards += f"""
        <div style="padding: 20px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; text-align: center; margin-top: 8px;">
            <div style="font-size: 14px; color: #6b7280; margin-bottom: 8px;">
                + {remaining} more proposal{'' if remaining == 1 else 's'} waiting in your dashboard
            </div>
            <a href="{dashboard_url}" style="display: inline-block; color: #1976d2; font-weight: 500; text-decoration: none; font-size: 13px;">
                View All Proposals →
            </a>
        </div>
        """

    # Full HTML email with clean, minimal design
    email_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                 background: #f9fafb; margin: 0; padding: 20px;">
        <div style="max-width: 650px; margin: 0 auto; background: white; border-radius: 8px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden;">

            <!-- Hero Header -->
            <div style="background: #1976d2; padding: 32px 24px; color: white;">
                <div style="font-size: 14px; text-transform: uppercase; letter-spacing: 1px; opacity: 0.9; margin-bottom: 8px;">
                    Upwork Monitor · {timestamp}
                </div>
                <h1 style="margin: 0; font-size: 24px; font-weight: 600; line-height: 1.3;">
                    {proposals_generated} New Proposal{'' if proposals_generated == 1 else 's'} Ready for Review
                </h1>
                {f'<p style="margin: 12px 0 0 0; font-size: 15px; opacity: 0.95;">{jobs_matched} matching job{'' if jobs_matched == 1 else 's'} found in this scan</p>' if jobs_matched > 0 else ''}
            </div>

            <!-- Quick Stats (This Run Only) -->
            <div style="padding: 20px 24px; background: #f8f9fa; border-bottom: 1px solid #e5e7eb;">
                <div style="font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                    This Run Summary
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 16px;">
                    {f'<div><div style="font-size: 20px; font-weight: 600; color: #0288d1;">{jobs_new}</div><div style="font-size: 11px; color: #6b7280; margin-top: 2px;">New Jobs</div></div>' if jobs_new > 0 else ''}
                    {f'<div><div style="font-size: 20px; font-weight: 600; color: #7b1fa2;">{jobs_classified}</div><div style="font-size: 11px; color: #6b7280; margin-top: 2px;">Classified</div></div>' if jobs_classified > 0 else ''}
                    <div>
                        <div style="font-size: 20px; font-weight: 600; color: #1976d2;">{jobs_matched}</div>
                        <div style="font-size: 11px; color: #6b7280; margin-top: 2px;">Matched</div>
                    </div>
                    <div>
                        <div style="font-size: 20px; font-weight: 600; color: #14a800;">{proposals_generated}</div>
                        <div style="font-size: 11px; color: #6b7280; margin-top: 2px;">Generated</div>
                    </div>
                    <div>
                        <div style="font-size: 20px; font-weight: 600; color: #6b7280;">{duration_str}</div>
                        <div style="font-size: 11px; color: #6b7280; margin-top: 2px;">Duration</div>
                    </div>
                </div>
            </div>

            <!-- Proposals Section -->
            <div style="padding: 24px;">
                {f'<div style="margin-bottom: 20px;"><h2 style="margin: 0; font-size: 16px; font-weight: 600; color: #111827;">Top {len(shown_proposals)} Proposal{'' if len(shown_proposals) == 1 else 's'}</h2><p style="margin: 4px 0 0 0; font-size: 13px; color: #6b7280;">Review and submit from your dashboard</p></div>' if shown_proposals else ''}
                {proposal_cards}
            </div>

            <!-- Footer -->
            <div style="padding: 24px; background: #f9fafb; text-align: center; border-top: 1px solid #e5e7eb;">
                <a href="{dashboard_url}" style="display: inline-block; background: #1976d2; color: white;
                   padding: 12px 32px; border-radius: 6px; text-decoration: none; font-weight: 500; font-size: 14px;">
                    Open Dashboard
                </a>
                <p style="margin: 16px 0 0 0; color: #9ca3af; font-size: 12px;">
                    Upwork Proposal Monitor · Automated by AI
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

    # Support both 'recipients' (list) and legacy 'recipient' (string)
    recipients = notifications_cfg.get('recipients')
    if not recipients:
        legacy = notifications_cfg.get('recipient')
        recipients = [legacy] if legacy else []
    elif isinstance(recipients, str):
        recipients = [recipients]

    # Validate
    if not smtp_username or not recipients:
        print("❌ SMTP username or recipients not configured in config/email_config.yaml")
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
        msg['To'] = ", ".join(recipients)

        # Attach HTML body
        msg.attach(MIMEText(html_body, 'html'))

        # Send via SMTP
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_username, recipients, msg.as_string())

        print(f"✅ Email sent successfully to {', '.join(recipients)}")
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

    # Generate email content - focus on NEW proposals from this run
    new_proposals = monitor_stats.get('proposals_generated', len(proposals))
    new_matches = monitor_stats.get('jobs_matched', 0)

    if new_proposals > 0:
        subject = f"🎯 {new_proposals} New Proposal{'' if new_proposals == 1 else 's'} · {new_matches} Job{'' if new_matches == 1 else 's'} Matched"
    else:
        subject = f"✅ Monitor Complete · {new_matches} Job{'' if new_matches == 1 else 's'} Matched"

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
