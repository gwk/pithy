#! /usr/bin/env bash

# Enable the operator user.

# curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/gwk/pithy/refs/heads/main/ops/linux/init/setup-operator-user.bash | bash

# The operator user is intended to be used interactively to administer the server.
# It has sudo and systemd journal permissions.
# The primary group of operator is `root`.

set -euxo pipefail

sudo mkdir -p /home/operator
sudo touch /home/operator/.zshrc # Create an empty zshrc. Prevents the interactive setup on login.
sudo chown operator:root /home/operator/.zshrc
sudo cp -r .ssh /home/operator/

sudo semanage fcontext -a -t user_home_dir_t '/home/operator(/.*)?'
sudo semanage fcontext -a -t ssh_home_t '/home/operator/.ssh(/.*)?'
sudo chown -R operator:root /home/operator
sudo restorecon -r /home/operator
sudo chmod 700 /home/operator

sudo usermod --home /home/operator operator
sudo chsh -s $(which zsh) operator # Change shell from nologin to zsh.

echo "operator ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/91-operator # Allow operator to sudo without password.
sudo usermod --append --groups adm,systemd-journal operator # Allow operator to read system and systemd-journal logs.

# Make it possible for `operator` to look at sshd config via the `root` group.
sudo chmod g+r /etc/ssh/sshd_config
sudo chmod g+rx /etc/ssh/sshd_config.d
