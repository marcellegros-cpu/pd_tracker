"""
Exercise tracking for PD Tracker.

Tracks physical activity including:
- Exercise type (walking, cycling, PT exercises, etc.)
- Start time
- Duration (in minutes)
- Intensity (light, moderate, vigorous)
- Notes

Exercise is particularly important for PD management as it can
help with symptoms and overall quality of life.
"""

from datetime import datetime, date, timedelta
from typing import Optional
from .database import get_connection


# Common exercise types for quick selection
COMMON_EXERCISES = [
    'Walking',
    'Cycling',
    'Swimming',
    'Physical Therapy',
    'Stretching',
    'Yoga',
    'Tai Chi',
    'Strength Training',
    'Dance',
    'Boxing/Rock Steady',
    'Treadmill',
    'Stationary Bike',
    'Other',
]

# Intensity levels
INTENSITY_LEVELS = ['light', 'moderate', 'vigorous']


def log_exercise(
    exercise_type: str,
    duration_minutes: int,
    intensity: str = 'moderate',
    start_time: datetime = None,
    notes: str = None,
) -> int:
    """
    Log an exercise session.

    Args:
        exercise_type: What exercise (e.g., "Walking", "Physical Therapy")
        duration_minutes: How long in minutes
        intensity: 'light', 'moderate', or 'vigorous'
        start_time: When the exercise started (defaults to now minus duration)
        notes: Optional notes

    Returns:
        The ID of the new exercise record
    """
    if start_time is None:
        # Default to "just finished" - start time is now minus duration
        start_time = datetime.now() - timedelta(minutes=duration_minutes)

    # Normalize intensity
    intensity = intensity.lower()
    if intensity not in INTENSITY_LEVELS:
        intensity = 'moderate'

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO exercise_logs
           (exercise_type, start_time, duration_minutes, intensity, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (exercise_type, start_time, duration_minutes, intensity, notes)
    )

    exercise_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return exercise_id


def get_exercise_today() -> list:
    """
    Get all exercise logged today.

    Returns:
        List of exercise records, most recent first
    """
    conn = get_connection()
    cursor = conn.cursor()

    today_start = datetime.combine(date.today(), datetime.min.time())

    cursor.execute(
        """SELECT * FROM exercise_logs
           WHERE start_time >= ?
           ORDER BY start_time DESC""",
        (today_start,)
    )

    records = cursor.fetchall()
    conn.close()

    return records


def get_exercise_logs(days: int = 7) -> list:
    """
    Get exercise logs for the past N days.

    Args:
        days: Number of days to look back

    Returns:
        List of exercise records, most recent first
    """
    conn = get_connection()
    cursor = conn.cursor()

    start_date = datetime.now() - timedelta(days=days)

    cursor.execute(
        """SELECT * FROM exercise_logs
           WHERE start_time >= ?
           ORDER BY start_time DESC""",
        (start_date,)
    )

    records = cursor.fetchall()
    conn.close()

    return records


def get_exercise_by_id(exercise_id: int) -> Optional[dict]:
    """
    Get an exercise record by its ID.

    Args:
        exercise_id: The exercise record's database ID

    Returns:
        The exercise record, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM exercise_logs WHERE id = ?", (exercise_id,))
    record = cursor.fetchone()
    conn.close()

    return record


def update_exercise(exercise_id: int, exercise_type: str = None, start_time: datetime = None,
                    duration_minutes: int = None, intensity: str = None,
                    notes: str = None) -> bool:
    """
    Update an exercise record.

    Args:
        exercise_id: The exercise record's database ID
        exercise_type: New exercise type (optional)
        start_time: New start time (optional)
        duration_minutes: New duration (optional)
        intensity: New intensity (optional)
        notes: New notes (optional)

    Returns:
        True if update was successful, False if exercise record not found
    """
    updates = []
    values = []

    if exercise_type is not None:
        updates.append("exercise_type = ?")
        values.append(exercise_type)
    if start_time is not None:
        updates.append("start_time = ?")
        values.append(start_time)
    if duration_minutes is not None:
        updates.append("duration_minutes = ?")
        values.append(duration_minutes)
    if intensity is not None:
        updates.append("intensity = ?")
        values.append(intensity.lower())
    if notes is not None:
        updates.append("notes = ?")
        values.append(notes)

    if not updates:
        return False

    values.append(exercise_id)

    conn = get_connection()
    cursor = conn.cursor()

    query = f"UPDATE exercise_logs SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def delete_exercise(exercise_id: int) -> bool:
    """
    Delete an exercise record.

    Args:
        exercise_id: The exercise record's database ID

    Returns:
        True if deletion was successful, False if exercise record not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM exercise_logs WHERE id = ?", (exercise_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def get_exercise_stats(days: int = 7) -> dict:
    """
    Calculate exercise statistics for the past N days.

    Args:
        days: Number of days to analyze

    Returns:
        Dict with total_minutes, total_sessions, avg_per_day, by_type
    """
    logs = get_exercise_logs(days)

    if not logs:
        return {
            'total_minutes': 0,
            'total_sessions': 0,
            'avg_minutes_per_day': 0,
            'by_type': {},
            'by_intensity': {'light': 0, 'moderate': 0, 'vigorous': 0},
        }

    total_minutes = sum(l['duration_minutes'] for l in logs)

    # Group by type
    by_type = {}
    for log in logs:
        etype = log['exercise_type']
        if etype not in by_type:
            by_type[etype] = {'sessions': 0, 'minutes': 0}
        by_type[etype]['sessions'] += 1
        by_type[etype]['minutes'] += log['duration_minutes']

    # Group by intensity
    by_intensity = {'light': 0, 'moderate': 0, 'vigorous': 0}
    for log in logs:
        intensity = log['intensity'] or 'moderate'
        if intensity in by_intensity:
            by_intensity[intensity] += log['duration_minutes']

    return {
        'total_minutes': total_minutes,
        'total_sessions': len(logs),
        'avg_minutes_per_day': round(total_minutes / days, 1),
        'by_type': by_type,
        'by_intensity': by_intensity,
    }


def get_today_stats() -> dict:
    """
    Get exercise stats for today only.

    Returns:
        Dict with total_minutes, sessions, types
    """
    logs = get_exercise_today()

    total_minutes = sum(l['duration_minutes'] for l in logs)
    types = list(set(l['exercise_type'] for l in logs))

    return {
        'total_minutes': total_minutes,
        'sessions': len(logs),
        'types': types,
    }


def format_exercise_entry(log: dict) -> str:
    """
    Format an exercise entry for display.

    Args:
        log: Exercise record from database

    Returns:
        Formatted string
    """
    lines = []

    start_time = datetime.fromisoformat(log['start_time'])
    lines.append(f"  {start_time.strftime('%a, %b %d')} at {start_time.strftime('%I:%M %p').lstrip('0')}")
    lines.append(f"    Type: {log['exercise_type']}")
    lines.append(f"    Duration: {log['duration_minutes']} minutes")
    lines.append(f"    Intensity: {log['intensity'].capitalize()}")

    if log['notes']:
        lines.append(f"    Notes: {log['notes']}")

    return '\n'.join(lines)


def format_duration_friendly(minutes: int) -> str:
    """
    Format minutes into a friendly string.

    Args:
        minutes: Duration in minutes

    Returns:
        String like "1h 30m" or "45m"
    """
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        if mins > 0:
            return f"{hours}h {mins}m"
        return f"{hours}h"
    return f"{minutes}m"
