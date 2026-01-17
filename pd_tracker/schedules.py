"""
Medication scheduling system for PD Tracker.

Supports multiple schedule types:
- 'on_wake': Take once when waking up for the day
- 'interval_from_wake': Take every X hours after waking (e.g., every 4 hours)
- 'mid_day': Take once mid-day
- 'night_wake': Take once if waking during the night
- 'monthly_injection': Take once every X months
- 'fixed': Specific times each day (legacy)
- 'prn': As needed (no automatic reminders)

The key feature is wake-based scheduling:
- When user logs waking up, the system calculates medication times
- Reminders are triggered based on wake time, not fixed clock times
- The schedule runs until the user logs going to sleep
"""

import json
from datetime import datetime, date, time, timedelta
from typing import Optional, List
from .database import get_connection


# Schedule type constants
SCHEDULE_TYPES = {
    'on_wake': 'Take once on waking',
    'interval_from_wake': 'Take every X hours after waking',
    'mid_day': 'Take once mid-day',
    'night_wake': 'Take if waking at night',
    'monthly_injection': 'Injection every X months',
    'fixed': 'Fixed daily times',
    'prn': 'As needed (no reminders)',
}

# Interval options (in hours, 30-minute increments)
INTERVAL_OPTIONS = [
    1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0
]


# ============================================================
# WAKE/SLEEP EVENT TRACKING
# ============================================================

def log_wake_event(event_time: datetime = None, notes: str = None) -> int:
    """
    Log a wake-up event. This triggers medication schedule calculations.

    Args:
        event_time: When the user woke up (defaults to now)
        notes: Optional notes

    Returns:
        The ID of the wake event
    """
    if event_time is None:
        event_time = datetime.now()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO wake_sleep_events (event_type, event_time, notes)
           VALUES ('wake', ?, ?)""",
        (event_time, notes)
    )

    event_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Generate pending reminders for wake-based schedules
    generate_wake_based_reminders(event_time)

    return event_id


def log_sleep_event(event_time: datetime = None, notes: str = None) -> int:
    """
    Log a going-to-sleep event. This stops wake-based reminders.

    Args:
        event_time: When the user went to sleep (defaults to now)
        notes: Optional notes

    Returns:
        The ID of the sleep event
    """
    if event_time is None:
        event_time = datetime.now()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO wake_sleep_events (event_type, event_time, notes)
           VALUES ('sleep', ?, ?)""",
        (event_time, notes)
    )

    event_id = cursor.lastrowid

    # Clear any pending reminders after sleep time
    cursor.execute(
        """UPDATE pending_reminders SET sent = 1
           WHERE scheduled_time > ? AND sent = 0""",
        (event_time,)
    )

    conn.commit()
    conn.close()

    return event_id


