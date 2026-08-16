#!/usr/bin/env bash

# Disable root login.

set -euo pipefail

fail() { echo "$@" 1>&2; exit 1; }

[[ $(whoami) == 'root' ]] && fail 'Do not disable root login while running as root; you might be locking yourself out!'

set -x

sudo passwd --lock root
echo -e 'PermitRootLogin no' | sudo tee -a /etc/ssh/sshd_config.d/90-disable-root-login.conf
