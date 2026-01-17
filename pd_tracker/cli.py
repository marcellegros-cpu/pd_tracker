"""
Command-line interface for PD Tracker.

Usage:
    pd med add             - Add a new medication
    pd med list            - List all medications
    pd med take <name>     - Log that you took a medication
    pd med status          - Show today's medication status ("Did I take my meds?")
    pd med schedule <name> - Set reminder schedule for a medication

    pd reminder setup      - Show Twilio setup instructions
    pd reminder test       - Send a test SMS
    pd reminder start      - Start the background reminder service

The CLI uses Click, a Python library for building command-line tools.
"""

import click
from datetime import datetime, date, timedelta
from pathlib import Path
from tabulate import tabulate

from .database import init_database
from .models import (
    add_medication,
    get_all_medications,
    get_medication_by_name,
    get_medication_by_id,
    update_medication,
    deactivate_medication,
    log_dose,
    get_medication_status_today,
    get_last_dose,
    format_timedelta,
)
from .schedules import (
    add_schedule,
    get_schedule,
    get_all_active_schedules,
    delete_schedule,
    get_scheduled_times_for_today,
    get_next_scheduled_dose,
    format_schedule,
)
from .reminders import (
    send_test_message,
    send_medication_reminder,
    format_upcoming_reminders,
)
from .symptoms import (
    log_symptom,
    log_quick_state,
    get_symptoms_today,
    get_latest_symptom,
    get_on_off_summary_today,
    format_symptom_entry,
    SYMPTOM_DESCRIPTIONS,
)
from .sleep import (
    log_sleep_start,
    log_wake,
    log_sleep_session,
    get_open_sleep_record,
    get_last_sleep,
    get_sleep_logs,
    get_sleep_stats,
    format_sleep_entry,
    format_duration,
    calculate_duration,
)
from .exercise import (
    log_exercise,
    get_exercise_today,
    get_exercise_logs,
    get_exercise_stats,
    get_today_stats,
    format_exercise_entry,
    format_duration_friendly,
    COMMON_EXERCISES,
    INTENSITY_LEVELS,
)
from . import config


# ============================================================
# MAIN CLI GROUP
# ============================================================

@click.group()
@click.version_option(version="0.1.0", prog_name="PD Tracker")
def cli():
    """
    PD Tracker - Parkinson's Disease Management Tool

    Track medications, symptoms, sleep, and exercise.
    """
    # Ensure database exists whenever CLI runs
    # This is silent if tables already exist
    init_database()


# ============================================================
# MEDICATION COMMANDS
# ============================================================

@cli.group()
def med():
    """Manage medications and log doses."""
    pass


@med.command("add")
@click.option("--name", "-n", prompt="Medication name", help="Name of the medication")
@click.option("--dosage", "-d", prompt="Dosage (e.g., 100mg)", default="", help="Dosage amount")
@click.option("--instructions", "-i", prompt="Instructions (optional)", default="",
              help="Special instructions")
def med_add(name, dosage, instructions):
    """Add a new medication to track."""
    # Convert empty strings to None for cleaner database storage
    dosage = dosage if dosage else None
    instructions = instructions if instructions else None

    med_id = add_medication(name, dosage, instructions)
    click.echo(f"\nAdded medication: {name}")
    if dosage:
        click.echo(f"  Dosage: {dosage}")
    click.echo(f"  ID: {med_id}")
    click.echo("\nUse 'pd med take' to log when you take this medication.")


@med.command("list")
@click.option("--all", "-a", "show_all", is_flag=True, help="Show inactive medications too")
def med_list(show_all):
    """List all medications."""
    medications = get_all_medications(active_only=not show_all)

    if not medications:
        click.echo("No medications found. Use 'pd med add' to add one.")
        return

    # Prepare data for table
    table_data = []
    for med in medications:
        status = "Active" if med["active"] else "Inactive"
        table_data.append([
            med["id"],
            med["name"],
            med["dosage"] or "-",
            med["instructions"] or "-",
            status
        ])

    # Print as a nice table
    headers = ["ID", "Name", "Dosage", "Instructions", "Status"]
    click.echo("\nMedications:")
    click.echo(tabulate(table_data, headers=headers, tablefmt="simple"))
    click.echo()


@med.command("take")
@click.argument("medication", required=False)
@click.option("--notes", "-n", default=None, help="Notes about this dose")
def med_take(medication, notes):
    """
    Log that you took a medication.

    MEDICATION can be the full name, partial name, or ID.

    Examples:
        pd med take levodopa
        pd med take "sinemet cr"
        pd med take 1
    """
    # If no medication specified, show interactive picker
    if not medication:
        medications = get_all_medications()
        if not medications:
            click.echo("No medications found. Use 'pd med add' to add one.")
            return

        click.echo("\nWhich medication did you take?\n")
        for i, med in enumerate(medications, 1):
            dosage_str = f" ({med['dosage']})" if med['dosage'] else ""
            click.echo(f"  {i}. {med['name']}{dosage_str}")

        click.echo()
        choice = click.prompt("Enter number", type=int)

        if 1 <= choice <= len(medications):
            med = medications[choice - 1]
        else:
            click.echo("Invalid choice.")
            return
    else:
        # Try to find the medication
        # First, check if it's a number (ID)
        try:
            med_id = int(medication)
            med = get_medication_by_id(med_id)
        except ValueError:
            # It's a name, search for it
            med = get_medication_by_name(medication)

        if not med:
            click.echo(f"Medication '{medication}' not found.")
            click.echo("Use 'pd med list' to see all medications.")
            return

    # Log the dose
    taken_time = datetime.now()
    dose_id = log_dose(med["id"], taken_time=taken_time, notes=notes)

    time_str = taken_time.strftime("%I:%M %p")  # e.g., "02:30 PM"
    click.echo(f"\n✓ Logged: {med['name']}")
    if med['dosage']:
        click.echo(f"  Dosage: {med['dosage']}")
    click.echo(f"  Time: {time_str}")
    if notes:
        click.echo(f"  Notes: {notes}")
    click.echo()


