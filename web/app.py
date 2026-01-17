"""
Flask web application for PD Tracker.

Mobile-friendly web interface for logging medications, symptoms, sleep, and exercise.
Designed for quick, easy logging from a phone.

Run with: python -m web.app
Or use: pd web start
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import pd_tracker modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, date, timedelta

# Import our tracking modules
from pd_tracker.database import init_database
from pd_tracker.models import (
    get_all_medications,
    get_medication_by_id,
    add_medication,
    update_medication,
    deactivate_medication,
    log_dose,
    get_dose_by_id,
    update_dose,
    delete_dose,
    get_doses_today,
    get_doses_range,
    get_medication_status_today,
)
from pd_tracker.symptoms import (
    log_symptom,
    log_quick_state,
    get_symptom_by_id,
    update_symptom,
    delete_symptom,
    get_symptoms_today,
    get_symptoms_range,
    get_on_off_summary_today,
)
from pd_tracker.sleep import (
    log_sleep_start,
    log_wake,
    log_sleep_session,
    get_sleep_by_id,
    update_sleep,
    delete_sleep,
    get_open_sleep_record,
    get_last_sleep,
    get_sleep_logs,
    get_sleep_stats,
    format_duration,
    calculate_duration,
)
from pd_tracker.exercise import (
    log_exercise,
    get_exercise_by_id,
    update_exercise,
    delete_exercise,
    get_exercise_today,
    get_exercise_logs,
    get_exercise_stats,
    get_today_stats as get_exercise_today_stats,
    COMMON_EXERCISES,
    INTENSITY_LEVELS,
)
from pd_tracker.schedules import (
    get_all_active_schedules,
    get_scheduled_times_for_today,
    add_schedule,
    get_schedule,
    update_schedule,
    delete_schedule,
    toggle_reminders,
    format_schedule,
    log_wake_event,
    log_sleep_event,
    get_last_wake_event,
    is_user_awake,
    SCHEDULE_TYPES,
    INTERVAL_OPTIONS,
)
from pd_tracker.export import export_pdf, export_excel, export_csv

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'pd-tracker-secret-key-change-in-production'

# Initialize database on startup
init_database()


# ============================================================
# TEMPLATE HELPERS
# ============================================================

@app.template_filter('time12')
def time12_filter(dt_string):
    """Convert datetime string to 12-hour format."""
    if not dt_string:
        return ""
    if isinstance(dt_string, str):
        dt = datetime.fromisoformat(dt_string)
    else:
        dt = dt_string
    return dt.strftime("%I:%M %p").lstrip('0')


@app.template_filter('dateformat')
def dateformat_filter(dt_string, fmt="%b %d"):
    """Format a date string."""
    if not dt_string:
        return ""
    if isinstance(dt_string, str):
        dt = datetime.fromisoformat(dt_string)
    else:
        dt = dt_string
    return dt.strftime(fmt)


@app.context_processor
def inject_now():
    """Make current time available in all templates."""
    return {'now': datetime.now()}


# ============================================================
# ROUTES - DASHBOARD
# ============================================================

@app.route('/')
def dashboard():
    """Main dashboard showing today's overview."""
    # Medication status
    med_status = get_medication_status_today()

    # Symptom summary
    symptom_summary = get_on_off_summary_today()

    # Sleep status
    open_sleep = get_open_sleep_record()
    last_sleep = get_last_sleep() if not open_sleep else None

    # Exercise today
    exercise_stats = get_exercise_today_stats()

    # Wake status for medication scheduling
    wake_status = get_last_wake_event()
    is_awake = is_user_awake()

    return render_template('dashboard.html',
                          med_status=med_status,
                          symptom_summary=symptom_summary,
                          open_sleep=open_sleep,
                          last_sleep=last_sleep,
                          exercise_stats=exercise_stats,
                          wake_status=wake_status,
                          is_awake=is_awake)


# ============================================================
# ROUTES - MEDICATIONS
# ============================================================

