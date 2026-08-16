#!/usr/bin/env bash

set -euo pipefail
set -x

sudo mkdir -p /service/vector/data
sudo mkdir -p /service/vector/conf
sudo mkdir -p /service/vector/creds

sudo chown -R vector:vector /service/vector

sudo usermod --append --groups systemd-journal vector # Allow vector user to read systemd-journal logs.