def get_last_wake_event() -> Optional[dict]:
    """
    Get the most recent wake event.

    Returns:
        Dict with event details, or None if no wake logged today
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get wake event from today
    today_start = datetime.combine(date.today(), time.min)

    cursor.execute(
        """SELECT * FROM wake_sleep_events
           WHERE event_type = 'wake' AND event_time >= ?
           ORDER BY event_time DESC LIMIT 1""",
        (today_start,)
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row['id'],
            'event_type': row['event_type'],
            'event_time': datetime.fromisoformat(row['event_time']) if isinstance(row['event_time'], str) else row['event_time'],
            'notes': row['notes'],
        }
    return None


def get_last_sleep_event() -> Optional[dict]:
    """
    Get the most recent sleep event.

    Returns:
        Dict with event details, or None
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT * FROM wake_sleep_events
           WHERE event_type = 'sleep'
           ORDER BY event_time DESC LIMIT 1"""
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row['id'],
            'event_type': row['event_type'],
            'event_time': datetime.fromisoformat(row['event_time']) if isinstance(row['event_time'], str) else row['event_time'],
            'notes': row['notes'],
        }
    return None


def is_user_awake() -> bool:
    """
    Check if the user is currently awake (logged wake but not sleep).

    Returns:
        True if awake, False otherwise
    """
    wake = get_last_wake_event()
    sleep = get_last_sleep_event()

    if not wake:
        return False

    if not sleep:
        return True

    wake_time = wake['event_time']
    sleep_time = sleep['event_time']

    return wake_time > sleep_time


# ============================================================
# SCHEDULE MANAGEMENT
# ============================================================

def add_schedule(medication_id: int, schedule_type: str, times_data: dict,
                 reminders_enabled: bool = True) -> int:
    """
    Add a schedule for a medication.

    Args:
        medication_id: The medication's database ID
        schedule_type: One of the SCHEDULE_TYPES
        times_data: Schedule details (format depends on type)
            - For 'on_wake': {} (no additional data needed)
            - For 'interval_from_wake': {"interval_hours": 4.0}
            - For 'mid_day': {}
            - For 'night_wake': {}
            - For 'monthly_injection': {"months": 3}
            - For 'fixed': {"times": ["08:00", "14:00", "20:00"]}
            - For 'prn': {}
        reminders_enabled: Whether to send SMS/email reminders

    Returns:
        The ID of the new schedule
    """
    conn = get_connection()
    cursor = conn.cursor()

    # First, deactivate any existing schedules for this medication
    cursor.execute(
        "UPDATE medication_schedules SET active = 0 WHERE medication_id = ?",
        (medication_id,)
    )

    # Insert the new schedule
    cursor.execute(
        """INSERT INTO medication_schedules
           (medication_id, schedule_type, times, reminders_enabled)
           VALUES (?, ?, ?, ?)""",
        (medication_id, schedule_type, json.dumps(times_data), 1 if reminders_enabled else 0)
    )

    schedule_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return schedule_id


def get_schedule(medication_id: int) -> Optional[dict]:
    """
    Get the active schedule for a medication.

    Returns:
        Schedule record with parsed times_data, or None if no schedule
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT * FROM medication_schedules
           WHERE medication_id = ? AND active = 1
           ORDER BY created_at DESC LIMIT 1""",
        (medication_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row['id'],
            'medication_id': row['medication_id'],
            'schedule_type': row['schedule_type'],
            'times_data': json.loads(row['times']) if row['times'] else {},
            'active': row['active'],
            'reminders_enabled': row['reminders_enabled'] if 'reminders_enabled' in row.keys() else 1,
            'created_at': row['created_at'],
        }
    return None


def update_schedule(schedule_id: int, schedule_type: str = None,
                    times_data: dict = None, reminders_enabled: bool = None) -> bool:
    """
    Update an existing schedule.

    Returns:
        True if update was successful
    """
    updates = []
    values = []

    if schedule_type is not None:
        updates.append("schedule_type = ?")
        values.append(schedule_type)
    if times_data is not None:
        updates.append("times = ?")
        values.append(json.dumps(times_data))
    if reminders_enabled is not None:
        updates.append("reminders_enabled = ?")
        values.append(1 if reminders_enabled else 0)

    if not updates:
        return False

    values.append(schedule_id)

    conn = get_connection()
    cursor = conn.cursor()

    query = f"UPDATE medication_schedules SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def toggle_reminders(medication_id: int, enabled: bool) -> bool:
    """
    Toggle reminders on/off for a medication's schedule.

    Returns:
        True if toggle was successful
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """UPDATE medication_schedules
           SET reminders_enabled = ?
           WHERE medication_id = ? AND active = 1""",
        (1 if enabled else 0, medication_id)
    )

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def get_all_active_schedules() -> list:
    """
    Get all active schedules with medication info.

    Returns:
        List of schedules with medication names and dosages
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT s.*, m.name as medication_name, m.dosage
           FROM medication_schedules s
           JOIN medications m ON s.medication_id = m.id
           WHERE s.active = 1 AND m.active = 1
           ORDER BY m.name"""
    )

    rows = cursor.fetchall()
    conn.close()

    schedules = []
    for row in rows:
        schedules.append({
            'id': row['id'],
            'medication_id': row['medication_id'],
            'medication_name': row['medication_name'],
            'dosage': row['dosage'],
            'schedule_type': row['schedule_type'],
            'times_data': json.loads(row['times']) if row['times'] else {},
            'reminders_enabled': row['reminders_enabled'] if 'reminders_enabled' in row.keys() else 1,
        })

    return schedules


