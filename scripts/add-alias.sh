#!/bin/bash
# Add PD Tracker alias to shell config

ALIAS_LINE='alias pd="source /mnt/Storage/pd_tracker/venv/bin/activate && pd"'
SHELL_RC="$HOME/.zshrc"

# Check if using bash instead
if [ -n "$BASH_VERSION" ] && [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

# Check if alias already exists
if grep -q "alias pd=" "$SHELL_RC" 2>/dev/null; then
    echo "Alias already exists in $SHELL_RC"
else
    echo "" >> "$SHELL_RC"
    echo "# PD Tracker - quick access to pd command" >> "$SHELL_RC"
    echo "$ALIAS_LINE" >> "$SHELL_RC"
    echo "Added alias to $SHELL_RC"
fi

echo ""
echo "Reload your shell config:"
echo "  source $SHELL_RC"
echo ""
echo "Then you can use 'pd' from anywhere!"
