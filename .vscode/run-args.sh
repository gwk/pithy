#!/bin/sh
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Run the argument list as a command and then print a confirmation.

"$@" && echo "done: $@"