@med.command("status")
def med_status():
    """
    Show today's medication status.

    This answers: "Did I take my meds?"
    Shows all active medications and when you last took each one.
    """
    status = get_medication_status_today()

    if not status:
        click.echo("No medications found. Use 'pd med add' to add some.")
        return

    click.echo("\n" + "=" * 50)
    click.echo("  TODAY'S MEDICATION STATUS")
    click.echo("  " + datetime.now().strftime("%A, %B %d, %Y"))
    click.echo("=" * 50 + "\n")

    for med in status:
        name_str = med['name']
        if med['dosage']:
            name_str += f" ({med['dosage']})"

        click.echo(f"  {name_str}")
        click.echo(f"  ├─ Doses today: {med['doses_today']}")

        if med['time_since_last']:
            time_ago = format_timedelta(med['time_since_last'])
            last_time = datetime.fromisoformat(med['last_dose_time']).strftime("%I:%M %p")
            click.echo(f"  └─ Last dose: {last_time} ({time_ago})")
        else:
            click.echo(f"  └─ Last dose: Not taken today")

        click.echo()

    click.echo("Use 'pd med take <name>' to log a dose.\n")


@med.command("remove")
@click.argument("medication")
@click.confirmation_option(prompt="Are you sure you want to deactivate this medication?")
def med_remove(medication):
    """
    Deactivate a medication (stop tracking).

    This doesn't delete the medication or its history - it just marks it
    as inactive so it won't show up in your daily status.

    MEDICATION can be the name or ID.
    """
    # Find the medication
    try:
        med_id = int(medication)
        med = get_medication_by_id(med_id)
    except ValueError:
        med = get_medication_by_name(medication)

    if not med:
        click.echo(f"Medication '{medication}' not found.")
        return

    if deactivate_medication(med["id"]):
        click.echo(f"Deactivated: {med['name']}")
        click.echo("Your dose history is preserved. Use 'pd med list --all' to see inactive medications.")
    else:
        click.echo("Failed to deactivate medication.")


@med.command("edit")
@click.argument("medication")
@click.option("--name", "-n", default=None, help="New name")
@click.option("--dosage", "-d", default=None, help="New dosage")
@click.option("--instructions", "-i", default=None, help="New instructions")
def med_edit(medication, name, dosage, instructions):
    """
    Edit a medication's details.

    MEDICATION can be the name or ID.

    Examples:
        pd med edit levodopa --dosage "150mg"
        pd med edit 1 --name "Sinemet CR" --instructions "Take with food"
    """
    # Find the medication
    try:
        med_id = int(medication)
        med = get_medication_by_id(med_id)
    except ValueError:
        med = get_medication_by_name(medication)

    if not med:
        click.echo(f"Medication '{medication}' not found.")
        return

    # If no options provided, prompt interactively
    if name is None and dosage is None and instructions is None:
        click.echo(f"\nEditing: {med['name']}")
        click.echo("Press Enter to keep current value.\n")

        name = click.prompt("Name", default=med['name'])
        dosage = click.prompt("Dosage", default=med['dosage'] or "")
        instructions = click.prompt("Instructions", default=med['instructions'] or "")

        # Convert to None if same as before or empty
        if name == med['name']:
            name = None
        if dosage == (med['dosage'] or ""):
            dosage = None
        if instructions == (med['instructions'] or ""):
            instructions = None

    if update_medication(med["id"], name=name, dosage=dosage, instructions=instructions):
        click.echo(f"\nUpdated medication.")
        # Show the updated medication
        updated = get_medication_by_id(med["id"])
        click.echo(f"  Name: {updated['name']}")
        click.echo(f"  Dosage: {updated['dosage'] or '-'}")
        click.echo(f"  Instructions: {updated['instructions'] or '-'}")
    else:
        click.echo("No changes made.")


# ============================================================
# MEDICATION SCHEDULE COMMAND
# ============================================================

