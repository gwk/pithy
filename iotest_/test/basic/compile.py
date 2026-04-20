#!/usr/bin/env python3

import os
import stat


with open('compile', 'w') as f:
  print('#!/usr/bin/env python3\nprint("output from compiled script.")\n', file=f)
  fd = f.fileno()
  perms = os.stat(fd).st_mode
  os.chmod(fd, perms | stat.S_IXUSR)