@app.route('/meds')
def meds():
    """Medication status and logging page."""
    medications = get_all_medications()
    med_status = get_medication_status_today()
    return render_template('meds.html',
                          medications=medications,
                          med_status=med_status)


@app.route('/meds/take/<int:med_id>', methods=['POST'])
def take_med(med_id):
    """Log taking a medication."""
    med = get_medication_by_id(med_id)
    if med:
        log_dose(med_id)
        flash(f"Logged: {med['name']}", 'success')
    return redirect(url_for('meds'))


@app.route('/meds/take', methods=['POST'])
def take_med_form():
    """Log taking a medication from form."""
    med_id = request.form.get('med_id', type=int)
    if med_id:
        med = get_medication_by_id(med_id)
        if med:
            log_dose(med_id)
            flash(f"Logged: {med['name']}", 'success')
    return redirect(url_for('dashboard'))


# ============================================================
# ROUTES - SYMPTOMS
# ============================================================

@app.route('/symptoms')
def symptoms():
    """Symptom logging page."""
    today_symptoms = get_symptoms_today()
    summary = get_on_off_summary_today()
    return render_template('symptoms.html',
                          symptoms=today_symptoms,
                          summary=summary)


@app.route('/symptoms/quick/<state>', methods=['POST'])
def symptom_quick(state):
    """Quick log on/off state."""
    if state in ['on', 'off', 'trans']:
        actual_state = 'transitioning' if state == 'trans' else state
        log_quick_state(actual_state)
        flash(f"Logged: {actual_state.upper()}", 'success')
    return redirect(url_for('symptoms'))


@app.route('/symptoms/log', methods=['POST'])
def symptom_log():
    """Log detailed symptoms."""
    on_off = request.form.get('on_off_state')
    severity = request.form.get('severity', type=int)
    tremor = request.form.get('tremor', type=int, default=0)
    rigidity = request.form.get('rigidity', type=int, default=0)
    bradykinesia = request.form.get('bradykinesia', type=int, default=0)
    dyskinesia = request.form.get('dyskinesia', type=int, default=0)
    freezing = request.form.get('freezing', type=int, default=0)
    balance = request.form.get('balance', type=int, default=0)
    notes = request.form.get('notes', '').strip() or None

    log_symptom(
        on_off_state=on_off if on_off else None,
        severity=severity,
        tremor=tremor,
        rigidity=rigidity,
        bradykinesia=bradykinesia,
        dyskinesia=dyskinesia,
        freezing=freezing,
        balance=balance,
        notes=notes,
    )

    flash("Symptoms logged", 'success')
    return redirect(url_for('symptoms'))


# ============================================================
# ROUTES - SLEEP
# ============================================================

@app.route('/sleep')
def sleep():
    """Sleep tracking page."""
    open_record = get_open_sleep_record()
    last = get_last_sleep()
    stats = get_sleep_stats(7)
    return render_template('sleep.html',
                          open_record=open_record,
                          last_sleep=last,
                          stats=stats)


@app.route('/sleep/start', methods=['POST'])
def sleep_start():
    """Log going to sleep."""
    notes = request.form.get('notes', '').strip() or None

    open_record = get_open_sleep_record()
    if open_record:
        flash("Already have an open sleep record", 'warning')
    else:
        log_sleep_start(notes=notes)
        flash("Sleep started - goodnight!", 'success')

    return redirect(url_for('sleep'))


@app.route('/sleep/wake', methods=['POST'])
def sleep_wake():
    """Log waking up."""
    quality = request.form.get('quality', type=int, default=5)
    notes = request.form.get('notes', '').strip() or None

    open_record = get_open_sleep_record()
    if not open_record:
        flash("No open sleep record found", 'warning')
    else:
        log_wake(quality=quality, notes=notes)
        flash("Good morning! Sleep logged.", 'success')

    return redirect(url_for('sleep'))


# ============================================================
# ROUTES - EXERCISE
# ============================================================

