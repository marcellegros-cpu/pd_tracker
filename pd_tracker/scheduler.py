"""
Background scheduler for medication reminders.

This module runs as a daemon, continuously checking for upcoming medication
doses and sending SMS reminders via Twilio.

Usage:
    pd reminder start       # Start in foreground (Ctrl+C to stop)
    pd reminder start -d    # Start as background daemon

The scheduler uses the pending_reminders database table for persistence,
ensuring reminders aren't lost on restart and duplicates aren't sent.

Flow:
1. When user logs "I'm Awake", generate_wake_based_reminders() populates pending_reminders
2. This scheduler checks pending_reminders every minute
3. Sends SMS for due reminders (reminder_time <= now, not sent)
4. Marks reminders as sent in database
5. Sends follow-up for overdue reminders (15 min after, dose not logged)
"""

import time
import signal
import sys
from datetime import datetime

from . import config
from .schedules import (
    get_due_reminders,
    get_overdue_reminders,
    mark_reminder_sent,
    mark_followup_sent,
    get_all_active_schedules,
    is_user_awake,
)
from .reminders import send_medication_reminder, send_missed_dose_followup


def check_and_send_reminders():
    """
    Check for due reminders and send them.

    Uses the pending_reminders table for persistence.
    """
    now = datetime.now()

    # Only send reminders if user is awake
    if not is_user_awake():
        return

    # Get reminders that are due now (reminder_time <= now, not sent)
    due_reminders = get_due_reminders()

    for reminder in due_reminders:
        med_name = reminder['medication_name']
        dosage = reminder['dosage']
        scheduled_time = reminder['scheduled_time']

        print(f"[{now.strftime('%H:%M')}] Sending reminder: {med_name} due at {scheduled_time.strftime('%I:%M %p')}")

        result = send_medication_reminder(med_name, dosage, scheduled_time)

        if result['success']:
            mark_reminder_sent(reminder['id'])
            print(f"  ✓ Reminder sent")
        else:
            print(f"  ✗ Failed: {result['error']}")


def check_and_send_followups():
    """
    Check for overdue reminders (dose not logged) and send follow-ups.
    """
    now = datetime.now()

    # Only send follow-ups if user is awake
    if not is_user_awake():
        return

    # Get reminders that are overdue (sent but dose not logged within 15 min)
    overdue = get_overdue_reminders(minutes=config.FOLLOWUP_MINUTES_AFTER)

    for reminder in overdue:
        med_name = reminder['medication_name']
        dosage = reminder['dosage']
        scheduled_time = reminder['scheduled_time']

        print(f"[{now.strftime('%H:%M')}] Sending follow-up: {med_name} was due at {scheduled_time.strftime('%I:%M %p')}")

        result = send_missed_dose_followup(med_name, dosage, scheduled_time)

        if result['success']:
            mark_followup_sent(reminder['id'])
            print(f"  ✓ Follow-up sent")
        else:
            print(f"  ✗ Failed: {result['error']}")


def run_scheduler(check_interval: int = 60):
    """
    Run the reminder scheduler.

    Args:
        check_interval: How often to check for reminders (in seconds)
    """
    print("\n" + "=" * 50)
    print("  PD TRACKER REMINDER SERVICE")
    print("=" * 50)
    print(f"\n  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Check interval: {check_interval} seconds")
    print(f"  Reminder window: {config.REMINDER_MINUTES_BEFORE} minutes before dose")
    print(f"  Follow-up window: {config.FOLLOWUP_MINUTES_AFTER} minutes after dose")
    print("\n  Using database-backed pending_reminders for persistence")
    print("\n  Press Ctrl+C to stop\n")
    print("-" * 50)

    # Set up signal handler for clean shutdown
    def signal_handler(sig, frame):
        print(f"\n\n[{datetime.now().strftime('%H:%M')}] Shutting down reminder service...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Show current status
    if is_user_awake():
        print("\nUser is AWAKE - reminders active")
    else:
        print("\nUser is NOT AWAKE - reminders paused")
        print("Reminders will start when user logs 'I'm Awake'")

    schedules = get_all_active_schedules()
    if schedules:
        print(f"\nActive medication schedules: {len(schedules)}")
        for sched in schedules:
            status = "reminders ON" if sched.get('reminders_enabled', True) else "reminders OFF"
            print(f"  • {sched['medication_name']}: {status}")
    else:
        print("\nNo active medication schedules.")
        print("Use the web UI or CLI to set up schedules.")
    print()

    # Main loop
    while True:
        try:
            check_and_send_reminders()
            check_and_send_followups()
            time.sleep(check_interval)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M')}] Error: {e}")
            time.sleep(check_interval)


if __name__ == "__main__":
    run_scheduler()
