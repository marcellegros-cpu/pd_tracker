"""
Email sender for PD Tracker.

Sends reports via email using SMTP.
Supports sending to multiple recipients with attachments.

Configuration is done via environment variables:
- PD_TRACKER_EMAIL: Your email address (sender)
- PD_TRACKER_EMAIL_PASSWORD: App password (not your regular password!)
- PD_TRACKER_SMTP_HOST: SMTP server (default: smtp.gmail.com)
- PD_TRACKER_SMTP_PORT: SMTP port (default: 587)
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional

from .database import get_connection


# ============================================================
# CONFIGURATION
# ============================================================

def get_email_config() -> dict:
    """Get email configuration from environment variables."""
    return {
        'email': os.environ.get('PD_TRACKER_EMAIL'),
        'password': os.environ.get('PD_TRACKER_EMAIL_PASSWORD'),
        'smtp_host': os.environ.get('PD_TRACKER_SMTP_HOST', 'smtp.gmail.com'),
        'smtp_port': int(os.environ.get('PD_TRACKER_SMTP_PORT', '587')),
    }


def is_email_configured() -> bool:
    """Check if email is configured."""
    config = get_email_config()
    return bool(config['email'] and config['password'])


def get_missing_email_config() -> List[str]:
    """Return list of missing configuration items."""
    config = get_email_config()
    missing = []
    if not config['email']:
        missing.append('PD_TRACKER_EMAIL')
    if not config['password']:
        missing.append('PD_TRACKER_EMAIL_PASSWORD')
    return missing


def print_email_setup_instructions():
    """Print instructions for setting up email."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           EMAIL SETUP INSTRUCTIONS                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  For Gmail:                                                                  ║
║  1. Enable 2-Factor Authentication on your Google account                    ║
║  2. Go to: https://myaccount.google.com/apppasswords                        ║
║  3. Generate an "App Password" for "Mail"                                   ║
║  4. Use that 16-character password (not your regular password!)             ║
║                                                                              ║
║  Add these lines to your ~/.zshrc file:                                     ║
║                                                                              ║
║     export PD_TRACKER_EMAIL="your.email@gmail.com"                          ║
║     export PD_TRACKER_EMAIL_PASSWORD="xxxx xxxx xxxx xxxx"                  ║
║                                                                              ║
║  Then run: source ~/.zshrc                                                  ║
║                                                                              ║
║  For other email providers, also set:                                       ║
║     export PD_TRACKER_SMTP_HOST="smtp.yourprovider.com"                     ║
║     export PD_TRACKER_SMTP_PORT="587"                                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


# ============================================================
# RECIPIENT MANAGEMENT
# ============================================================

def add_recipient(email: str, name: str = None) -> int:
    """
    Add an email recipient for reports.

    Args:
        email: Email address
        name: Optional name

    Returns:
        ID of the recipient
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR REPLACE INTO email_recipients (email, name, active) VALUES (?, ?, 1)",
        (email, name)
    )

    recipient_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return recipient_id


def get_recipients(active_only: bool = True) -> List[dict]:
    """Get all email recipients."""
    conn = get_connection()
    cursor = conn.cursor()

    if active_only:
        cursor.execute("SELECT * FROM email_recipients WHERE active = 1")
    else:
        cursor.execute("SELECT * FROM email_recipients")

    rows = cursor.fetchall()
    conn.close()

    return [dict(r) for r in rows]


def remove_recipient(email: str) -> bool:
    """Remove (deactivate) a recipient."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE email_recipients SET active = 0 WHERE email = ?",
        (email,)
    )

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


# ============================================================
# EMAIL SENDING
# ============================================================

def send_email(
    to_addresses: List[str],
    subject: str,
    body: str,
    attachments: List[Path] = None,
) -> dict:
    """
    Send an email with optional attachments.

    Args:
        to_addresses: List of recipient email addresses
        subject: Email subject
        body: Email body (plain text)
        attachments: List of file paths to attach

    Returns:
        Dict with 'success' and either 'message' or 'error'
    """
    if not is_email_configured():
        return {
            'success': False,
            'error': 'Email not configured. Run "pd report email-setup" for instructions.'
        }

    config = get_email_config()

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = config['email']
        msg['To'] = ', '.join(to_addresses)
        msg['Subject'] = subject

        # Attach body
        msg.attach(MIMEText(body, 'plain'))

        # Attach files
        if attachments:
            for filepath in attachments:
                filepath = Path(filepath)
                if filepath.exists():
                    with open(filepath, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{filepath.name}"'
                    )
                    msg.attach(part)

        # Send email
        with smtplib.SMTP(config['smtp_host'], config['smtp_port']) as server:
            server.starttls()
            server.login(config['email'], config['password'])
            server.send_message(msg)

        return {
            'success': True,
            'message': f'Email sent to {len(to_addresses)} recipient(s)'
        }

    except smtplib.SMTPAuthenticationError:
        return {
            'success': False,
            'error': 'Authentication failed. Check your email and app password.'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def send_report_email(
    report_path: Path,
    to_addresses: List[str] = None,
    subject: str = None,
) -> dict:
    """
    Send a report file via email.

    Args:
        report_path: Path to the report file
        to_addresses: List of recipients (uses saved recipients if None)
        subject: Custom subject (auto-generated if None)

    Returns:
        Dict with 'success' and either 'message' or 'error'
    """
    # Get recipients
    if to_addresses is None:
        recipients = get_recipients()
        if not recipients:
            return {
                'success': False,
                'error': 'No email recipients configured. Use "pd report add-email" first.'
            }
        to_addresses = [r['email'] for r in recipients]

    # Generate subject
    if subject is None:
        from datetime import datetime
        subject = f"PD Tracker Report - {datetime.now().strftime('%Y-%m-%d')}"

    # Generate body
    body = f"""
PD Tracker Report

Please find your health tracking report attached.

Report file: {report_path.name}
Generated: {Path(report_path).stat().st_mtime if report_path.exists() else 'N/A'}

---
This report was automatically generated by PD Tracker.
"""

    return send_email(to_addresses, subject, body, [report_path])


def send_test_email() -> dict:
    """Send a test email to verify configuration."""
    if not is_email_configured():
        return {
            'success': False,
            'error': 'Email not configured. Run "pd report email-setup" for instructions.'
        }

    config = get_email_config()

    result = send_email(
        [config['email']],
        "PD Tracker - Test Email",
        "This is a test email from PD Tracker.\n\nIf you received this, your email configuration is working correctly!"
    )

    return result