@app.route('/exercise')
def exercise():
    """Exercise tracking page."""
    today = get_exercise_today()
    stats = get_exercise_today_stats()
    return render_template('exercise.html',
                          exercises=today,
                          stats=stats,
                          exercise_types=COMMON_EXERCISES)


@app.route('/exercise/log', methods=['POST'])
def exercise_log():
    """Log an exercise session."""
    exercise_type = request.form.get('exercise_type', '').strip()
    custom_type = request.form.get('custom_type', '').strip()
    duration = request.form.get('duration', type=int, default=30)
    intensity = request.form.get('intensity', 'moderate')
    notes = request.form.get('notes', '').strip() or None

    # Use custom type if "Other" was selected
    if exercise_type == 'Other' and custom_type:
        exercise_type = custom_type

    if exercise_type and duration > 0:
        log_exercise(exercise_type, duration, intensity, notes=notes)
        flash(f"Logged: {exercise_type}, {duration} min", 'success')

    return redirect(url_for('exercise'))


# ============================================================
# MEDICATION MANAGEMENT ROUTES
# ============================================================

@app.route('/meds/manage')
def meds_manage():
    """Medication management page."""
    medications = get_all_medications(active_only=False)
    return render_template('meds_manage.html', medications=medications)


@app.route('/meds/add', methods=['GET', 'POST'])
def meds_add():
    """Add a new medication."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        dosage = request.form.get('dosage', '').strip() or None
        instructions = request.form.get('instructions', '').strip() or None

        if name:
            add_medication(name, dosage, instructions)
            flash(f"Added medication: {name}", 'success')
            return redirect(url_for('meds_manage'))
        else:
            flash("Medication name is required", 'error')

    return render_template('meds_add.html')


@app.route('/meds/edit/<int:med_id>', methods=['GET', 'POST'])
def meds_edit(med_id):
    """Edit a medication."""
    med = get_medication_by_id(med_id)
    if not med:
        flash("Medication not found", 'error')
        return redirect(url_for('meds_manage'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip() or None
        dosage = request.form.get('dosage', '').strip() or None
        instructions = request.form.get('instructions', '').strip() or None

        if update_medication(med_id, name=name, dosage=dosage, instructions=instructions):
            flash(f"Updated medication: {name or med['name']}", 'success')
            return redirect(url_for('meds_manage'))

    return render_template('meds_edit.html', medication=med)


@app.route('/meds/delete/<int:med_id>', methods=['POST'])
def meds_delete(med_id):
    """Deactivate a medication."""
    med = get_medication_by_id(med_id)
    if med and deactivate_medication(med_id):
        flash(f"Deactivated medication: {med['name']}", 'success')
    return redirect(url_for('meds_manage'))


# ============================================================
# SCHEDULE MANAGEMENT ROUTES
# ============================================================

@app.route('/schedules')
def schedules():
    """View all medication schedules."""
    medications = get_all_medications()
    schedules_list = []

    for med in medications:
        sched = get_schedule(med['id'])
        schedules_list.append({
            'medication': med,
            'schedule': sched,
            'formatted': format_schedule(sched) if sched else 'No schedule',
        })

    wake_status = get_last_wake_event()
    awake = is_user_awake()

    return render_template('schedules.html',
                          schedules=schedules_list,
                          wake_status=wake_status,
                          is_awake=awake,
                          schedule_types=SCHEDULE_TYPES)


@app.route('/schedules/add/<int:med_id>', methods=['GET', 'POST'])
def schedule_add(med_id):
    """Add/edit schedule for a medication."""
    med = get_medication_by_id(med_id)
    if not med:
        flash("Medication not found", 'error')
        return redirect(url_for('schedules'))

    existing = get_schedule(med_id)

    if request.method == 'POST':
        schedule_type = request.form.get('schedule_type')
        reminders_on = request.form.get('reminders_enabled') == '1'

        # Build times_data based on schedule type
        times_data = {}

        if schedule_type == 'interval_from_wake':
            interval = request.form.get('interval_hours', type=float) or 4.0
            times_data['interval_hours'] = interval

        elif schedule_type == 'monthly_injection':
            months = request.form.get('months', type=int) or 1
            times_data['months'] = months

        elif schedule_type == 'fixed':
            times = request.form.getlist('fixed_times')
            times_data['times'] = [t for t in times if t]

        add_schedule(med_id, schedule_type, times_data, reminders_on)
        flash(f"Schedule set for {med['name']}", 'success')
        return redirect(url_for('schedules'))

    return render_template('schedule_add.html',
                          medication=med,
                          existing=existing,
                          schedule_types=SCHEDULE_TYPES,
                          interval_options=INTERVAL_OPTIONS)


@app.route('/schedules/delete/<int:med_id>', methods=['POST'])
def schedule_delete(med_id):
    """Delete schedule for a medication."""
    med = get_medication_by_id(med_id)
    if med and delete_schedule(med_id):
        flash(f"Schedule removed for {med['name']}", 'success')
    return redirect(url_for('schedules'))


@app.route('/schedules/toggle/<int:med_id>', methods=['POST'])
def schedule_toggle_reminders(med_id):
    """Toggle reminders on/off for a medication."""
    enabled = request.form.get('enabled') == '1'
    med = get_medication_by_id(med_id)

    if med and toggle_reminders(med_id, enabled):
        status = "enabled" if enabled else "disabled"
        flash(f"Reminders {status} for {med['name']}", 'success')

    return redirect(url_for('schedules'))


# ============================================================
# WAKE/SLEEP EVENT ROUTES
# ============================================================

@app.route('/wake', methods=['POST'])
def wake_event():
    """Log waking up - triggers medication schedule."""
    notes = request.form.get('notes', '').strip() or None
    log_wake_event(notes=notes)
    flash("Good morning! Medication reminders started.", 'success')

    # Redirect based on where the request came from
    next_url = request.form.get('next') or url_for('dashboard')
    return redirect(next_url)


@app.route('/going-to-sleep', methods=['POST'])
def log_going_to_sleep():
    """Log going to sleep - stops medication reminders."""
    notes = request.form.get('notes', '').strip() or None
    log_sleep_event(notes=notes)
    flash("Good night! Reminders paused until you wake.", 'success')

    next_url = request.form.get('next') or url_for('dashboard')
    return redirect(next_url)


# ============================================================
# DOSE EDIT/DELETE ROUTES
# ============================================================

@app.route('/meds/history')
def meds_history():
    """View medication dose history."""
    days = request.args.get('days', 7, type=int)
    med_id = request.args.get('med_id', type=int)

    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)

    doses = get_doses_range(start_date, end_date, med_id)
    medications = get_all_medications()

    return render_template('meds_history.html',
                          doses=doses,
                          medications=medications,
                          days=days,
                          selected_med=med_id)


@app.route('/meds/dose/edit/<int:dose_id>', methods=['GET', 'POST'])
def dose_edit(dose_id):
    """Edit a dose record."""
    dose = get_dose_by_id(dose_id)
    if not dose:
        flash("Dose not found", 'error')
        return redirect(url_for('meds_history'))

    if request.method == 'POST':
        # Parse date and time
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        notes = request.form.get('notes', '').strip() or None

        if date_str and time_str:
            taken_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            if update_dose(dose_id, taken_time=taken_time, notes=notes):
                flash("Dose updated", 'success')
                return redirect(url_for('meds_history'))

    return render_template('dose_edit.html', dose=dose)


@app.route('/meds/dose/delete/<int:dose_id>', methods=['POST'])
def dose_delete(dose_id):
    """Delete a dose record."""
    if delete_dose(dose_id):
        flash("Dose deleted", 'success')
    return redirect(url_for('meds_history'))


# ============================================================
# SYMPTOM EDIT/DELETE ROUTES
# ============================================================

@app.route('/symptoms/history')
def symptoms_history():
    """View symptom history."""
    days = request.args.get('days', 7, type=int)

    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)

    symptoms = get_symptoms_range(start_date, end_date)

    return render_template('symptoms_history.html',
                          symptoms=symptoms,
                          days=days)


@app.route('/symptoms/edit/<int:symptom_id>', methods=['GET', 'POST'])
def symptom_edit(symptom_id):
    """Edit a symptom entry."""
    symptom = get_symptom_by_id(symptom_id)
    if not symptom:
        flash("Symptom entry not found", 'error')
        return redirect(url_for('symptoms_history'))

    if request.method == 'POST':
        # Parse datetime
        date_str = request.form.get('date')
        time_str = request.form.get('time')

        updates = {}
        if date_str and time_str:
            updates['timestamp'] = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        on_off = request.form.get('on_off_state')
        if on_off:
            updates['on_off_state'] = on_off

        severity = request.form.get('severity', type=int)
        if severity is not None:
            updates['severity'] = severity

        for symptom_type in ['tremor', 'rigidity', 'bradykinesia', 'dyskinesia', 'freezing', 'balance']:
            val = request.form.get(symptom_type, type=int)
            if val is not None:
                updates[symptom_type] = val

        notes = request.form.get('notes', '').strip()
        if notes:
            updates['notes'] = notes

        if update_symptom(symptom_id, **updates):
            flash("Symptom entry updated", 'success')
            return redirect(url_for('symptoms_history'))

    return render_template('symptom_edit.html', symptom=symptom)


@app.route('/symptoms/delete/<int:symptom_id>', methods=['POST'])
def symptom_delete(symptom_id):
    """Delete a symptom entry."""
    if delete_symptom(symptom_id):
        flash("Symptom entry deleted", 'success')
    return redirect(url_for('symptoms_history'))


# ============================================================
# SLEEP EDIT/DELETE/MANUAL ENTRY ROUTES
# ============================================================

@app.route('/sleep/history')
def sleep_history():
    """View sleep history."""
    days = request.args.get('days', 30, type=int)
    logs = get_sleep_logs(days)
    stats = get_sleep_stats(days)

    return render_template('sleep_history.html',
                          logs=logs,
                          stats=stats,
                          days=days)


@app.route('/sleep/manual', methods=['GET', 'POST'])
def sleep_manual():
    """Manually log a sleep session."""
    if request.method == 'POST':
        # Parse sleep date/time
        sleep_date = request.form.get('sleep_date')
        sleep_time_str = request.form.get('sleep_time')
        wake_date = request.form.get('wake_date')
        wake_time_str = request.form.get('wake_time')
        quality = request.form.get('quality', type=int)
        notes = request.form.get('notes', '').strip() or None

        if sleep_date and sleep_time_str and wake_date and wake_time_str:
            sleep_time = datetime.strptime(f"{sleep_date} {sleep_time_str}", "%Y-%m-%d %H:%M")
            wake_time = datetime.strptime(f"{wake_date} {wake_time_str}", "%Y-%m-%d %H:%M")

            log_sleep_session(sleep_time, wake_time, quality, notes)
            flash("Sleep session logged", 'success')
            return redirect(url_for('sleep'))

    return render_template('sleep_manual.html')


@app.route('/sleep/edit/<int:sleep_id>', methods=['GET', 'POST'])
def sleep_edit(sleep_id):
    """Edit a sleep record."""
    sleep_log = get_sleep_by_id(sleep_id)
    if not sleep_log:
        flash("Sleep record not found", 'error')
        return redirect(url_for('sleep_history'))

    if request.method == 'POST':
        # Parse datetimes
        sleep_date = request.form.get('sleep_date')
        sleep_time_str = request.form.get('sleep_time')
        wake_date = request.form.get('wake_date')
        wake_time_str = request.form.get('wake_time')
        quality = request.form.get('quality', type=int)
        notes = request.form.get('notes', '').strip() or None

        updates = {}
        if sleep_date and sleep_time_str:
            updates['sleep_time'] = datetime.strptime(f"{sleep_date} {sleep_time_str}", "%Y-%m-%d %H:%M")
        if wake_date and wake_time_str:
            updates['wake_time'] = datetime.strptime(f"{wake_date} {wake_time_str}", "%Y-%m-%d %H:%M")
        if quality is not None:
            updates['quality'] = quality
        if notes is not None:
            updates['notes'] = notes

        if update_sleep(sleep_id, **updates):
            flash("Sleep record updated", 'success')
            return redirect(url_for('sleep_history'))

    return render_template('sleep_edit.html', sleep_log=sleep_log)


@app.route('/sleep/delete/<int:sleep_id>', methods=['POST'])
def sleep_delete(sleep_id):
    """Delete a sleep record."""
    if delete_sleep(sleep_id):
        flash("Sleep record deleted", 'success')
    return redirect(url_for('sleep_history'))


# ============================================================
# EXERCISE EDIT/DELETE ROUTES
# ============================================================

@app.route('/exercise/history')
def exercise_history():
    """View exercise history."""
    days = request.args.get('days', 30, type=int)
    logs = get_exercise_logs(days)
    stats = get_exercise_stats(days)

    return render_template('exercise_history.html',
                          logs=logs,
                          stats=stats,
                          days=days)


@app.route('/exercise/edit/<int:exercise_id>', methods=['GET', 'POST'])
def exercise_edit(exercise_id):
    """Edit an exercise record."""
    exercise_log = get_exercise_by_id(exercise_id)
    if not exercise_log:
        flash("Exercise record not found", 'error')
        return redirect(url_for('exercise_history'))

    if request.method == 'POST':
        exercise_type = request.form.get('exercise_type', '').strip()
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        duration = request.form.get('duration', type=int)
        intensity = request.form.get('intensity')
        notes = request.form.get('notes', '').strip() or None

        updates = {}
        if exercise_type:
            updates['exercise_type'] = exercise_type
        if date_str and time_str:
            updates['start_time'] = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if duration is not None:
            updates['duration_minutes'] = duration
        if intensity:
            updates['intensity'] = intensity
        if notes is not None:
            updates['notes'] = notes

        if update_exercise(exercise_id, **updates):
            flash("Exercise record updated", 'success')
            return redirect(url_for('exercise_history'))

    return render_template('exercise_edit.html',
                          exercise_log=exercise_log,
                          exercise_types=COMMON_EXERCISES,
                          intensity_levels=INTENSITY_LEVELS)


@app.route('/exercise/delete/<int:exercise_id>', methods=['POST'])
def exercise_delete(exercise_id):
    """Delete an exercise record."""
    if delete_exercise(exercise_id):
        flash("Exercise record deleted", 'success')
    return redirect(url_for('exercise_history'))


# ============================================================
# VISUALIZATION ROUTES
# ============================================================

@app.route('/visualizations')
def visualizations():
    """Main visualizations page."""
    return render_template('visualizations.html')


@app.route('/visualizations/correlation')
def vis_correlation():
    """Medication compliance vs symptoms correlation view."""
    view_type = request.args.get('view', 'weekly')  # 'hourly' or 'weekly'
    days = request.args.get('days', 7, type=int)

    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)

    # Get data for the period
    doses = get_doses_range(start_date, end_date)
    symptoms = get_symptoms_range(start_date, end_date)
    schedules = get_all_active_schedules()

    # Prepare data for visualization
    vis_data = prepare_correlation_data(doses, symptoms, schedules, start_date, end_date, view_type)

    return render_template('vis_correlation.html',
                          view_type=view_type,
                          days=days,
                          data=vis_data)


def prepare_correlation_data(doses, symptoms, schedules, start_date, end_date, view_type):
    """Prepare data for correlation visualization."""
    # This will be used by the template to render charts
    data = {
        'labels': [],
        'compliance': [],
        'on_states': [],
        'off_states': [],
        'severity': []
    }

    if view_type == 'hourly':
        # Hourly view for the past week
        current = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())

        while current <= end:
            hour_end = current + timedelta(hours=1)

            # Count doses in this hour
            hour_doses = [d for d in doses
                         if current <= datetime.fromisoformat(d['taken_time']) < hour_end]

            # Count symptoms in this hour
            hour_symptoms = [s for s in symptoms
                            if current <= datetime.fromisoformat(s['timestamp']) < hour_end]

            on_count = sum(1 for s in hour_symptoms if s['on_off_state'] == 'on')
            off_count = sum(1 for s in hour_symptoms if s['on_off_state'] == 'off')
            avg_severity = sum(s['severity'] or 0 for s in hour_symptoms) / len(hour_symptoms) if hour_symptoms else 0

            data['labels'].append(current.strftime('%m/%d %H:00'))
            data['compliance'].append(len(hour_doses))
            data['on_states'].append(on_count)
            data['off_states'].append(off_count)
            data['severity'].append(round(avg_severity, 1))

            current = hour_end

    else:  # weekly view
        # Daily aggregation
        current = start_date

        while current <= end_date:
            day_start = datetime.combine(current, datetime.min.time())
            day_end = datetime.combine(current, datetime.max.time())

            # Count doses this day
            day_doses = [d for d in doses
                        if day_start <= datetime.fromisoformat(d['taken_time']) <= day_end]

            # Count symptoms this day
            day_symptoms = [s for s in symptoms
                           if day_start <= datetime.fromisoformat(s['timestamp']) <= day_end]

            on_count = sum(1 for s in day_symptoms if s['on_off_state'] == 'on')
            off_count = sum(1 for s in day_symptoms if s['on_off_state'] == 'off')
            avg_severity = sum(s['severity'] or 0 for s in day_symptoms) / len(day_symptoms) if day_symptoms else 0

            data['labels'].append(current.strftime('%a %m/%d'))
            data['compliance'].append(len(day_doses))
            data['on_states'].append(on_count)
            data['off_states'].append(off_count)
            data['severity'].append(round(avg_severity, 1))

            current += timedelta(days=1)

    return data


# ============================================================
# REPORT/EXPORT ROUTES
# ============================================================

@app.route('/reports')
def reports():
    """Reports and export page."""
    return render_template('reports.html')


@app.route('/reports/generate', methods=['POST'])
def reports_generate():
    """Generate a report."""
    format_type = request.form.get('format', 'pdf')
    days = request.form.get('days', 7, type=int)

    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)

    try:
        if format_type == 'pdf':
            filepath = export_pdf(start_date, end_date)
        elif format_type == 'excel':
            filepath = export_excel(start_date, end_date)
        else:
            filepath = export_csv('all', start_date, end_date)

        flash(f"Report generated: {filepath.name}", 'success')
    except Exception as e:
        flash(f"Error generating report: {e}", 'error')

    return redirect(url_for('reports'))


# ============================================================
# API ROUTES (for AJAX if needed)
# ============================================================

@app.route('/api/status')
def api_status():
    """Get current status as JSON."""
    med_status = get_medication_status_today()
    symptom_summary = get_on_off_summary_today()
    exercise_stats = get_exercise_today_stats()

    return jsonify({
        'medications': [dict(m) for m in med_status] if med_status else [],
        'symptoms': symptom_summary,
        'exercise': exercise_stats,
    })


# ============================================================
# RUN SERVER
# ============================================================

def run_server(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask development server."""
    print(f"\n{'='*50}")
    print("  PD TRACKER WEB SERVER")
    print(f"{'='*50}")
    print(f"\n  Local:   http://localhost:{port}")
    print(f"  Network: http://<your-ip>:{port}")
    print(f"\n  Press Ctrl+C to stop\n")

    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_server(debug=True)