def delete_schedule(medication_id: int) -> bool:
    """
    Deactivate (soft delete) the schedule for a medication.

    Returns:
        True if a schedule was deactivated, False if none existed
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE medication_schedules SET active = 0 WHERE medication_id = ? AND active = 1",
        (medication_id,)
    )

    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return affected


# ============================================================
# WAKE-BASED REMINDER GENERATION
# ============================================================

def generate_wake_based_reminders(wake_time: datetime):
    """
    Generate pending reminders based on wake time.

    This is called when the user logs waking up.
    It creates reminder entries for all wake-based schedules.
    """
    schedules = get_all_active_schedules()

    conn = get_connection()
    cursor = conn.cursor()

    # Clear old pending reminders for today
    today_start = datetime.combine(date.today(), time.min)
    cursor.execute(
        "DELETE FROM pending_reminders WHERE created_at >= ?",
        (today_start,)
    )

    for sched in schedules:
        if not sched['reminders_enabled']:
            continue

        med_id = sched['medication_id']
        stype = sched['schedule_type']
        data = sched['times_data']

        if stype == 'on_wake':
            # Immediate reminder on waking
            scheduled = wake_time
            reminder = wake_time  # Remind immediately
            _add_pending_reminder(cursor, med_id, scheduled, reminder)

        elif stype == 'interval_from_wake':
            # Every X hours from wake time
            interval_hours = data.get('interval_hours', 4.0)
            interval = timedelta(hours=interval_hours)

            # First dose immediately on wake
            scheduled = wake_time
            reminder = wake_time
            _add_pending_reminder(cursor, med_id, scheduled, reminder)

            # Subsequent doses every interval
            # Assume 16-hour wake window (will stop when user logs sleep)
            max_wake_hours = 18
            current = wake_time + interval
            end_of_day = wake_time + timedelta(hours=max_wake_hours)

            while current <= end_of_day:
                # Reminder 5 minutes before
                reminder = current - timedelta(minutes=5)
                _add_pending_reminder(cursor, med_id, current, reminder)
                current += interval

        elif stype == 'mid_day':
            # Approximate mid-day (6 hours after wake)
            scheduled = wake_time + timedelta(hours=6)
            reminder = scheduled - timedelta(minutes=5)
            _add_pending_reminder(cursor, med_id, scheduled, reminder)

    conn.commit()
    conn.close()


def _add_pending_reminder(cursor, medication_id: int, scheduled_time: datetime,
                          reminder_time: datetime):
    """Helper to add a pending reminder."""
    cursor.execute(
        """INSERT INTO pending_reminders
           (medication_id, scheduled_time, reminder_time)
           VALUES (?, ?, ?)""",
        (medication_id, scheduled_time, reminder_time)
    )


def get_pending_reminders() -> list:
    """
    Get all pending (unsent) reminders.

    Returns:
        List of pending reminders with medication info
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT pr.*, m.name as medication_name, m.dosage
           FROM pending_reminders pr
           JOIN medications m ON pr.medication_id = m.id
           WHERE pr.sent = 0
           ORDER BY pr.reminder_time"""
    )

    rows = cursor.fetchall()
    conn.close()

    reminders = []
    for row in rows:
        reminders.append({
            'id': row['id'],
            'medication_id': row['medication_id'],
            'medication_name': row['medication_name'],
            'dosage': row['dosage'],
            'scheduled_time': datetime.fromisoformat(row['scheduled_time']) if isinstance(row['scheduled_time'], str) else row['scheduled_time'],
            'reminder_time': datetime.fromisoformat(row['reminder_time']) if isinstance(row['reminder_time'], str) else row['reminder_time'],
            'sent': row['sent'],
            'followup_sent': row['followup_sent'],
        })

    return reminders


def get_due_reminders() -> list:
    """
    Get reminders that are due to be sent now.

    Returns:
        List of reminders where reminder_time <= now and not yet sent
    """
    now = datetime.now()
    pending = get_pending_reminders()

    return [r for r in pending if r['reminder_time'] <= now and not r['sent']]


def mark_reminder_sent(reminder_id: int) -> bool:
    """Mark a reminder as sent."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE pending_reminders SET sent = 1 WHERE id = ?",
        (reminder_id,)
    )

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def get_overdue_reminders(minutes: int = 15) -> list:
    """
    Get reminders that are overdue (medication not logged within X minutes).

    Args:
        minutes: Minutes past scheduled time to consider overdue

    Returns:
        List of overdue reminders needing follow-up
    """
    from .models import get_doses_today

    now = datetime.now()
    cutoff = now - timedelta(minutes=minutes)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT pr.*, m.name as medication_name, m.dosage
           FROM pending_reminders pr
           JOIN medications m ON pr.medication_id = m.id
           WHERE pr.sent = 1 AND pr.followup_sent = 0
             AND pr.scheduled_time <= ?
           ORDER BY pr.scheduled_time""",
        (cutoff,)
    )

    rows = cursor.fetchall()
    conn.close()

    overdue = []
    for row in rows:
        med_id = row['medication_id']
        scheduled = datetime.fromisoformat(row['scheduled_time']) if isinstance(row['scheduled_time'], str) else row['scheduled_time']

        # Check if dose was logged near the scheduled time
        today_doses = get_doses_today(med_id)
        dose_logged = False

        for dose in today_doses:
            dose_time = datetime.fromisoformat(dose['taken_time'])
            # Consider logged if within 30 minutes of scheduled
            if abs((dose_time - scheduled).total_seconds()) < 1800:
                dose_logged = True
                break

        if not dose_logged:
            overdue.append({
                'id': row['id'],
                'medication_id': med_id,
                'medication_name': row['medication_name'],
                'dosage': row['dosage'],
                'scheduled_time': scheduled,
            })

    return overdue


def mark_followup_sent(reminder_id: int) -> bool:
    """Mark a followup reminder as sent."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE pending_reminders SET followup_sent = 1 WHERE id = ?",
        (reminder_id,)
    )

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


