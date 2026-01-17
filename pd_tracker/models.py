"""
Data models and helper functions for PD Tracker.

This module provides functions to:
- Add, update, and retrieve medications
- Log doses taken
- Check medication status ("Did I take my meds?")

Each function handles its own database connection to keep things simple.
"""

from datetime import datetime, date, timedelta
from typing import Optional
from .database import get_connection


# ============================================================
# MEDICATION FUNCTIONS
# ============================================================

def add_medication(name: str, dosage: str = None, instructions: str = None) -> int:
    """
    Add a new medication to track.

    Args:
        name: Name of the medication (e.g., "Levodopa", "Pramipexole")
        dosage: Dosage amount (e.g., "100mg", "1 tablet")
        instructions: Special instructions (e.g., "Take with food")

    Returns:
        The ID of the newly created medication

    Example:
        med_id = add_medication("Levodopa", "100mg/25mg", "Take with protein-free snack")
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO medications (name, dosage, instructions) VALUES (?, ?, ?)",
        (name, dosage, instructions)
    )

    med_id = cursor.lastrowid  # Get the ID of the row we just inserted
    conn.commit()
    conn.close()

    return med_id


def get_all_medications(active_only: bool = True) -> list:
    """
    Get all medications.

    Args:
        active_only: If True, only return medications you're currently taking

    Returns:
        List of medication records (as dict-like Row objects)
    """
    conn = get_connection()
    cursor = conn.cursor()

    if active_only:
        cursor.execute("SELECT * FROM medications WHERE active = 1 ORDER BY name")
    else:
        cursor.execute("SELECT * FROM medications ORDER BY name")

    medications = cursor.fetchall()
    conn.close()

    return medications


def get_medication_by_name(name: str) -> Optional[dict]:
    """
    Find a medication by name (case-insensitive partial match).

    Args:
        name: Full or partial medication name

    Returns:
        The medication record, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    # LIKE with % does a partial match, LOWER() makes it case-insensitive
    cursor.execute(
        "SELECT * FROM medications WHERE LOWER(name) LIKE LOWER(?) AND active = 1",
        (f"%{name}%",)
    )

    medication = cursor.fetchone()
    conn.close()

    return medication


def get_medication_by_id(med_id: int) -> Optional[dict]:
    """
    Get a medication by its ID.

    Args:
        med_id: The medication's database ID

    Returns:
        The medication record, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM medications WHERE id = ?", (med_id,))
    medication = cursor.fetchone()
    conn.close()

    return medication


def update_medication(med_id: int, name: str = None, dosage: str = None,
                      instructions: str = None, active: bool = None) -> bool:
    """
    Update a medication's details.

    Only updates fields that are provided (not None).

    Args:
        med_id: The medication's database ID
        name: New name (optional)
        dosage: New dosage (optional)
        instructions: New instructions (optional)
        active: Whether medication is active (optional)

    Returns:
        True if update was successful, False if medication not found
    """
    # Build the UPDATE query dynamically based on what's provided
    updates = []
    values = []

    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if dosage is not None:
        updates.append("dosage = ?")
        values.append(dosage)
    if instructions is not None:
        updates.append("instructions = ?")
        values.append(instructions)
    if active is not None:
        updates.append("active = ?")
        values.append(1 if active else 0)

    if not updates:
        return False  # Nothing to update

    values.append(med_id)

    conn = get_connection()
    cursor = conn.cursor()

    query = f"UPDATE medications SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)

    success = cursor.rowcount > 0  # rowcount tells us if any rows were affected
    conn.commit()
    conn.close()

    return success


def deactivate_medication(med_id: int) -> bool:
    """
    Mark a medication as inactive (stop tracking, but keep history).

    This is better than deleting because you preserve your dose history.

    Args:
        med_id: The medication's database ID

    Returns:
        True if successful, False if medication not found
    """
    return update_medication(med_id, active=False)


# ============================================================
# DOSE LOGGING FUNCTIONS
# ============================================================

def log_dose(medication_id: int, taken_time: datetime = None,
             scheduled_time: datetime = None, notes: str = None) -> int:
    """
    Record that a medication dose was taken.

    Args:
        medication_id: The medication's database ID
        taken_time: When the dose was taken (defaults to now)
        scheduled_time: When it was scheduled (optional)
        notes: Any notes about this dose

    Returns:
        The ID of the dose record
    """
    if taken_time is None:
        taken_time = datetime.now()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO doses_taken
           (medication_id, taken_time, scheduled_time, notes)
           VALUES (?, ?, ?, ?)""",
        (medication_id, taken_time, scheduled_time, notes)
    )

    dose_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return dose_id


def log_skipped_dose(medication_id: int, scheduled_time: datetime = None,
                     notes: str = None) -> int:
    """
    Record that a scheduled dose was skipped.

    Args:
        medication_id: The medication's database ID
        scheduled_time: When it was scheduled
        notes: Reason for skipping

    Returns:
        The ID of the dose record
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO doses_taken
           (medication_id, scheduled_time, skipped, notes)
           VALUES (?, ?, 1, ?)""",
        (medication_id, scheduled_time, notes)
    )

    dose_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return dose_id


