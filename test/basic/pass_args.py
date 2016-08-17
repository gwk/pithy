#!/usr/bin/env python3

# args 1, 2, 3 are used for exit code, stdout, stderr.

import sys

print(sys.argv[2], file=sys.stdout)
print(sys.argv[3], file=sys.stderr)

sys.exit(int(sys.argv[1]))
