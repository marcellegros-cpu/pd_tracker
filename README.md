# PD Tracker

A Parkinson's Disease tracking application for monitoring medications, symptoms, sleep, and exercise.

## Features

- **Medication Management**: Track medications with dosages and schedules
- **Wake-Based Scheduling**: Medication reminders based on actual wake time, not fixed times
- **Symptom Logging**: Track ON/OFF states and individual PD symptoms
- **Sleep Tracking**: Monitor sleep quality and duration
- **Exercise Logging**: Record physical activity
- **SMS Reminders**: Twilio-based medication reminders
- **Reports & Visualizations**: Generate PDFs and view symptom correlations
- **Mobile-First Web UI**: Optimized for phone usage

## Project Structure

```
pd_tracker/
├── pd_tracker/          # Core Python modules
│   ├── database.py      # SQLite database schema
│   ├── models.py        # Medication tracking
│   ├── symptoms.py      # Symptom logging
│   ├── sleep.py         # Sleep tracking
│   ├── exercise.py      # Exercise logging
│   ├── schedules.py     # Medication scheduling system
│   ├── reminders.py     # SMS reminder logic
│   ├── export.py        # PDF/Excel report generation
│   └── cli.py           # Command-line interface
├── web/                 # Flask web application
│   ├── app.py           # Web routes and logic
│   ├── templates/       # Jinja2 templates
│   └── static/          # CSS and assets
├── scripts/             # Setup scripts
└── services/            # systemd service files
```

## Schedule Types

- **Once on waking**: Reminder when you log waking up
- **Every X hours**: Interval-based (e.g., Levodopa every 4 hours from wake time)
- **Once mid-day**: ~6 hours after waking
- **If waking at night**: For nighttime medications
- **Monthly injection**: Track periodic injections
- **Fixed daily times**: Traditional clock-based schedule
- **PRN (As needed)**: No automatic reminders

## Key Design Principles

1. **Wake-Based Timing**: Schedules adapt to actual wake time, not fixed clock times
2. **Mobile-First**: All UI designed for one-handed phone use
3. **Quick Logging**: Minimal taps to log data
4. **Privacy**: All data stored locally in SQLite

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python -m pd_tracker.database

# Run web server
python -m web.app
```

## Technologies

- Python 3.12+
- Flask (web framework)
- SQLite (database)
- Twilio (SMS notifications)
- Chart.js (visualizations)
- ReportLab (PDF generation)