@med.command("schedule")
@click.argument("medication", required=False)
def med_schedule(medication):
    """
    Set or view the reminder schedule for a medication.

    MEDICATION can be the name or ID. If not provided, shows all schedules.

    Examples:
        pd med schedule              # Show all schedules
        pd med schedule levodopa     # Set schedule for levodopa
    """
    # If no medication specified, show all schedules
    if not medication:
        schedules = get_all_active_schedules()
        if not schedules:
            click.echo("\nNo medication schedules set.")
            click.echo("Use 'pd med schedule <medication>' to set one.\n")
            return

        click.echo("\nMedication Schedules:")
        click.echo("-" * 50)
        for sched in schedules:
            name = sched['medication_name']
            if sched['dosage']:
                name += f" ({sched['dosage']})"
            click.echo(f"\n  {name}")
            click.echo(f"  └─ {format_schedule(sched)}")

            # Show today's scheduled times
            times = get_scheduled_times_for_today(sched['medication_id'])
            if times:
                time_strs = [t.strftime("%I:%M %p").lstrip('0') for t in times]
                click.echo(f"     Today: {', '.join(time_strs)}")

        click.echo()
        return

    # Find the medication
    try:
        med_id = int(medication)
        med = get_medication_by_id(med_id)
    except ValueError:
        med = get_medication_by_name(medication)

    if not med:
        click.echo(f"Medication '{medication}' not found.")
        return

    # Show current schedule if any
    current = get_schedule(med['id'])
    if current:
        click.echo(f"\nCurrent schedule for {med['name']}:")
        click.echo(f"  {format_schedule(current)}")
        click.echo()

    # Ask what type of schedule
    click.echo("Schedule type:")
    click.echo("  1. Fixed times (e.g., 8am, 2pm, 8pm)")
    click.echo("  2. Interval (e.g., every 4 hours)")
    click.echo("  3. As needed (PRN) - no reminders")
    click.echo("  4. Remove schedule")
    click.echo()

    choice = click.prompt("Choose", type=int, default=1)

    if choice == 1:
        # Fixed times
        click.echo("\nEnter times in 24-hour format (HH:MM), separated by commas.")
        click.echo("Example: 08:00, 14:00, 20:00")
        times_input = click.prompt("Times")

        # Parse the times
        times = []
        for t in times_input.split(','):
            t = t.strip()
            try:
                # Validate format
                hour, minute = map(int, t.split(':'))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    times.append(f"{hour:02d}:{minute:02d}")
                else:
                    click.echo(f"Invalid time: {t}")
                    return
            except ValueError:
                click.echo(f"Invalid time format: {t}")
                return

        add_schedule(med['id'], 'fixed', {'times': times})
        click.echo(f"\nSchedule set for {med['name']}:")
        click.echo(f"  Daily at: {', '.join(times)}")

    elif choice == 2:
        # Interval
        interval = click.prompt("Hours between doses", type=int, default=4)
        start_time = click.prompt("Start time (HH:MM)", default="07:00")
        end_time = click.prompt("End time (HH:MM)", default="22:00")

        add_schedule(med['id'], 'interval', {
            'interval_hours': interval,
            'start_time': start_time,
            'end_time': end_time,
        })
        click.echo(f"\nSchedule set for {med['name']}:")
        click.echo(f"  Every {interval} hours from {start_time} to {end_time}")

    elif choice == 3:
        # PRN
        add_schedule(med['id'], 'prn', {})
        click.echo(f"\nSchedule set for {med['name']}: As needed (no reminders)")

    elif choice == 4:
        # Remove schedule
        if delete_schedule(med['id']):
            click.echo(f"\nSchedule removed for {med['name']}")
        else:
            click.echo(f"\nNo schedule to remove for {med['name']}")

    else:
        click.echo("Invalid choice.")
        return

    # Show today's times if applicable
    times = get_scheduled_times_for_today(med['id'])
    if times:
        click.echo("\nToday's scheduled times:")
        for t in times:
            click.echo(f"  {t.strftime('%I:%M %p').lstrip('0')}")
    click.echo()


# ============================================================
# REMINDER COMMANDS
# ============================================================

@cli.group()
def reminder():
    """Manage SMS reminders via Twilio."""
    pass


@reminder.command("setup")
def reminder_setup():
    """Show instructions for setting up Twilio SMS reminders."""
    config.print_twilio_setup_instructions()


@reminder.command("status")
def reminder_status():
    """Check if Twilio is configured and show upcoming reminders."""
    click.echo("\n" + "=" * 50)
    click.echo("  REMINDER STATUS")
    click.echo("=" * 50)

    # Check Twilio config
    if config.is_twilio_configured():
        click.echo("\n  Twilio: ✓ Configured")
        click.echo(f"    From: {config.TWILIO_PHONE_NUMBER}")
        click.echo(f"    To: {config.USER_PHONE_NUMBER}")
    else:
        click.echo("\n  Twilio: ✗ Not configured")
        missing = config.get_missing_twilio_config()
        click.echo(f"    Missing: {', '.join(missing)}")
        click.echo("    Run 'pd reminder setup' for instructions.")

    # Show schedules
    schedules = get_all_active_schedules()
    if schedules:
        click.echo(f"\n  Active schedules: {len(schedules)}")
        for sched in schedules:
            click.echo(f"    • {sched['medication_name']}: {format_schedule(sched)}")
    else:
        click.echo("\n  Active schedules: None")
        click.echo("    Use 'pd med schedule <name>' to set one.")

    click.echo()


@reminder.command("test")
def reminder_test():
    """Send a test SMS to verify Twilio is working."""
    if not config.is_twilio_configured():
        click.echo("\nTwilio is not configured.")
        click.echo("Run 'pd reminder setup' for instructions.\n")
        return

    click.echo(f"\nSending test SMS to {config.USER_PHONE_NUMBER}...")

    result = send_test_message()

    if result['success']:
        click.echo("✓ Test message sent successfully!")
        click.echo(f"  Message ID: {result['sid']}")
        click.echo("\nCheck your phone - you should receive the message shortly.\n")
    else:
        click.echo(f"✗ Failed to send: {result['error']}\n")


