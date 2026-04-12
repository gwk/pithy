# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ast import dump, parse


def parse_and_dump(code:str, *, filename:str='<str>', mode:str='exec', type_comments:bool=True, feature_version:int|tuple[int,int]|None=None,
annotate:bool=True, include_attributes:bool=False, indent:int|str|None=2) -> str:
  return dump(parse(code, filename=filename, mode=mode, type_comments=type_comments, feature_version=feature_version),
    annotate_fields=annotate, include_attributes=include_attributes, indent=indent)
