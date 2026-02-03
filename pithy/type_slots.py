# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from .util import memoize


@memoize()
def all_slots(type:type) -> tuple[str,...]:
  '''
  Subclasses of slots classes may define their own slots, which hold just the additions to the parent class.
  Therefore we need to iterate over the inheritance chain to get all slot names.
  See: https://docs.python.org/3/reference/datamodel.html#slots.
  Note: a slot in a child class masks a slot of the same name in a parent class.
  The slots are returned in the order they are defined, from parent to child.
  '''
  slots_set: set[str] = set()
  slots_seq = []
  for t in type.__mro__: # Iterate from child to parent.
    try: raw_slots = t.__slots__ # type: ignore[attr-defined]
    except AttributeError: break # A subclass that does not define its own slots will have that of its parent; ok to stop.
    else:
      slots = (raw_slots.split() if isinstance(raw_slots, str) else raw_slots)
      for s in reversed(slots):
        if s not in slots_set: # Child slots mask parents.
          # Note: this assumes that the slot is not repeated within the class. If it is, the order will be last-wins.
          slots_set.add(s)
          slots_seq.append(s)

  return tuple(reversed(slots_seq))