@reminder.command("send")
@click.argument("medication", required=False)
def reminder_send(medication):
    """
    Manually send a reminder for a medication (for testing).

    MEDICATION can be the name or ID.
    """
    if not config.is_twilio_configured():
        click.echo("\nTwilio is not configured.")
        click.echo("Run 'pd reminder setup' for instructions.\n")
        return

    # If no medication specified, show picker
    if not medication:
        medications = get_all_medications()
        if not medications:
            click.echo("No medications found.")
            return

        click.echo("\nWhich medication?\n")
        for i, med in enumerate(medications, 1):
            dosage_str = f" ({med['dosage']})" if med['dosage'] else ""
            click.echo(f"  {i}. {med['name']}{dosage_str}")

        click.echo()
        choice = click.prompt("Enter number", type=int)

        if 1 <= choice <= len(medications):
            med = medications[choice - 1]
        else:
            click.echo("Invalid choice.")
            return
    else:
        try:
            med_id = int(medication)
            med = get_medication_by_id(med_id)
        except ValueError:
            med = get_medication_by_name(medication)

        if not med:
            click.echo(f"Medication '{medication}' not found.")
            return

    click.echo(f"\nSending reminder for {med['name']}...")

    result = send_medication_reminder(med['name'], med['dosage'])

    if result['success']:
        click.echo("✓ Reminder sent!")
    else:
        click.echo(f"✗ Failed: {result['error']}")
    click.echo()


@reminder.command("start")
@click.option("--interval", "-i", default=60, help="Check interval in seconds (default: 60)")
def reminder_start(interval):
    """
    Start the reminder service.

    This runs continuously, checking for upcoming medication doses
    and sending SMS reminders. Press Ctrl+C to stop.

    The service will:
    - Send reminders 5 minutes before each scheduled dose
    - Send follow-up messages 15 minutes after missed doses
    - Reset tracking at midnight each day
    """
    if not config.is_twilio_configured():
        click.echo("\nTwilio is not configured.")
        click.echo("Run 'pd reminder setup' for instructions.\n")
        return

    from .scheduler import run_scheduler
    run_scheduler(check_interval=interval)


# ============================================================
# QUICK STATUS COMMAND (shortcut)
# ============================================================

@cli.command("status")
def quick_status():
    """Quick shortcut for 'pd med status'."""
    ctx = click.Context(med_status)
    ctx.invoke(med_status)


# ============================================================
# SYMPTOM COMMANDS
# ============================================================

@cli.group()
def symptom():
    """Track PD symptoms and on/off states."""
    pass


@symptom.command("log")
def symptom_log():
    """
    Log your current symptoms (interactive).

    Records on/off state, severity, and individual symptom ratings.
    """
    click.echo("\n--- Log Symptoms ---\n")

    # On/Off state
    click.echo("Current state:")
    click.echo("  1. ON (medication working well)")
    click.echo("  2. OFF (medication wearing off)")
    click.echo("  3. Transitioning")
    click.echo("  4. Skip")

    state_choice = click.prompt("Choose", type=int, default=4)
    state_map = {1: 'on', 2: 'off', 3: 'transitioning', 4: None}
    on_off_state = state_map.get(state_choice)

    # Overall severity
    severity = click.prompt("\nOverall severity (1-10, or 0 to skip)", type=int, default=0)
    if severity == 0:
        severity = None

    # Individual symptoms
    click.echo("\nRate each symptom 0-10 (0 = not present):\n")

    tremor = click.prompt("  Tremor", type=int, default=0)
    rigidity = click.prompt("  Rigidity (stiffness)", type=int, default=0)
    bradykinesia = click.prompt("  Bradykinesia (slowness)", type=int, default=0)
    dyskinesia = click.prompt("  Dyskinesia (involuntary movement)", type=int, default=0)
    freezing = click.prompt("  Freezing", type=int, default=0)
    balance = click.prompt("  Balance issues", type=int, default=0)

    # Notes
    notes = click.prompt("\nNotes (optional)", default="")
    notes = notes if notes else None

    # Save
    symptom_id = log_symptom(
        on_off_state=on_off_state,
        severity=severity,
        tremor=tremor,
        rigidity=rigidity,
        bradykinesia=bradykinesia,
        dyskinesia=dyskinesia,
        freezing=freezing,
        balance=balance,
        notes=notes,
    )

    click.echo(f"\n✓ Symptoms logged (ID: {symptom_id})")

    # Show summary
    if on_off_state:
        click.echo(f"  State: {on_off_state.upper()}")
    if severity:
        click.echo(f"  Severity: {severity}/10")
    click.echo()


@symptom.command("quick")
@click.argument("state", type=click.Choice(['on', 'off', 'trans'], case_sensitive=False))
@click.option("--notes", "-n", default=None, help="Optional notes")
def symptom_quick(state, notes):
    """
    Quickly log on/off state.

    STATE is 'on', 'off', or 'trans' (transitioning).

    Examples:
        pd symptom quick on
        pd symptom quick off -n "wearing off after 3 hours"
    """
    state_map = {'on': 'on', 'off': 'off', 'trans': 'transitioning'}
    actual_state = state_map[state.lower()]

    symptom_id = log_quick_state(actual_state, notes)

    time_str = datetime.now().strftime("%I:%M %p").lstrip('0')
    click.echo(f"\n✓ Logged: {actual_state.upper()} at {time_str}")
    if notes:
        click.echo(f"  Notes: {notes}")
    click.echo()


