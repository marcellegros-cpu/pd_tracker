"""
Sleep tracking for PD Tracker.

Tracks sleep patterns including:
- Sleep time (when you went to bed)
- Wake time (when you got up)
- Sleep quality (1-10)
- Notes (interruptions, dreams, etc.)

Supports both real-time logging (log when you sleep/wake) and
manual entry for past sleep sessions.
"""

from datetime import datetime, date, timedelta
from typing import Optional
from .database import get_connection


def log_sleep_start(sleep_time: datetime = None, notes: str = None) -> int:
    """
    Log when you're going to sleep.

    Creates a partial sleep record that will be completed when you wake up.

    Args:
        sleep_time: When you went to sleep (defaults to now)
        notes: Optional notes

    Returns:
        The ID of the new sleep record
    """
    if sleep_time is None:
        sleep_time = datetime.now()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO sleep_logs (sleep_time, notes, logged_at)
           VALUES (?, ?, ?)""",
        (sleep_time, notes, datetime.now())
    )

    sleep_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return sleep_id


def log_wake(wake_time: datetime = None, quality: int = None, notes: str = None) -> Optional[int]:
    """
    Log when you woke up, completing the most recent sleep record.

    Args:
        wake_time: When you woke up (defaults to now)
        quality: Sleep quality 1-10
        notes: Optional notes (appended to existing notes)

    Returns:
        The ID of the updated sleep record, or None if no open sleep record
    """
    if wake_time is None:
        wake_time = datetime.now()

    conn = get_connection()
    cursor = conn.cursor()

    # Find the most recent sleep record without a wake time
    cursor.execute(
        """SELECT id, notes FROM sleep_logs
           WHERE wake_time IS NULL
           ORDER BY sleep_time DESC LIMIT 1"""
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    sleep_id = row['id']

    # Combine notes if both exist
    existing_notes = row['notes']
    if existing_notes and notes:
        combined_notes = f"{existing_notes}; Wake: {notes}"
    elif notes:
        combined_notes = notes
    else:
        combined_notes = existing_notes

    cursor.execute(
        """UPDATE sleep_logs
           SET wake_time = ?, quality = ?, notes = ?
           WHERE id = ?""",
        (wake_time, quality, combined_notes, sleep_id)
    )

    conn.commit()
    conn.close()

    return sleep_id


def log_sleep_session(
    sleep_time: datetime,
    wake_time: datetime,
    quality: int = None,
    notes: str = None
) -> int:
    """
    Log a complete sleep session (manual entry).

    Args:
        sleep_time: When you went to sleep
        wake_time: When you woke up
        quality: Sleep quality 1-10
        notes: Optional notes

    Returns:
        The ID of the new sleep record
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO sleep_logs (sleep_time, wake_time, quality, notes, logged_at)
           VALUES (?, ?, ?, ?, ?)""",
        (sleep_time, wake_time, quality, notes, datetime.now())
    )

    sleep_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return sleep_id


def get_open_sleep_record() -> Optional[dict]:
    """
    Get the current open sleep record (started but not completed).

    Returns:
        The open sleep record, or None if you're not currently "sleeping"
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT * FROM sleep_logs
           WHERE wake_time IS NULL
           ORDER BY sleep_time DESC LIMIT 1"""
    )

    record = cursor.fetchone()
    conn.close()

    return record


def get_last_sleep() -> Optional[dict]:
    """
    Get the most recent completed sleep record.

    Returns:
        The last complete sleep record, or None
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT * FROM sleep_logs
           WHERE wake_time IS NOT NULL
           ORDER BY wake_time DESC LIMIT 1"""
    )

    record = cursor.fetchone()
    conn.close()

    return record


def get_sleep_logs(days: int = 7) -> list:
    """
    Get sleep logs for the past N days.

    Args:
        days: Number of days to look back

    Returns:
        List of sleep records, most recent first
    """
    conn = get_connection()
    cursor = conn.cursor()

    start_date = datetime.now() - timedelta(days=days)

    cursor.execute(
        """SELECT * FROM sleep_logs
           WHERE sleep_time >= ?
           ORDER BY sleep_time DESC""",
        (start_date,)
    )

    records = cursor.fetchall()
    conn.close()

    return records


def get_sleep_range(start_date: date, end_date: date) -> list:
    """
    Get sleep logs for a specific date range.

    Args:
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        List of sleep records within the range, most recent first
    """
    conn = get_connection()
    cursor = conn.cursor()

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    cursor.execute(
        """SELECT * FROM sleep_logs
           WHERE sleep_time >= ? AND sleep_time < ?
           ORDER BY sleep_time DESC""",
        (start_dt, end_dt)
    )

    records = cursor.fetchall()
    conn.close()

    return records


def get_sleep_by_id(sleep_id: int) -> Optional[dict]:
    """
    Get a sleep record by its ID.

    Args:
        sleep_id: The sleep record's database ID

    Returns:
        The sleep record, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM sleep_logs WHERE id = ?", (sleep_id,))
    record = cursor.fetchone()
    conn.close()

    return record


