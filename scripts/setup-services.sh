#!/bin/bash
# PD Tracker Service Setup Script
# This script installs systemd services for automatic startup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_DIR="$PROJECT_DIR/services"

echo "========================================"
echo "  PD Tracker Service Setup"
echo "========================================"
echo ""
echo "Project directory: $PROJECT_DIR"
echo ""

# Create environment file for services
ENV_FILE="$HOME/.pd_tracker_env"
echo "Creating environment file: $ENV_FILE"

cat > "$ENV_FILE" << 'EOF'
# PD Tracker Environment Variables
# This file is used by systemd services

# Twilio Configuration (for SMS reminders)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
PD_TRACKER_PHONE=

# Email Configuration (for reports)
PD_TRACKER_EMAIL=
PD_TRACKER_EMAIL_PASSWORD=
EOF

echo "  Created $ENV_FILE"
echo "  IMPORTANT: Edit this file and add your Twilio/email credentials"
echo ""

# Install services
echo "Installing systemd services..."

# Update service files with correct username
CURRENT_USER=$(whoami)
sed -i "s/User=marcel/User=$CURRENT_USER/" "$SERVICE_DIR/pd-reminder.service"
sed -i "s/User=marcel/User=$CURRENT_USER/" "$SERVICE_DIR/pd-web.service"

# Copy service files
sudo cp "$SERVICE_DIR/pd-reminder.service" /etc/systemd/system/
sudo cp "$SERVICE_DIR/pd-web.service" /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

echo "  Installed pd-reminder.service"
echo "  Installed pd-web.service"
echo ""

echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit your environment file:"
echo "   nano ~/.pd_tracker_env"
echo ""
echo "2. Enable and start services:"
echo "   sudo systemctl enable pd-web"
echo "   sudo systemctl start pd-web"
echo ""
echo "   sudo systemctl enable pd-reminder"
echo "   sudo systemctl start pd-reminder"
echo ""
echo "3. Check status:"
echo "   sudo systemctl status pd-web"
echo "   sudo systemctl status pd-reminder"
echo ""
echo "4. View logs:"
echo "   journalctl -u pd-web -f"
echo "   journalctl -u pd-reminder -f"
echo ""