@symptom.command("status")
def symptom_status():
    """Show today's symptom summary."""
    summary = get_on_off_summary_today()

    click.echo("\n" + "=" * 40)
    click.echo("  TODAY'S SYMPTOM SUMMARY")
    click.echo("=" * 40)

    click.echo(f"\n  Total entries: {summary['total_entries']}")
    click.echo(f"  ON states: {summary['on']}")
    click.echo(f"  OFF states: {summary['off']}")
    click.echo(f"  Transitioning: {summary['transitioning']}")

    if summary['last_state']:
        last_time = datetime.fromisoformat(summary['last_time'])
        click.echo(f"\n  Last logged: {summary['last_state'].upper()} at {last_time.strftime('%I:%M %p').lstrip('0')}")
    else:
        click.echo("\n  No symptoms logged today.")

    click.echo()


@symptom.command("history")
@click.option("--days", "-d", default=1, help="Number of days to show (default: 1)")
def symptom_history(days):
    """Show recent symptom entries."""
    from datetime import timedelta

    if days == 1:
        symptoms = get_symptoms_today()
        title = "TODAY'S SYMPTOMS"
    else:
        from .symptoms import get_symptoms_range
        start = date.today() - timedelta(days=days-1)
        symptoms = get_symptoms_range(start)
        title = f"SYMPTOMS (Last {days} days)"

    click.echo("\n" + "=" * 40)
    click.echo(f"  {title}")
    click.echo("=" * 40)

    if not symptoms:
        click.echo("\n  No symptoms logged.\n")
        return

    for s in symptoms:
        click.echo()
        click.echo(format_symptom_entry(s))

    click.echo()


# ============================================================
# SLEEP COMMANDS
# ============================================================

@cli.group()
def sleep():
    """Track sleep patterns."""
    pass


@sleep.command("start")
@click.option("--notes", "-n", default=None, help="Notes (e.g., 'feeling tired')")
def sleep_start(notes):
    """
    Log that you're going to sleep now.

    Use 'pd sleep wake' when you wake up to complete the record.
    """
    # Check if already have an open sleep record
    open_record = get_open_sleep_record()
    if open_record:
        sleep_time = datetime.fromisoformat(open_record['sleep_time'])
        click.echo(f"\nYou already have an open sleep record from {sleep_time.strftime('%I:%M %p').lstrip('0')}.")
        click.echo("Use 'pd sleep wake' to complete it first.\n")
        return

    sleep_id = log_sleep_start(notes=notes)
    time_str = datetime.now().strftime("%I:%M %p").lstrip('0')

    click.echo(f"\n✓ Sleep started at {time_str}")
    click.echo("  Use 'pd sleep wake' when you wake up.")
    if notes:
        click.echo(f"  Notes: {notes}")
    click.echo()


@sleep.command("wake")
@click.option("--quality", "-q", type=int, default=None, help="Sleep quality 1-10")
@click.option("--notes", "-n", default=None, help="Notes about your sleep")
def sleep_wake(quality, notes):
    """
    Log that you just woke up.

    Completes the sleep record started with 'pd sleep start'.
    """
    open_record = get_open_sleep_record()
    if not open_record:
        click.echo("\nNo open sleep record found.")
        click.echo("Use 'pd sleep start' when going to sleep, or 'pd sleep log' for manual entry.\n")
        return

    # Prompt for quality if not provided
    if quality is None:
        quality = click.prompt("Sleep quality (1-10)", type=int, default=5)

    sleep_id = log_wake(quality=quality, notes=notes)

    # Get the completed record for display
    sleep_time = datetime.fromisoformat(open_record['sleep_time'])
    wake_time = datetime.now()
    duration = calculate_duration(sleep_time, wake_time)

    click.echo(f"\n✓ Good morning! Sleep logged.")
    click.echo(f"  Slept: {sleep_time.strftime('%I:%M %p').lstrip('0')} - {wake_time.strftime('%I:%M %p').lstrip('0')}")
    click.echo(f"  Duration: {format_duration(duration)}")
    click.echo(f"  Quality: {quality}/10")
    if notes:
        click.echo(f"  Notes: {notes}")
    click.echo()


@sleep.command("log")
def sleep_log_manual():
    """
    Manually log a sleep session (for past sleep).

    Use this when you forgot to use 'pd sleep start/wake'.
    """
    click.echo("\n--- Log Sleep (Manual Entry) ---\n")

    # Date
    date_str = click.prompt("Date (YYYY-MM-DD, or 'today'/'yesterday')", default="today")
    if date_str == "today":
        sleep_date = date.today()
    elif date_str == "yesterday":
        sleep_date = date.today() - timedelta(days=1)
    else:
        try:
            sleep_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            click.echo("Invalid date format. Use YYYY-MM-DD.")
            return

    # Sleep time
    sleep_time_str = click.prompt("Sleep time (HH:MM, 24h format)", default="22:00")
    try:
        hour, minute = map(int, sleep_time_str.split(':'))
        sleep_time = datetime.combine(sleep_date, datetime.min.time().replace(hour=hour, minute=minute))
    except ValueError:
        click.echo("Invalid time format. Use HH:MM.")
        return

    # Wake time (might be next day)
    wake_time_str = click.prompt("Wake time (HH:MM, 24h format)", default="07:00")
    try:
        hour, minute = map(int, wake_time_str.split(':'))
        wake_time = datetime.combine(sleep_date, datetime.min.time().replace(hour=hour, minute=minute))
        # If wake time is earlier than sleep time, it's the next day
        if wake_time <= sleep_time:
            wake_time += timedelta(days=1)
    except ValueError:
        click.echo("Invalid time format. Use HH:MM.")
        return

    # Quality
    quality = click.prompt("Sleep quality (1-10)", type=int, default=5)

    # Notes
    notes = click.prompt("Notes (optional)", default="")
    notes = notes if notes else None

    sleep_id = log_sleep_session(sleep_time, wake_time, quality, notes)
    duration = calculate_duration(sleep_time, wake_time)

    click.echo(f"\n✓ Sleep logged")
    click.echo(f"  Date: {sleep_date.strftime('%a, %b %d')}")
    click.echo(f"  Time: {sleep_time.strftime('%I:%M %p').lstrip('0')} - {wake_time.strftime('%I:%M %p').lstrip('0')}")
    click.echo(f"  Duration: {format_duration(duration)}")
    click.echo(f"  Quality: {quality}/10")
    click.echo()


