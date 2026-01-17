"""
Configuration for PD Tracker.

Sensitive values (API keys, phone numbers) are loaded from environment variables.
This keeps secrets out of your code - important if you ever share or backup your code.

To set environment variables on Linux, add these lines to your ~/.bashrc or ~/.profile:
    export TWILIO_ACCOUNT_SID="your_account_sid"
    export TWILIO_AUTH_TOKEN="your_auth_token"
    export TWILIO_PHONE_NUMBER="+1234567890"
    export PD_TRACKER_PHONE="+1234567890"

Then run: source ~/.bashrc (or restart your terminal)
"""

import os
from pathlib import Path


# ============================================================
# FILE PATHS
# ============================================================

# Project root directory (where setup.py is)
PROJECT_ROOT = Path(__file__).parent.parent

# Data directory for the database
DATA_DIR = PROJECT_ROOT / "data"

# Database file path
DB_PATH = DATA_DIR / "pd_tracker.db"


# ============================================================
# TWILIO CONFIGURATION (for SMS reminders)
# ============================================================

# Your Twilio Account SID (found on Twilio console dashboard)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")

# Your Twilio Auth Token (found on Twilio console dashboard)
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

# Your Twilio phone number (the one Twilio gave you, must include country code)
# Format: "+12025551234"
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

# Your personal phone number (where reminders will be sent)
# Format: "+12025551234"
USER_PHONE_NUMBER = os.environ.get("PD_TRACKER_PHONE")


# ============================================================
# REMINDER SETTINGS
# ============================================================

# How many minutes before a scheduled dose to send a reminder
REMINDER_MINUTES_BEFORE = 5

# How many minutes after a missed dose to send a "did you take it?" follow-up
FOLLOWUP_MINUTES_AFTER = 15


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def is_twilio_configured() -> bool:
    """Check if all Twilio settings are configured."""
    return all([
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN,
        TWILIO_PHONE_NUMBER,
        USER_PHONE_NUMBER,
    ])


def get_missing_twilio_config() -> list:
    """Return a list of missing Twilio configuration items."""
    missing = []
    if not TWILIO_ACCOUNT_SID:
        missing.append("TWILIO_ACCOUNT_SID")
    if not TWILIO_AUTH_TOKEN:
        missing.append("TWILIO_AUTH_TOKEN")
    if not TWILIO_PHONE_NUMBER:
        missing.append("TWILIO_PHONE_NUMBER")
    if not USER_PHONE_NUMBER:
        missing.append("PD_TRACKER_PHONE")
    return missing


def print_twilio_setup_instructions():
    """Print instructions for setting up Twilio."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           TWILIO SETUP INSTRUCTIONS                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  1. Create a Twilio account at: https://www.twilio.com/try-twilio           ║
║     (Free trial gives you $15+ credit)                                       ║
║                                                                              ║
║  2. From your Twilio Console (https://console.twilio.com):                  ║
║     - Copy your Account SID                                                  ║
║     - Copy your Auth Token                                                   ║
║     - Get a phone number (Twilio provides one free for trial)               ║
║                                                                              ║
║  3. Add these lines to your ~/.bashrc file:                                 ║
║                                                                              ║
║     export TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"          ║
║     export TWILIO_AUTH_TOKEN="your_auth_token_here"                         ║
║     export TWILIO_PHONE_NUMBER="+12025551234"                               ║
║     export PD_TRACKER_PHONE="+12025559876"                                  ║
║                                                                              ║
║  4. Run: source ~/.bashrc                                                   ║
║                                                                              ║
║  5. Test with: pd reminder test                                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
