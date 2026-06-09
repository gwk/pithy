#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import math
from datetime import date, datetime, time
from typing import Any, Mapping

import tomli_w
from pithy.fs import real_path, walk_files
from pithy.iterable import fan_by_key_fn
from pithy.json import load_json
from pithy.path import path_dir, path_ext, path_join
from pithy.type_utils import req_type
from tomul import load_toml, parse_toml, render_toml
from utest import utest, utest_val


tomli_w._writer.MAX_LINE_LENGTH = 128


def reference_dumps(obj:Mapping[str,Any]) -> str:
  return tomli_w.dumps(obj, multiline_strings=True, indent=2)


def main() -> None:
  test_dir = path_dir(real_path(__file__))
  test_data_dir = path_join(test_dir, 'toml-test-data', 'valid')
  ext_paths = fan_by_key_fn(walk_files(test_data_dir), key=path_ext)
  for ext, paths in ext_paths.items():
    if ext not in ('.toml', '.json'):
      print('Unexpected files:', paths)

  json_paths = ext_paths['.json']
  toml_paths = ext_paths['.toml']

  for json_path, toml_path in zip(json_paths, toml_paths, strict=True):
    with open(toml_path, 'rb') as f: # Do not normalize newlines.
      loaded = load_toml(f)
    with open(json_path) as f:
      expected_tagged = load_json(f)

    expected = convert_tagged(expected_tagged)
    utest(True, is_equal, loaded, expected, _utest_label=toml_path)

    assert isinstance(loaded, dict)

    dumped = reference_dumps(loaded)
    rendered = render_toml(loaded)

    if dumped != rendered:
      if (dumped, rendered) not in known_differences:
        utest_val(dumped, rendered, 'rendered', _utest_label=toml_path)

    try: reparsed = parse_toml(rendered)
    except:
      print(f'{toml_path}: parse error;\nrendered repr:\n{rendered!r}\nrendered text:\n{rendered}')
      raise
    utest(True, is_equal, loaded, reparsed, _utest_label=toml_path)


def convert_tagged(obj:object) -> object:
  if isinstance(obj, list):
    return [convert_tagged(item) for item in obj]
  if isinstance(obj, dict):
    if set(obj.keys()) == {'type', 'value'}:
      type_str = req_type(obj['type'], str)
      value = req_type(obj['value'], str)
      return convert_tagged_value(type_str, value)
    return {k: convert_tagged(v) for k, v in obj.items()}
  raise TypeError(f'unexpected JSON structure: {obj!r}')


def convert_tagged_value(type_tag:str, value:str) -> object:
  if type_tag == 'string': return value
  if type_tag == 'bool': return str_to_bool[value]
  if type_tag == 'integer': return int(value)
  if type_tag == 'float': return float(value)
  if type_tag == 'datetime': return datetime.fromisoformat(value)
  if type_tag == 'datetime-local': return datetime.fromisoformat(value)
  if type_tag == 'date-local': return date.fromisoformat(value)
  if type_tag == 'time-local': return time.fromisoformat(value)
  raise ValueError(f'unknown type tag: {type_tag!r}')


str_to_bool = dict(true=True, false=False)


def is_equal(a:object, b:object) -> bool:
  '''
  Recursive equality:
  * disallows cross-type equality (bool/int/float).
  * treats any NaN == any NaN; required because float('nan') != float('nan').
  '''
  if type(a) is not type(b): return False # Do not allow bool/int/float comparison.
  if isinstance(a, float) and isinstance(b, float):
    return (math.isnan(a) and math.isnan(b)) or a == b
  if isinstance(a, dict) and isinstance(b, dict):
    if a.keys() != b.keys(): return False
    return all(is_equal(a[k], b[k]) for k in a)
  if isinstance(a, list) and isinstance(b, list):
    if len(a) != len(b): return False
    return all(is_equal(x, y) for x, y in zip(a, b))
  return a == b


known_differences = frozenset([
  ( 'str2 = """\nRoses are red\nViolets are blue"""\nstr3 = """\nRoses are red\nViolets are blue"""\n',
    'str2 = """\nRoses are red\nViolets are blue"""\nstr3 = """\nRoses are red\\r\nViolets are blue"""\n'),
])

main()