@sleep.command("status")
def sleep_status():
    """Show sleep status and recent stats."""
    # Check for open record
    open_record = get_open_sleep_record()

    click.echo("\n" + "=" * 40)
    click.echo("  SLEEP STATUS")
    click.echo("=" * 40)

    if open_record:
        sleep_time = datetime.fromisoformat(open_record['sleep_time'])
        duration = datetime.now() - sleep_time
        click.echo(f"\n  Currently sleeping (started {sleep_time.strftime('%I:%M %p').lstrip('0')})")
        click.echo(f"  Duration so far: {format_duration(duration)}")
        click.echo("\n  Use 'pd sleep wake' when you wake up.")
    else:
        last = get_last_sleep()
        if last:
            wake_time = datetime.fromisoformat(last['wake_time'])
            click.echo(f"\n  Last wake: {wake_time.strftime('%a, %b %d at %I:%M %p').lstrip('0')}")
            if last['quality']:
                click.echo(f"  Quality: {last['quality']}/10")

    # Weekly stats
    stats = get_sleep_stats(7)
    if stats['total_nights'] > 0:
        click.echo(f"\n  --- Last 7 Days ---")
        click.echo(f"  Nights logged: {stats['total_nights']}")
        click.echo(f"  Avg duration: {stats['avg_duration_formatted']}")
        if stats['avg_quality']:
            click.echo(f"  Avg quality: {stats['avg_quality']}/10")

    click.echo()


@sleep.command("history")
@click.option("--days", "-d", default=7, help="Number of days to show (default: 7)")
def sleep_history(days):
    """Show recent sleep history."""
    logs = get_sleep_logs(days)

    click.echo("\n" + "=" * 40)
    click.echo(f"  SLEEP HISTORY (Last {days} days)")
    click.echo("=" * 40)

    if not logs:
        click.echo("\n  No sleep logged.\n")
        return

    for log in logs:
        click.echo()
        click.echo(format_sleep_entry(log))

    # Stats
    stats = get_sleep_stats(days)
    if stats['total_nights'] > 0:
        click.echo("\n  --- Summary ---")
        click.echo(f"  Total nights: {stats['total_nights']}")
        click.echo(f"  Avg duration: {stats['avg_duration_formatted']}")
        if stats['avg_quality']:
            click.echo(f"  Avg quality: {stats['avg_quality']}/10")

    click.echo()


# ============================================================
# EXERCISE COMMANDS
# ============================================================

@cli.group()
def exercise():
    """Track physical activity."""
    pass


