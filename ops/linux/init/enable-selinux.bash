#!/usr/bin/env bash

set -euo pipefail
set -x

sudo yum install -y policycoreutils-python-utils python3-policycoreutils

sudo sed -i 's/^SELINUX=permissive/SELINUX=enforcing/' /etc/selinux/config

sudo setenforce 1
sudo getenforce
