#!/usr/bin/env bash

# See: https://dnf5.readthedocs.io/en/latest/dnf5_plugins/automatic.8.html#automatic-plugin-ref-label.

set -euo pipefail
set -x

sudo dnf install -y dnf5-plugin-automatic

echo '# Automatically apply security upgrades only.
[commands]
apply_updates = yes
upgrade_type = security
reboot = when-needed
' | sudo tee /etc/dnf/automatic.conf

# Create an override file to set the OnCalendar time to 5:00 AM.
automatic_timer_dir="/etc/systemd/system/dnf5-automatic.timer.d"
automatic_timer_file="${automatic_timer_dir}/override.conf"
sudo mkdir -p "$automatic_timer_dir"
# Write the override configuration to set the OnCalendar time to 5:00 AM
echo -e "[Timer]\nOnCalendar=*-*-* 5:00" | sudo tee "$automatic_timer_file"

sudo systemctl enable --now dnf5-automatic.timer
# Reload systemd and restart the timer to apply the changes.
sudo systemctl daemon-reload
sudo systemctl restart dnf5-automatic.timer

# List dnf5 timers; should show the dnf5-automatic service timer.
systemctl list-timers 'dnf5-*'
