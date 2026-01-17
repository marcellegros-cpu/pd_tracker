"""
Background scheduler for medication reminders.

This module runs as a daemon, continuously checking for upcoming medication
doses and sending SMS reminders via Twilio.

Usage:
    pd reminder start       # Start in foreground (Ctrl+C to stop)
    pd reminder start -d    # Start as background daemon

The scheduler:
1. Checks every minute for doses due in the next 5 minutes
2. Sends SMS reminders for upcoming doses
3. Tracks which reminders have been sent to avoid duplicates
4. Optionally sends follow-up reminders for missed doses
"""

import time
import signal
import sys
from datetime import datetime, date
from typing import Set

from . import config
from .schedules import get_all_active_schedules, get_scheduled_times_for_today
from .reminders import send_medication_reminder, send_missed_dose_followup
from .models import get_doses_today


# Track which reminders we've already sent today (to avoid duplicates)
# Key format: "med_id:HH:MM"
sent_reminders: Set[str] = set()
sent_followups: Set[str] = set()
current_date: date = None


def reset_daily_tracking():
    """Reset the sent reminders tracking at midnight."""
    global sent_reminders, sent_followups, current_date
    today = date.today()
    if current_date != today:
        sent_reminders = set()
        sent_followups = set()
        current_date = today
        print(f"[{datetime.now().strftime('%H:%M')}] New day - reset reminder tracking")


def get_reminder_key(medication_id: int, scheduled_time: datetime) -> str:
    """Generate a unique key for a reminder."""
    return f"{medication_id}:{scheduled_time.strftime('%H:%M')}"


def check_and_send_reminders():
    """
    Check for upcoming doses and send reminders.

    This is the main function that runs every minute.
    """
    reset_daily_tracking()

    now = datetime.now()
    schedules = get_all_active_schedules()

    for sched in schedules:
        med_id = sched['medication_id']
        med_name = sched['medication_name']
        dosage = sched['dosage']

        # Get today's scheduled times for this medication
        times = get_scheduled_times_for_today(med_id)

        for scheduled_time in times:
            key = get_reminder_key(med_id, scheduled_time)

            # Calculate minutes until this dose
            diff_seconds = (scheduled_time - now).total_seconds()
            diff_minutes = diff_seconds / 60

            # Send reminder if dose is coming up (within reminder window)
            if 0 < diff_minutes <= config.REMINDER_MINUTES_BEFORE:
                if key not in sent_reminders:
                    print(f"[{now.strftime('%H:%M')}] Sending reminder: {med_name} due at {scheduled_time.strftime('%I:%M %p')}")
                    result = send_medication_reminder(med_name, dosage, scheduled_time)
                    if result['success']:
                        sent_reminders.add(key)
                        print(f"  ✓ Reminder sent")
                    else:
                        print(f"  ✗ Failed: {result['error']}")

            # Send follow-up if dose was missed (past the scheduled time + followup window)
            elif -config.FOLLOWUP_MINUTES_AFTER <= diff_minutes < -config.REMINDER_MINUTES_BEFORE:
                followup_key = f"followup:{key}"
                if followup_key not in sent_followups:
                    # Check if dose was actually taken
                    today_doses = get_doses_today(med_id)
                    dose_taken = False
                    for dose in today_doses:
                        dose_time = datetime.fromisoformat(dose['taken_time'])
                        # Consider it taken if logged within 30 minutes of scheduled time
                        if abs((dose_time - scheduled_time).total_seconds()) < 1800:
                            dose_taken = True
                            break

                    if not dose_taken:
                        print(f"[{now.strftime('%H:%M')}] Sending follow-up: {med_name} was due at {scheduled_time.strftime('%I:%M %p')}")
                        result = send_missed_dose_followup(med_name, dosage, scheduled_time)
                        if result['success']:
                            sent_followups.add(followup_key)
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
    print("\n  Press Ctrl+C to stop\n")
    print("-" * 50)

    # Set up signal handler for clean shutdown
    def signal_handler(sig, frame):
        print(f"\n\n[{datetime.now().strftime('%H:%M')}] Shutting down reminder service...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Show current schedules
    schedules = get_all_active_schedules()
    if schedules:
        print("\nActive medication schedules:")
        for sched in schedules:
            times = get_scheduled_times_for_today(sched['medication_id'])
            time_strs = [t.strftime('%I:%M %p').lstrip('0') for t in times]
            print(f"  • {sched['medication_name']}: {', '.join(time_strs) if time_strs else 'No times today'}")
    else:
        print("\nNo active medication schedules.")
        print("Use 'pd med schedule <medication>' to set up schedules.")
    print()

    # Main loop
    while True:
        try:
            check_and_send_reminders()
            time.sleep(check_interval)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M')}] Error: {e}")
            time.sleep(check_interval)


if __name__ == "__main__":
    run_scheduler()