def get_doses_today(medication_id: int = None) -> list:
    """
    Get all doses taken today.

    Args:
        medication_id: Optional - filter to specific medication

    Returns:
        List of dose records with medication names
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get the start of today
    today_start = datetime.combine(date.today(), datetime.min.time())

    if medication_id:
        cursor.execute(
            """SELECT d.*, m.name as medication_name, m.dosage
               FROM doses_taken d
               JOIN medications m ON d.medication_id = m.id
               WHERE d.medication_id = ? AND d.taken_time >= ?
               ORDER BY d.taken_time DESC""",
            (medication_id, today_start)
        )
    else:
        cursor.execute(
            """SELECT d.*, m.name as medication_name, m.dosage
               FROM doses_taken d
               JOIN medications m ON d.medication_id = m.id
               WHERE d.taken_time >= ?
               ORDER BY d.taken_time DESC""",
            (today_start,)
        )

    doses = cursor.fetchall()
    conn.close()

    return doses


def get_last_dose(medication_id: int) -> Optional[dict]:
    """
    Get the most recent dose of a specific medication.

    Args:
        medication_id: The medication's database ID

    Returns:
        The most recent dose record, or None if never taken
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT d.*, m.name as medication_name
           FROM doses_taken d
           JOIN medications m ON d.medication_id = m.id
           WHERE d.medication_id = ? AND d.skipped = 0
           ORDER BY d.taken_time DESC
           LIMIT 1""",
        (medication_id,)
    )

    dose = cursor.fetchone()
    conn.close()

    return dose


def get_medication_status_today() -> list:
    """
    Get today's medication status - what you've taken and when.

    This powers the "Did I take my meds?" feature.

    Returns:
        List of dicts with medication info and today's doses
    """
    medications = get_all_medications(active_only=True)
    today_doses = get_doses_today()

    # Group doses by medication
    doses_by_med = {}
    for dose in today_doses:
        med_id = dose['medication_id']
        if med_id not in doses_by_med:
            doses_by_med[med_id] = []
        doses_by_med[med_id].append(dose)

    # Build status for each medication
    status = []
    for med in medications:
        med_doses = doses_by_med.get(med['id'], [])

        # Calculate time since last dose
        last_dose = None
        time_since = None
        if med_doses:
            last_dose = med_doses[0]  # Most recent (already sorted DESC)
            last_time = datetime.fromisoformat(last_dose['taken_time'])
            time_since = datetime.now() - last_time

        status.append({
            'id': med['id'],
            'name': med['name'],
            'dosage': med['dosage'],
            'doses_today': len(med_doses),
            'last_dose_time': last_dose['taken_time'] if last_dose else None,
            'time_since_last': time_since,
            'dose_times': [d['taken_time'] for d in med_doses]
        })

    return status


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_dose_by_id(dose_id: int) -> Optional[dict]:
    """
    Get a dose record by its ID.

    Args:
        dose_id: The dose record's database ID

    Returns:
        The dose record with medication info, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT d.*, m.name as medication_name, m.dosage
           FROM doses_taken d
           JOIN medications m ON d.medication_id = m.id
           WHERE d.id = ?""",
        (dose_id,)
    )

    dose = cursor.fetchone()
    conn.close()

    return dose


def update_dose(dose_id: int, taken_time: datetime = None,
                scheduled_time: datetime = None, notes: str = None,
                skipped: bool = None) -> bool:
    """
    Update a dose record.

    Args:
        dose_id: The dose record's database ID
        taken_time: New taken time (optional)
        scheduled_time: New scheduled time (optional)
        notes: New notes (optional)
        skipped: New skipped status (optional)

    Returns:
        True if update was successful, False if dose not found
    """
    updates = []
    values = []

    if taken_time is not None:
        updates.append("taken_time = ?")
        values.append(taken_time)
    if scheduled_time is not None:
        updates.append("scheduled_time = ?")
        values.append(scheduled_time)
    if notes is not None:
        updates.append("notes = ?")
        values.append(notes)
    if skipped is not None:
        updates.append("skipped = ?")
        values.append(1 if skipped else 0)

    if not updates:
        return False

    values.append(dose_id)

    conn = get_connection()
    cursor = conn.cursor()

    query = f"UPDATE doses_taken SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def delete_dose(dose_id: int) -> bool:
    """
    Delete a dose record.

    Args:
        dose_id: The dose record's database ID

    Returns:
        True if deletion was successful, False if dose not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM doses_taken WHERE id = ?", (dose_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def get_doses_range(start_date: date, end_date: date = None,
                    medication_id: int = None) -> list:
    """
    Get all doses in a date range.

    Args:
        start_date: Start of range
        end_date: End of range (defaults to today)
        medication_id: Optional - filter to specific medication

    Returns:
        List of dose records with medication names
    """
    if end_date is None:
        end_date = date.today()

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    conn = get_connection()
    cursor = conn.cursor()

    if medication_id:
        cursor.execute(
            """SELECT d.*, m.name as medication_name, m.dosage
               FROM doses_taken d
               JOIN medications m ON d.medication_id = m.id
               WHERE d.medication_id = ? AND d.taken_time BETWEEN ? AND ?
               ORDER BY d.taken_time DESC""",
            (medication_id, start_dt, end_dt)
        )
    else:
        cursor.execute(
            """SELECT d.*, m.name as medication_name, m.dosage
               FROM doses_taken d
               JOIN medications m ON d.medication_id = m.id
               WHERE d.taken_time BETWEEN ? AND ?
               ORDER BY d.taken_time DESC""",
            (start_dt, end_dt)
        )

    doses = cursor.fetchall()
    conn.close()

    return doses


def format_timedelta(td: timedelta) -> str:
    """
    Format a timedelta into a human-readable string.

    Args:
        td: A timedelta object

    Returns:
        String like "2h 30m ago" or "45m ago"
    """
    if td is None:
        return "never"

    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m ago"
    elif minutes > 0:
        return f"{minutes}m ago"
    else:
        return "just now"
