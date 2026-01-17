"""
Database connection and initialization for PD Tracker.

This module handles:
- Connecting to the SQLite database
- Creating tables if they don't exist
- Providing a connection for other modules to use
"""

import sqlite3
from pathlib import Path


# Where to store the database file
# Path(__file__) gets the location of THIS file (database.py)
# .parent goes up one folder, then up again to get to pd_tracker root
# Then we go into the 'data' folder
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "pd_tracker.db"


def get_connection():
    """
    Get a connection to the database.

    Returns a sqlite3 Connection object that you can use to run queries.

    Example usage:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM medications")
        rows = cursor.fetchall()
        conn.close()
    """
    # Make sure the data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Connect to database (creates file if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)

    # This makes rows return as dict-like objects instead of plain tuples
    # So you can access columns by name: row['name'] instead of row[0]
    conn.row_factory = sqlite3.Row

    return conn


def init_database():
    """
    Create all the database tables if they don't exist.

    This is safe to run multiple times - it won't delete existing data.
    The 'IF NOT EXISTS' part of each CREATE TABLE ensures that.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ============================================================
    # MEDICATIONS TABLE
    # Stores information about each medication you take
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dosage TEXT,
            instructions TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ============================================================
    # MEDICATION SCHEDULES TABLE
    # Each medication can have a schedule for when to take it
    # schedule_type options:
    #   - 'on_wake': Take once on waking
    #   - 'interval_from_wake': Take every X hours after waking (until sleep)
    #   - 'mid_day': Take once mid-day
    #   - 'night_wake': Take once if waking during the night
    #   - 'monthly_injection': Take once every X months
    #   - 'fixed': Specific times each day (legacy)
    #   - 'prn': As needed (no reminders)
    # times: JSON with schedule details
    # reminders_enabled: Toggle for SMS/email reminders
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medication_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            schedule_type TEXT NOT NULL,
            times TEXT,
            active INTEGER DEFAULT 1,
            reminders_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (medication_id) REFERENCES medications (id)
        )
    """)

    # ============================================================
    # WAKE/SLEEP TRACKING TABLE
    # Tracks when the user wakes up and goes to sleep
    # Used to calculate wake-based medication schedules
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wake_sleep_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)

    # ============================================================
    # PENDING REMINDERS TABLE
    # Tracks scheduled reminders that need to be sent
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            scheduled_time TIMESTAMP NOT NULL,
            reminder_time TIMESTAMP NOT NULL,
            sent INTEGER DEFAULT 0,
            followup_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (medication_id) REFERENCES medications (id)
        )
    """)

    # ============================================================
    # DOSES TAKEN TABLE
    # Records every time you take (or skip) a medication
    # This is the core tracking data for medication adherence
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doses_taken (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            scheduled_time TIMESTAMP,
            taken_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            skipped INTEGER DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (medication_id) REFERENCES medications (id)
        )
    """)

    # ============================================================
    # SYMPTOMS TABLE
    # Tracks your PD symptoms over time
    # on_off_state: 'on', 'off', or 'transitioning'
    # Individual symptom scores are 0-10 (0 = not present)
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS symptoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            on_off_state TEXT,
            severity INTEGER,
            tremor INTEGER DEFAULT 0,
            rigidity INTEGER DEFAULT 0,
            bradykinesia INTEGER DEFAULT 0,
            dyskinesia INTEGER DEFAULT 0,
            freezing INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0,
            notes TEXT
        )
    """)

    # ============================================================
    # SLEEP LOGS TABLE
    # Tracks your sleep patterns
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sleep_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sleep_time TIMESTAMP,
            wake_time TIMESTAMP,
            quality INTEGER,
            notes TEXT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ============================================================
    # EXERCISE LOGS TABLE
    # Tracks your physical activity
    # intensity: 'light', 'moderate', 'vigorous'
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exercise_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_type TEXT NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_minutes INTEGER,
            intensity TEXT,
            notes TEXT
        )
    """)

    # ============================================================
    # EMAIL RECIPIENTS TABLE
    # Stores email addresses for report delivery
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    # ============================================================
    # MIGRATIONS - Add missing columns to existing tables
    # This handles upgrading older databases to the current schema
    # ============================================================
    def add_column_if_missing(table, column, definition):
        cursor.execute(f'PRAGMA table_info({table})')
        columns = [col[1] for col in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
            print(f"  Added column {column} to {table}")

    # medication_schedules migrations
    add_column_if_missing('medication_schedules', 'reminders_enabled', 'INTEGER DEFAULT 1')

    # Save all the changes
    conn.commit()
    conn.close()

    print(f"Database initialized at: {DB_PATH}")


# This runs when you execute this file directly: python database.py
# It won't run when you import this file from another module
if __name__ == "__main__":
    init_database()
