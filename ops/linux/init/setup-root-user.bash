#! /usr/bin/env bash

# Configure the root user.

# The root user is not intended to be used for normal operations but can be useful.

set -euxo pipefail

sudo chsh -s $(which zsh) root # Change shell to zsh.

sudo touch /root/.zshrc # Create an empty zshrc. Prevents the interactive setup on login.
