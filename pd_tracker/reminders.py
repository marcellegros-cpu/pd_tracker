"""
SMS reminder system using Twilio.

This module handles:
- Sending medication reminders via SMS
- Testing the Twilio connection
- Formatting reminder messages
"""

from datetime import datetime
from typing import Optional

from . import config


def send_sms(message: str) -> dict:
    """
    Send an SMS message via Twilio.

    Args:
        message: The text message to send

    Returns:
        Dict with 'success' boolean and either 'sid' (message ID) or 'error'
    """
    # Import here to avoid errors if Twilio isn't configured yet
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException

    if not config.is_twilio_configured():
        return {
            'success': False,
            'error': 'Twilio not configured. Run "pd reminder setup" for instructions.'
        }

    try:
        client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)

        message = client.messages.create(
            body=message,
            from_=config.TWILIO_PHONE_NUMBER,
            to=config.USER_PHONE_NUMBER
        )

        return {
            'success': True,
            'sid': message.sid,
        }

    except TwilioRestException as e:
        return {
            'success': False,
            'error': f"Twilio error: {e.msg}"
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Error: {str(e)}"
        }


def send_medication_reminder(medication_name: str, dosage: Optional[str] = None,
                              scheduled_time: Optional[datetime] = None) -> dict:
    """
    Send a medication reminder SMS.

    Args:
        medication_name: Name of the medication
        dosage: Optional dosage string
        scheduled_time: Optional scheduled time for the dose

    Returns:
        Result dict from send_sms()
    """
    # Build the message
    if dosage:
        med_str = f"{medication_name} ({dosage})"
    else:
        med_str = medication_name

    if scheduled_time:
        time_str = scheduled_time.strftime("%I:%M %p").lstrip('0')
        message = f"💊 PD Tracker Reminder\n\nTime to take: {med_str}\nScheduled: {time_str}"
    else:
        message = f"💊 PD Tracker Reminder\n\nTime to take: {med_str}"

    return send_sms(message)


def send_missed_dose_followup(medication_name: str, dosage: Optional[str] = None,
                               scheduled_time: Optional[datetime] = None) -> dict:
    """
    Send a follow-up SMS for a potentially missed dose.

    Args:
        medication_name: Name of the medication
        dosage: Optional dosage string
        scheduled_time: When the dose was scheduled

    Returns:
        Result dict from send_sms()
    """
    if dosage:
        med_str = f"{medication_name} ({dosage})"
    else:
        med_str = medication_name

    if scheduled_time:
        time_str = scheduled_time.strftime("%I:%M %p").lstrip('0')
        message = f"❓ PD Tracker Follow-up\n\nDid you take your {med_str}?\nIt was scheduled for {time_str}.\n\nLog it with: pd med take {medication_name.split()[0].lower()}"
    else:
        message = f"❓ PD Tracker Follow-up\n\nDid you take your {med_str}?\n\nLog it with: pd med take {medication_name.split()[0].lower()}"

    return send_sms(message)


def send_daily_summary(summary_text: str) -> dict:
    """
    Send a daily medication summary SMS.

    Args:
        summary_text: Pre-formatted summary text

    Returns:
        Result dict from send_sms()
    """
    message = f"📋 PD Tracker Daily Summary\n\n{summary_text}"
    return send_sms(message)


def send_test_message() -> dict:
    """
    Send a test SMS to verify Twilio is working.

    Returns:
        Result dict from send_sms()
    """
    message = "✅ PD Tracker Test\n\nYour SMS reminders are working!\n\nYou'll receive reminders when your medications are due."
    return send_sms(message)


def format_upcoming_reminders(upcoming: list) -> str:
    """
    Format a list of upcoming doses for display or SMS.

    Args:
        upcoming: List from schedules.get_all_upcoming_doses()

    Returns:
        Formatted string
    """
    if not upcoming:
        return "No upcoming doses"

    lines = []
    for dose in upcoming:
        time_str = dose['scheduled_time'].strftime("%I:%M %p").lstrip('0')
        if dose['dosage']:
            lines.append(f"  {time_str} - {dose['medication_name']} ({dose['dosage']})")
        else:
            lines.append(f"  {time_str} - {dose['medication_name']}")

    return "\n".join(lines)
