# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from collections import Counter
from itertools import zip_longest
from typing import Any, Callable, NamedTuple, Optional, Type, TypeVar, Union, cast, get_type_hints


_T = TypeVar('_T')


def transtructor_for(t:Type[_T]) -> Callable[[Any],_T]:
  '''
  Return a "transtructor" for the given type.
  A transtructor takes a generic value, e.g. a JSON value or a CSV row, and returns a well type value.
  Transtructors are recursive functions meant to alleviate the tedium of type checking parsed but softly typed data values.
  '''
  try: return primitive_transtructors[t] # type: ignore
  except KeyError: pass

  if annotations := get_type_hints(t): # Includes NamedTuple.
    return transtructor_for_annotated_class(t, annotations)

  if o := getattr(t, '__origin__', None): # Generic types have an origin type.
    return transtructor_for_generic_type(t, o)

  return t


def transtructor_for_generic_type(t:Type[_T], origin:Type[_T]) -> Callable[[Any],_T]:
  # The origin type is usually a runtime type, but not in the case of Union.
  type_args = cast(tuple[Type,...], getattr(t, '__args__', ()))
  if origin is Union:
    return transtructor_for_union_type(frozenset(type_args))
  if issubclass(origin, tuple):
    return transtructor_for_tuple_type(t, origin, type_args)
  if issubclass(origin, dict) and len(type_args) > 1: # Excludes Counter.
    key_type, val_type = type_args
    key_ctor = transtructor_for(key_type)
    val_ctor = transtructor_for(val_type)
    return lambda d: origin((key_ctor(k), val_ctor(v)) for k, v in d.items()) # type: ignore
  if issubclass(origin, (list, set, frozenset, Counter)):
    assert len(type_args) == 1
    el_type = type_args[0]
    el_ctor = transtructor_for(el_type)
    return lambda v: origin(el_ctor(e) for e in v) # type: ignore
  return origin


def transtructor_for_annotated_class(class_:Type[_T], annotations:dict[str,Type]) -> Callable[[Any], _T]:
  transtructors = {k: transtructor_for(v) for k, v in annotations.items()}

  pre_transtruct_dict:Optional[Callable[[dict[str,Any]],dict[str,Any]]] = getattr(class_, 'pre_transtruct_dict', None)
  pre_transtruct_list:Optional[Callable[[list[Any]],list[Any]]] = getattr(class_, 'pre_transtruct_list', None)

  def transtruct_annotated_class(args:Any) -> _T:
    if isinstance(args, dict):
      if pre_transtruct_dict:
        args = pre_transtruct_dict(args)
      typed_kwargs:dict[str,Any] = {}
      for name, val in args.items():
        try: transtructor = transtructors[name]
        except KeyError: raise ValueError(f'{class_}: transtruct argument {name} not found in annotations.')
        typed_kwargs[name] = transtructor(val)
      return class_(**typed_kwargs)

    # Assume `args` is a positional argument list.
    if pre_transtruct_list:
      args = pre_transtruct_list(args)
    typed_args:list[Any] = []
    for idx, (arg, pair) in enumerate(zip_longest(args, transtructors.items())):
      if arg is None: break
      if pair is None:
        raise ValueError(f'{class_}: transtruct argument {idx} exceeds number of annotations.')
      name, transtructor = pair
      typed_args.append(transtructor(arg))
    if issubclass(class_, NamedTuple): return class_(typed_args) # type: ignore # For Namenamed tuple types, the args are passed as a single iterable.
    return class_(*typed_args)

  return transtruct_annotated_class


def transtructor_for_tuple_type(type_:Type, rtt:Type, types:tuple[Type,...]) -> Callable[[Any],Any]:
  # TODO: handle sequence tuple definitions.
  transtructors = tuple(transtructor_for(t) for t in types)

  def transtruct_tuple(args:Any) -> Any:
    typed_args:list[Any] = []
    for idx, (arg, transtructor) in enumerate(zip_longest(args, transtructors)):
      if arg is None:
        raise ValueError(f'{type_}: transtructor received too few arguments: {idx}.')
      if transtructor is None:
        raise ValueError(f'{type_}: transtructor argument {idx} exceeds number of type annotations.')
      typed_args.append(transtructor(arg))
    return rtt(typed_args)

  return transtruct_tuple


def transtructor_for_union_type(types:frozenset[Type]) -> Callable[[Any],Any]:
  if len(types) == 2 and NoneType in types:
    t = next(t for t in types if t is not NoneType)
    return lambda v: v if v is None else t(v)
  raise NotImplementedError('Union types other than Optional are not yet supported.')


NoneType = type(None)


def transtructor_bool(v:Any) -> bool:
  try: return bool_vals[v]
  except KeyError: pass
  return bool(v)


def transtructor_None(v:Any) -> None:
  if v is None: return None
  raise ValueError(f'Expected None, got {v}.')


primitive_transtructors = {
  NoneType: transtructor_None,
  bool: transtructor_bool,
  int: int,
  float: float,
  str: str,
}


_bool_cap_items:list[tuple[str,bool]] = [
  ('True', True),
  ('Yes', True),
  ('On', True),
  ('1', True),
  ('False', False),
  ('No', False),
  ('Off', False),
  ('0', False),
  ('T', True),
  ('F', False),
  ('Y', True),
  ('N', False),
]


bool_vals:dict[Any,bool] = dict([
  (False, False),
  (True, True),
  (0, False),
  (1, True),
  ('', False),
  *_bool_cap_items,
  *[(s.lower(), b) for (s, b) in _bool_cap_items],
  *[(s.upper(), b) for (s, b) in _bool_cap_items],
])
