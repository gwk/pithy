# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from b2sdk.v3 import ALL_CAPABILITIES


all_capabilities = tuple(ALL_CAPABILITIES)

all_capabilities_and_groups = all_capabilities + ('file-ro', 'file-rw', 'file-rwd')

key_mgmt_capabilities:tuple[str, ...] = ('listKeys', 'writeKeys', 'deleteKeys')

file_ro_capabilities:tuple[str, ...] = ('listFiles', 'readFiles')
file_rw_capabilities:tuple[str, ...] = tuple(file_ro_capabilities + ('writeFiles',))
file_rwd_capabilities:tuple[str, ...] = tuple(file_rw_capabilities + ('deleteFiles',))
