# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Generic CLI for backing up and restoring a pithy.sqlite Database group.

Because a BackupConfig is defined by the owning application,
each command takes a dotted `app` spec naming the module that defines it. See `resolve_backup_config`.
'''

from . import main_entry


if __name__ == '__main__': main_entry(None, prog='pithy.sqlite.backup')
