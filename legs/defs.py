# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Dict, DefaultDict, List, NamedTuple, Tuple


class Mode(NamedTuple):
  name:str
  start:int
  invalid:int

ModeTransitions = Dict[str,Dict[str,Tuple[str,str]]]
NodeTransitions = DefaultDict[int,Dict[str,Tuple[int,str]]]
