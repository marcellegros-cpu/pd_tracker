"""
Symptom tracking for PD Tracker.

Tracks Parkinson's disease symptoms including:
- On/Off state (medication effectiveness)
- Overall severity (1-10)
- Specific symptoms: tremor, rigidity, bradykinesia, dyskinesia, freezing, balance
- Free-form notes

Each symptom can be rated 0-10 where 0 means not present.
"""

from datetime import datetime, date, timedelta
from typing import Optional
from .database import get_connection


# Standard PD symptoms with descriptions
SYMPTOM_DESCRIPTIONS = {
    'tremor': 'Shaking or trembling, usually at rest',
    'rigidity': 'Muscle stiffness or tightness',
    'bradykinesia': 'Slowness of movement',
    'dyskinesia': 'Involuntary movements (often from medication)',
    'freezing': 'Sudden inability to move, feet stuck to floor',
    'balance': 'Balance problems or unsteadiness',
}


def log_symptom(
    on_off_state: str = None,
    severity: int = None,
    tremor: int = 0,
    rigidity: int = 0,
    bradykinesia: int = 0,
    dyskinesia: int = 0,
    freezing: int = 0,
    balance: int = 0,
    notes: str = None,
    timestamp: datetime = None,
) -> int:
    """
    Log a symptom entry.

    Args:
        on_off_state: 'on', 'off', or 'transitioning'
        severity: Overall severity 1-10
        tremor: Tremor severity 0-10
        rigidity: Rigidity severity 0-10
        bradykinesia: Bradykinesia severity 0-10
        dyskinesia: Dyskinesia severity 0-10
        freezing: Freezing severity 0-10
        balance: Balance issues severity 0-10
        notes: Free-form notes
        timestamp: When symptoms occurred (defaults to now)

    Returns:
        The ID of the new symptom record
    """
    if timestamp is None:
        timestamp = datetime.now()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO symptoms
           (timestamp, on_off_state, severity, tremor, rigidity,
            bradykinesia, dyskinesia, freezing, balance, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (timestamp, on_off_state, severity, tremor, rigidity,
         bradykinesia, dyskinesia, freezing, balance, notes)
    )

    symptom_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return symptom_id


def log_quick_state(on_off_state: str, notes: str = None) -> int:
    """
    Quick log of just on/off state.

    Args:
        on_off_state: 'on', 'off', or 'transitioning'
        notes: Optional notes

    Returns:
        The ID of the new symptom record
    """
    return log_symptom(on_off_state=on_off_state, notes=notes)


def get_symptoms_today() -> list:
    """
    Get all symptom entries for today.

    Returns:
        List of symptom records, most recent first
    """
    conn = get_connection()
    cursor = conn.cursor()

    today_start = datetime.combine(date.today(), datetime.min.time())

    cursor.execute(
        """SELECT * FROM symptoms
           WHERE timestamp >= ?
           ORDER BY timestamp DESC""",
        (today_start,)
    )

    symptoms = cursor.fetchall()
    conn.close()

    return symptoms


def get_symptoms_range(start_date: date, end_date: date = None) -> list:
    """
    Get symptom entries for a date range.

    Args:
        start_date: Start of range
        end_date: End of range (defaults to today)

    Returns:
        List of symptom records
    """
    if end_date is None:
        end_date = date.today()

    conn = get_connection()
    cursor = conn.cursor()

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    cursor.execute(
        """SELECT * FROM symptoms
           WHERE timestamp >= ? AND timestamp < ?
           ORDER BY timestamp DESC""",
        (start_dt, end_dt)
    )

    symptoms = cursor.fetchall()
    conn.close()

    return symptoms


def get_latest_symptom() -> Optional[dict]:
    """
    Get the most recent symptom entry.

    Returns:
        The most recent symptom record, or None
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM symptoms ORDER BY timestamp DESC LIMIT 1"
    )

    symptom = cursor.fetchone()
    conn.close()

    return symptom


def get_on_off_summary_today() -> dict:
    """
    Get a summary of on/off states for today.

    Returns:
        Dict with counts of each state
    """
    symptoms = get_symptoms_today()

    summary = {
        'on': 0,
        'off': 0,
        'transitioning': 0,
        'total_entries': len(symptoms),
        'last_state': None,
        'last_time': None,
    }

    for s in symptoms:
        state = s['on_off_state']
        if state in summary:
            summary[state] += 1

    if symptoms:
        summary['last_state'] = symptoms[0]['on_off_state']
        summary['last_time'] = symptoms[0]['timestamp']

    return summary


def get_symptom_by_id(symptom_id: int) -> Optional[dict]:
    """
    Get a symptom entry by its ID.

    Args:
        symptom_id: The symptom record's database ID

    Returns:
        The symptom record, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM symptoms WHERE id = ?", (symptom_id,))
    symptom = cursor.fetchone()
    conn.close()

    return symptom


def update_symptom(symptom_id: int, **kwargs) -> bool:
    """
    Update a symptom entry.

    Args:
        symptom_id: The symptom record's database ID
        **kwargs: Fields to update (timestamp, on_off_state, severity, tremor,
                  rigidity, bradykinesia, dyskinesia, freezing, balance, notes)

    Returns:
        True if update was successful, False if symptom not found
    """
    valid_fields = {'timestamp', 'on_off_state', 'severity', 'tremor', 'rigidity',
                    'bradykinesia', 'dyskinesia', 'freezing', 'balance', 'notes'}

    updates = []
    values = []

    for field, value in kwargs.items():
        if field in valid_fields and value is not None:
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        return False

    values.append(symptom_id)

    conn = get_connection()
    cursor = conn.cursor()

    query = f"UPDATE symptoms SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def delete_symptom(symptom_id: int) -> bool:
    """
    Delete a symptom entry.

    Args:
        symptom_id: The symptom record's database ID

    Returns:
        True if deletion was successful, False if symptom not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM symptoms WHERE id = ?", (symptom_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def format_symptom_entry(symptom: dict) -> str:
    """
    Format a symptom entry for display.

    Args:
        symptom: Symptom record from database

    Returns:
        Formatted string
    """
    lines = []

    # Time
    ts = datetime.fromisoformat(symptom['timestamp'])
    lines.append(f"  {ts.strftime('%I:%M %p').lstrip('0')} - {ts.strftime('%b %d')}")

    # On/Off state
    state = symptom['on_off_state']
    if state:
        state_display = {'on': 'ON', 'off': 'OFF', 'transitioning': 'Transitioning'}
        lines.append(f"    State: {state_display.get(state, state)}")

    # Severity
    if symptom['severity']:
        lines.append(f"    Severity: {symptom['severity']}/10")

    # Individual symptoms (only show non-zero)
    symptom_names = ['tremor', 'rigidity', 'bradykinesia', 'dyskinesia', 'freezing', 'balance']
    active_symptoms = []
    for name in symptom_names:
        value = symptom[name]
        if value and value > 0:
            active_symptoms.append(f"{name.capitalize()}: {value}")

    if active_symptoms:
        lines.append(f"    Symptoms: {', '.join(active_symptoms)}")

    # Notes
    if symptom['notes']:
        lines.append(f"    Notes: {symptom['notes']}")

    return '\n'.join(lines)
