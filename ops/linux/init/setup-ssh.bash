#!/usr/bin/env bash

# Change SSH port to reduce the volume of SSH probing.
# Usage: setup-ssh.bash <port>

# The official "registered" port range is 1024-49151.
# To choose a random high port:
# SSH_PORT=$(shuf -i 1024-49151 -n 1) # Linux.
# SSH_PORT=$(jot -r 1 1024 49151) # macOS.


set -euo pipefail

fail() { echo "Error: $@" 1>&2; exit 1; }

port="${1:-}"

[[ -n "$port" ]] || fail "missing required argument: port number."
[[ "$port" =~ ^[0-9]+$ ]] || fail "port must be a number, got: $port."
ss -tlnH "sport = :$port" 2>/dev/null | grep -q . && fail "port $port appears to be already in use."

set -x

echo "Port $port" | sudo tee /etc/ssh/sshd_config.d/91-custom-port.conf

sudo semanage port -a -t ssh_port_t -p tcp "$port"
sudo semanage port -l | grep ssh_port_t | grep "$port"
#^ Verify that the port is present.

sudo sshd -t && sudo systemctl restart sshd
#^ Test and restart sshd.