def update_sleep(sleep_id: int, sleep_time: datetime = None, wake_time: datetime = None,
                 quality: int = None, notes: str = None) -> bool:
    """
    Update a sleep record.

    Args:
        sleep_id: The sleep record's database ID
        sleep_time: New sleep time (optional)
        wake_time: New wake time (optional)
        quality: New quality rating (optional)
        notes: New notes (optional)

    Returns:
        True if update was successful, False if sleep record not found
    """
    updates = []
    values = []

    if sleep_time is not None:
        updates.append("sleep_time = ?")
        values.append(sleep_time)
    if wake_time is not None:
        updates.append("wake_time = ?")
        values.append(wake_time)
    if quality is not None:
        updates.append("quality = ?")
        values.append(quality)
    if notes is not None:
        updates.append("notes = ?")
        values.append(notes)

    if not updates:
        return False

    values.append(sleep_id)

    conn = get_connection()
    cursor = conn.cursor()

    query = f"UPDATE sleep_logs SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def delete_sleep(sleep_id: int) -> bool:
    """
    Delete a sleep record.

    Args:
        sleep_id: The sleep record's database ID

    Returns:
        True if deletion was successful, False if sleep record not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM sleep_logs WHERE id = ?", (sleep_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def calculate_duration(sleep_time: datetime, wake_time: datetime) -> timedelta:
    """
    Calculate sleep duration.

    Args:
        sleep_time: When sleep started
        wake_time: When sleep ended

    Returns:
        Duration as timedelta
    """
    if isinstance(sleep_time, str):
        sleep_time = datetime.fromisoformat(sleep_time)
    if isinstance(wake_time, str):
        wake_time = datetime.fromisoformat(wake_time)

    return wake_time - sleep_time


def format_duration(td: timedelta) -> str:
    """
    Format a duration for display.

    Args:
        td: Duration as timedelta

    Returns:
        String like "7h 30m"
    """
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def get_sleep_stats(days: int = 7) -> dict:
    """
    Calculate sleep statistics for the past N days.

    Args:
        days: Number of days to analyze

    Returns:
        Dict with avg_duration, avg_quality, total_nights
    """
    logs = get_sleep_logs(days)

    # Filter to complete records only
    complete = [l for l in logs if l['wake_time'] is not None]

    if not complete:
        return {
            'avg_duration': None,
            'avg_quality': None,
            'total_nights': 0,
        }

    # Calculate durations
    durations = []
    qualities = []

    for log in complete:
        duration = calculate_duration(log['sleep_time'], log['wake_time'])
        durations.append(duration.total_seconds())

        if log['quality']:
            qualities.append(log['quality'])

    avg_duration_seconds = sum(durations) / len(durations)
    avg_duration = timedelta(seconds=avg_duration_seconds)

    avg_quality = sum(qualities) / len(qualities) if qualities else None

    return {
        'avg_duration': avg_duration,
        'avg_duration_formatted': format_duration(avg_duration),
        'avg_quality': round(avg_quality, 1) if avg_quality else None,
        'total_nights': len(complete),
    }


def format_sleep_entry(log: dict) -> str:
    """
    Format a sleep log entry for display.

    Args:
        log: Sleep record from database

    Returns:
        Formatted string
    """
    lines = []

    sleep_time = datetime.fromisoformat(log['sleep_time'])
    lines.append(f"  {sleep_time.strftime('%a, %b %d')}")
    lines.append(f"    Sleep: {sleep_time.strftime('%I:%M %p').lstrip('0')}")

    if log['wake_time']:
        wake_time = datetime.fromisoformat(log['wake_time'])
        duration = calculate_duration(sleep_time, wake_time)
        lines.append(f"    Wake:  {wake_time.strftime('%I:%M %p').lstrip('0')}")
        lines.append(f"    Duration: {format_duration(duration)}")
    else:
        lines.append(f"    Wake:  (still sleeping)")

    if log['quality']:
        lines.append(f"    Quality: {log['quality']}/10")

    if log['notes']:
        lines.append(f"    Notes: {log['notes']}")

    return '\n'.join(lines)
