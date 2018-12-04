# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, List, NamedTuple, Tuple


class Ctx(NamedTuple):
  build_dir: str
  coverage: bool
  dbg: bool
  fail_fast: Callable[..., None]
  interactive: bool
  parse_only: bool
  proj_dir: str
  show_times: bool
  top_paths: Tuple[str, ...]

