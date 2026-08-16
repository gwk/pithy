#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail


function fail() { echo "$1" 2>&1; exit 1; }

[ $# -eq 2 ] || fail "Usage: $0 SERVICE_NAME UID"

NAME="$1"
SERVICE_HOME="/service/${NAME}"
SERVICE_UID="$2"

if id -u "${NAME}"; then
  echo "User ${NAME} already exists."
  exit 0
fi

# Create /service if it does not exist.
if [ ! -d "/service" ]; then
  sudo mkdir -p /service
  # Set appropriate SELinux context for service directory.
  sudo semanage fcontext -a -t var_lib_t "/service(/.*)?"
  sudo restorecon -R /service
fi

# Create group first so that the UID and GID match.
if group_info=$(getent group "${NAME}"); then
  echo "Group ${NAME} already exists: ${group_info}"
  if [[ "$(cut -d: -f3 <<< "${group_info}")" != "${SERVICE_UID}" ]]; then
    fail "Group ${NAME} already exists but has a different UID."
  fi
else
  sudo groupadd "${NAME}" --gid "${SERVICE_UID}"
fi

set -x

# Create user.
sudo useradd \
  --comment "Service account for ${NAME}" \
  --shell /sbin/nologin \
  --create-home \
  --home-dir "${SERVICE_HOME}" \
  --uid "${SERVICE_UID}" \
  --gid "${SERVICE_UID}" \
  "${NAME}"

# Set proper SELinux context for the service home directory.
sudo semanage fcontext -a -t var_lib_t "${SERVICE_HOME}(/.*)?"
sudo restorecon -R "${SERVICE_HOME}"

sudo find "${SERVICE_HOME}" -name '.*' -delete # Remove the bash, zsh, and .cloud-locale-test.skip files.

# Allow operator to read and write to the service home directory.
sudo chmod 770 "${SERVICE_HOME}"
sudo usermod --append --groups "${NAME}" operator