# ============================================================
# SCHEDULE TIME CALCULATIONS (for compatibility)
# ============================================================

def get_scheduled_times_for_today(medication_id: int) -> list:
    """
    Get all scheduled dose times for a medication today.

    Uses wake time if available, otherwise falls back to fixed times.

    Args:
        medication_id: The medication's database ID

    Returns:
        List of datetime objects for today's scheduled doses
    """
    schedule = get_schedule(medication_id)
    if not schedule:
        return []

    today = date.today()
    times = []
    wake = get_last_wake_event()

    stype = schedule['schedule_type']
    data = schedule['times_data']

    if stype == 'on_wake':
        if wake:
            times.append(wake['event_time'])

    elif stype == 'interval_from_wake':
        if wake:
            interval_hours = data.get('interval_hours', 4.0)
            interval = timedelta(hours=interval_hours)

            wake_time = wake['event_time']
            current = wake_time
            end_of_day = datetime.combine(today, time(23, 59))

            while current <= end_of_day:
                times.append(current)
                current += interval

    elif stype == 'mid_day':
        if wake:
            times.append(wake['event_time'] + timedelta(hours=6))
        else:
            times.append(datetime.combine(today, time(12, 0)))

    elif stype == 'fixed':
        # Fixed times: ["08:00", "14:00", "20:00"]
        for time_str in data.get('times', []):
            hour, minute = map(int, time_str.split(':'))
            times.append(datetime.combine(today, time(hour, minute)))

    # PRN and monthly_injection have no daily times

    return sorted(times)


def get_next_scheduled_dose(medication_id: int) -> Optional[datetime]:
    """
    Get the next scheduled dose time for a medication.

    Returns:
        The next scheduled datetime, or None if no upcoming dose today
    """
    times = get_scheduled_times_for_today(medication_id)
    now = datetime.now()

    for dose_time in times:
        if dose_time > now:
            return dose_time

    return None


# ============================================================
# SCHEDULE FORMATTING
# ============================================================

def format_schedule(schedule: dict) -> str:
    """
    Format a schedule for display.

    Args:
        schedule: Schedule dict from get_schedule()

    Returns:
        Human-readable schedule description
    """
    if not schedule:
        return "No schedule set"

    stype = schedule['schedule_type']
    data = schedule['times_data']

    if stype == 'on_wake':
        return "Once on waking"

    elif stype == 'interval_from_wake':
        hours = data.get('interval_hours', 4.0)
        if hours == int(hours):
            return f"Every {int(hours)} hours after waking"
        else:
            return f"Every {hours} hours after waking"

    elif stype == 'mid_day':
        return "Once mid-day"

    elif stype == 'night_wake':
        return "Once if waking at night"

    elif stype == 'monthly_injection':
        months = data.get('months', 1)
        if months == 1:
            return "Injection every month"
        return f"Injection every {months} months"

    elif stype == 'fixed':
        times_list = data.get('times', [])
        if not times_list:
            return "Fixed schedule (no times set)"
        formatted = []
        for t in times_list:
            hour, minute = map(int, t.split(':'))
            dt = time(hour, minute)
            formatted.append(dt.strftime("%I:%M %p").lstrip('0'))
        return f"Daily at: {', '.join(formatted)}"

    elif stype == 'prn':
        return "As needed (PRN)"

    return "Unknown schedule type"


def format_schedule_status(medication_id: int) -> str:
    """
    Format the current status of a medication schedule.

    Returns:
        Status string including next dose time
    """
    schedule = get_schedule(medication_id)
    if not schedule:
        return "No schedule"

    status = format_schedule(schedule)

    # Add reminder status
    if not schedule.get('reminders_enabled', True):
        status += " (reminders off)"

    # Add next dose time if applicable
    next_dose = get_next_scheduled_dose(medication_id)
    if next_dose:
        time_str = next_dose.strftime("%I:%M %p").lstrip('0')
        status += f"\nNext dose: {time_str}"

    return status