@exercise.command("log")
@click.option("--type", "-t", "exercise_type", default=None, help="Exercise type")
@click.option("--duration", "-d", "duration_mins", type=int, default=None, help="Duration in minutes")
@click.option("--intensity", "-i", type=click.Choice(['light', 'moderate', 'vigorous']), default=None)
@click.option("--notes", "-n", default=None, help="Notes")
def exercise_log_cmd(exercise_type, duration_mins, intensity, notes):
    """
    Log an exercise session.

    Can be used with options or interactively.

    Examples:
        pd exercise log
        pd exercise log -t Walking -d 30 -i moderate
    """
    # Interactive mode if no options provided
    if not exercise_type:
        click.echo("\n--- Log Exercise ---\n")
        click.echo("Exercise type:")
        for i, ex in enumerate(COMMON_EXERCISES, 1):
            click.echo(f"  {i:2}. {ex}")

        choice = click.prompt("\nChoose (or type custom)", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(COMMON_EXERCISES):
                exercise_type = COMMON_EXERCISES[idx]
                if exercise_type == "Other":
                    exercise_type = click.prompt("Enter exercise type")
            else:
                exercise_type = choice
        except ValueError:
            exercise_type = choice

    if not duration_mins:
        duration_mins = click.prompt("Duration (minutes)", type=int, default=30)

    if not intensity:
        click.echo("\nIntensity:")
        click.echo("  1. Light (easy, can talk easily)")
        click.echo("  2. Moderate (somewhat hard, can talk)")
        click.echo("  3. Vigorous (hard, difficult to talk)")
        int_choice = click.prompt("Choose", type=int, default=2)
        intensity = ['light', 'moderate', 'vigorous'][int_choice - 1] if 1 <= int_choice <= 3 else 'moderate'

    if notes is None:
        notes = click.prompt("Notes (optional)", default="")
        notes = notes if notes else None

    exercise_id = log_exercise(exercise_type, duration_mins, intensity, notes=notes)

    click.echo(f"\n✓ Exercise logged")
    click.echo(f"  Type: {exercise_type}")
    click.echo(f"  Duration: {duration_mins} minutes")
    click.echo(f"  Intensity: {intensity.capitalize()}")
    if notes:
        click.echo(f"  Notes: {notes}")
    click.echo()


@exercise.command("quick")
@click.argument("exercise_type")
@click.argument("duration", type=int)
@click.option("--intensity", "-i", type=click.Choice(['light', 'moderate', 'vigorous']), default='moderate')
def exercise_quick(exercise_type, duration, intensity):
    """
    Quickly log an exercise session.

    Examples:
        pd exercise quick Walking 30
        pd exercise quick "Physical Therapy" 45 -i light
    """
    exercise_id = log_exercise(exercise_type, duration, intensity)

    click.echo(f"\n✓ Logged: {exercise_type}, {duration} min, {intensity}")
    click.echo()


@exercise.command("status")
def exercise_status():
    """Show today's exercise summary."""
    today = get_today_stats()

    click.echo("\n" + "=" * 40)
    click.echo("  TODAY'S EXERCISE")
    click.echo("=" * 40)

    if today['sessions'] == 0:
        click.echo("\n  No exercise logged today.")
        click.echo("  Use 'pd exercise log' to add some.\n")
        return

    click.echo(f"\n  Sessions: {today['sessions']}")
    click.echo(f"  Total time: {format_duration_friendly(today['total_minutes'])}")
    click.echo(f"  Types: {', '.join(today['types'])}")

    # Show individual sessions
    logs = get_exercise_today()
    click.echo("\n  --- Sessions ---")
    for log in logs:
        start = datetime.fromisoformat(log['start_time'])
        click.echo(f"  • {start.strftime('%I:%M %p').lstrip('0')}: {log['exercise_type']} ({log['duration_minutes']}m, {log['intensity']})")

    click.echo()


@exercise.command("history")
@click.option("--days", "-d", default=7, help="Number of days to show (default: 7)")
def exercise_history(days):
    """Show recent exercise history."""
    logs = get_exercise_logs(days)

    click.echo("\n" + "=" * 40)
    click.echo(f"  EXERCISE HISTORY (Last {days} days)")
    click.echo("=" * 40)

    if not logs:
        click.echo("\n  No exercise logged.\n")
        return

    for log in logs:
        click.echo()
        click.echo(format_exercise_entry(log))

    # Stats
    stats = get_exercise_stats(days)
    click.echo("\n  --- Summary ---")
    click.echo(f"  Total sessions: {stats['total_sessions']}")
    click.echo(f"  Total time: {format_duration_friendly(stats['total_minutes'])}")
    click.echo(f"  Avg per day: {stats['avg_minutes_per_day']} min")

    if stats['by_type']:
        click.echo("\n  By type:")
        for etype, data in stats['by_type'].items():
            click.echo(f"    {etype}: {data['sessions']} sessions, {data['minutes']} min")

    click.echo()


# ============================================================
# REPORT COMMANDS
# ============================================================

@cli.group()
def report():
    """Generate and email reports."""
    pass


@report.command("generate")
@click.option("--format", "-f", type=click.Choice(['pdf', 'excel', 'csv']), default='pdf',
              help="Export format (default: pdf)")
@click.option("--days", "-d", default=7, type=int, help="Number of days to include (default: 7)")
@click.option("--email/--no-email", default=False, help="Send report via email")
def report_generate(format, days, email):
    """
    Generate a report for the specified period.

    Examples:
        pd report generate                    # PDF report, last 7 days
        pd report generate -f excel -d 30     # Excel report, last 30 days
        pd report generate --email            # Generate and email PDF
    """
    from .export import export_pdf, export_excel, export_csv, EXPORT_DIR
    from .email_sender import send_report_email, is_email_configured

    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)

    click.echo(f"\nGenerating {format.upper()} report...")
    click.echo(f"  Period: {start_date} to {end_date}")

    try:
        if format == 'pdf':
            filepath = export_pdf(start_date, end_date)
        elif format == 'excel':
            filepath = export_excel(start_date, end_date)
        else:
            filepath = export_csv('all', start_date, end_date)

        click.echo(f"\n✓ Report generated: {filepath}")

        if email:
            if not is_email_configured():
                click.echo("\nEmail not configured. Run 'pd report email-setup' for instructions.")
                return

            click.echo("\nSending via email...")
            result = send_report_email(filepath)

            if result['success']:
                click.echo(f"✓ {result['message']}")
            else:
                click.echo(f"✗ {result['error']}")

    except Exception as e:
        click.echo(f"\n✗ Error generating report: {e}")

    click.echo()


@report.command("today")
def report_today():
    """Show a quick summary of today's data."""
    med_status = get_medication_status_today()
    from .symptoms import get_on_off_summary_today
    from .exercise import get_today_stats

    symptom_summary = get_on_off_summary_today()
    exercise_stats = get_today_stats()

    click.echo("\n" + "=" * 50)
    click.echo("  TODAY'S SUMMARY")
    click.echo("  " + datetime.now().strftime("%A, %B %d, %Y"))
    click.echo("=" * 50)

    # Medications
    click.echo("\n  MEDICATIONS")
    if med_status:
        for med in med_status:
            click.echo(f"    {med['name']}: {med['doses_today']} doses")
    else:
        click.echo("    No medications tracked")

    # Symptoms
    click.echo("\n  SYMPTOMS")
    click.echo(f"    ON: {symptom_summary['on']}  |  OFF: {symptom_summary['off']}  |  Trans: {symptom_summary['transitioning']}")

    # Exercise
    click.echo("\n  EXERCISE")
    if exercise_stats['sessions'] > 0:
        click.echo(f"    {exercise_stats['sessions']} session(s), {exercise_stats['total_minutes']} minutes")
    else:
        click.echo("    No exercise logged")

    click.echo()


