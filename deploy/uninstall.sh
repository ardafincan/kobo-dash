#!/usr/bin/env bash
# Stop and remove the Kobo Dashboard launchd jobs from this machine.
set -euo pipefail
AGENTS="$HOME/Library/LaunchAgents"
for name in render serve; do
    label="com.kobo-dash.$name"
    launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
    rm -f "$AGENTS/$label.plist"
    echo "removed $label"
done