@report.command("email-setup")
def report_email_setup():
    """Show instructions for setting up email."""
    from .email_sender import print_email_setup_instructions
    print_email_setup_instructions()


@report.command("email-test")
def report_email_test():
    """Send a test email to verify configuration."""
    from .email_sender import send_test_email, is_email_configured, get_email_config

    if not is_email_configured():
        click.echo("\nEmail not configured.")
        click.echo("Run 'pd report email-setup' for instructions.\n")
        return

    config = get_email_config()
    click.echo(f"\nSending test email to {config['email']}...")

    result = send_test_email()

    if result['success']:
        click.echo("✓ Test email sent! Check your inbox.\n")
    else:
        click.echo(f"✗ Failed: {result['error']}\n")


@report.command("add-email")
@click.argument("email")
@click.option("--name", "-n", default=None, help="Recipient name")
def report_add_email(email, name):
    """
    Add an email recipient for reports.

    Examples:
        pd report add-email doctor@clinic.com -n "Dr. Smith"
        pd report add-email spouse@email.com
    """
    from .email_sender import add_recipient

    add_recipient(email, name)
    click.echo(f"\n✓ Added recipient: {email}")
    if name:
        click.echo(f"  Name: {name}")
    click.echo()


@report.command("list-emails")
def report_list_emails():
    """List all email recipients."""
    from .email_sender import get_recipients

    recipients = get_recipients()

    if not recipients:
        click.echo("\nNo email recipients configured.")
        click.echo("Use 'pd report add-email <address>' to add one.\n")
        return

    click.echo("\nEmail Recipients:")
    for r in recipients:
        name_str = f" ({r['name']})" if r.get('name') else ""
        click.echo(f"  • {r['email']}{name_str}")
    click.echo()


@report.command("remove-email")
@click.argument("email")
def report_remove_email(email):
    """Remove an email recipient."""
    from .email_sender import remove_recipient

    if remove_recipient(email):
        click.echo(f"\n✓ Removed: {email}\n")
    else:
        click.echo(f"\n✗ Recipient not found: {email}\n")


# ============================================================
# WEB SERVER COMMAND
# ============================================================

@cli.group()
def web():
    """Manage the web interface."""
    pass


@web.command("start")
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
@click.option("--port", "-p", default=5000, type=int, help="Port to run on (default: 5000)")
@click.option("--debug", "-d", is_flag=True, help="Run in debug mode")
def web_start(host, port, debug):
    """
    Start the web interface.

    Access from your phone at http://<your-computer-ip>:5000

    Examples:
        pd web start              # Start on default port 5000
        pd web start -p 8080      # Start on port 8080
        pd web start -d           # Start in debug mode (auto-reload)
    """
    from web.app import run_server
    run_server(host=host, port=port, debug=debug)


# ============================================================
# BACKUP COMMANDS
# ============================================================

@cli.group()
def backup():
    """Backup and restore your data."""
    pass


@backup.command("create")
@click.option("--output", "-o", default=None, help="Output file path")
def backup_create(output):
    """
    Create a backup of your database.

    Examples:
        pd backup create                      # Auto-named backup in exports/
        pd backup create -o ~/my_backup.db    # Custom location
    """
    import shutil
    from .database import DB_PATH
    from .export import ensure_export_dir

    if not DB_PATH.exists():
        click.echo("No database found to backup.")
        return

    if output is None:
        ensure_export_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path(__file__).parent.parent / "exports" / f"pd_tracker_backup_{timestamp}.db"
    else:
        output = Path(output)

    shutil.copy2(DB_PATH, output)
    size_kb = output.stat().st_size / 1024

    click.echo(f"\n✓ Backup created: {output}")
    click.echo(f"  Size: {size_kb:.1f} KB\n")


@backup.command("restore")
@click.argument("backup_file", type=click.Path(exists=True))
@click.confirmation_option(prompt="This will overwrite your current data. Continue?")
def backup_restore(backup_file):
    """
    Restore from a backup file.

    WARNING: This will replace all current data!

    Examples:
        pd backup restore ~/my_backup.db
    """
    import shutil
    from .database import DB_PATH, DATA_DIR

    backup_path = Path(backup_file)

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Create a backup of current data first
    if DB_PATH.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_backup = DATA_DIR / f"pre_restore_backup_{timestamp}.db"
        shutil.copy2(DB_PATH, old_backup)
        click.echo(f"  Current data backed up to: {old_backup}")

    # Restore
    shutil.copy2(backup_path, DB_PATH)
    click.echo(f"\n✓ Restored from: {backup_path}\n")


@backup.command("list")
def backup_list():
    """List available backups."""
    from .export import EXPORT_DIR

    if not EXPORT_DIR.exists():
        click.echo("\nNo backups found.\n")
        return

    backups = sorted(EXPORT_DIR.glob("pd_tracker_backup_*.db"), reverse=True)

    if not backups:
        click.echo("\nNo backups found.\n")
        return

    click.echo("\nAvailable Backups:")
    for b in backups[:10]:  # Show last 10
        size_kb = b.stat().st_size / 1024
        mtime = datetime.fromtimestamp(b.stat().st_mtime)
        click.echo(f"  {b.name}  ({size_kb:.1f} KB, {mtime.strftime('%Y-%m-%d %H:%M')})")

    if len(backups) > 10:
        click.echo(f"  ... and {len(backups) - 10} more")
    click.echo()


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
