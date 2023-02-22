# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from collections import Counter, defaultdict
from dataclasses import is_dataclass, asdict as dataclass_asdict
from datetime import date, datetime
from functools import cache
from itertools import zip_longest
from typing import (Any, Callable, cast, ClassVar, get_args, get_origin, get_type_hints, NamedTuple, Optional, Type, TypeVar,
  Union)

from .types import is_type_namedtuple, is_namedtuple


_T = TypeVar('_T')


SelectorFn = Callable[[type,Any],type] # A function that takes raw input data and returns the appropriate datatype.
PrefigureFn = Callable[[type,Any],Any]


class TranstructorError(Exception):

  def __init__(self, error:Exception|str, class_:type, args:Any):
    super().__init__(f'{error};\n  class: {class_};\n  args: {args!r}')



class Transtructor:
  '''
  A transtructor is an object that facilitates transforming typed data.
  It is typically used to convert parsed but softly typed data (e.g. CSV or JSON) into well-typed data.
  However it can also be used to convert between different types of strongly typed data,
  for example namedtuples from parse trees or dataclasses from other sources.

  Transtructor attempts to provide automatic conversions of many structural types while not being too magicial.

  A Transtructor instance is first configured in order to customize the transformation.
  It is then invoked using `transtructor_for` or `transtruct`.

  `transtructor_for` takes a desired type and returns a transtructor function.
  A transtructor function takes a generic value, e.g. a JSON value or a CSV row, and returns a well typed value.

  `transtruct` simply calls `transtructor_for` and then invokes the transtructor function.

  Use @selector and @prefigure to register custom helper functions on a transtructor instance.

  Selectors are functions that take a raw input value and return a type.
  These are necessary for polymorphic objects,
  such as an attribute whose type is a union or base class.

  Prefigures are functions that take a raw input value and return an altered value.
  Whether or not the alteration is a mutation of the original input value is up to the programmer for their specific case.
  '''

  def __init__(self) -> None:
    self.selectors:dict[type,SelectorFn] = {}
    self.prefigures:dict[type,PrefigureFn] = {}


  def transtruct(self, t:Type[_T], val:Any, dbg=False) -> _T:
    transtructor = self.transtructor_for(t) # type: ignore[arg-type]
    if dbg: print(f'transtructor for type:{t!r}: {transtructor!r}')
    return transtructor(val)


  @cache
  def transtructor_for(self, t:Type[_T]) -> Callable[[Any],_T]:
    '''
    Return a "transtructor" function for the desired output type.
    A transtructor function takes a single argument value and returns a transformed value of the desired output type.
    This method is cached per Transtructor instance.
    '''
    if self.selector_fn_for(t): # type: ignore[arg-type]
      return self.transtructor_for_selector(t)

    return self.transtructor_post_selector_for(t) # type: ignore[arg-type]


  @cache
  def transtructor_post_selector_for(self, t:Type[_T]) -> Callable[[Any],_T]:
    '''
    Choose a transtructor for the desired output type, but after any selector has been applied.
    This prevents infinite recursion for types whose selectors return the original type,
    which is common for class families.
    '''

    try: return primitive_transtructors[t] # type: ignore[return-value]
    except KeyError: pass

    origin = get_origin(t)
    type_args = get_args(t)
    if origin and type_args: # Generic types have an origin type and a tuple of type arguments.
      return self.transtructor_for_generic_type(t, origin=origin, type_args=type_args)

    if annotations := get_type_hints(t): # Note: annotated NamedTuple will return hints.
      return self.transtructor_for_annotated_class(t, annotations)

    if is_type_namedtuple(t):
      return self.transtructor_for_unannotated_namedtuple(t)

    return self.transtructor_for_unannotated_type(t)


  def transtructor_for_selector(self, static_type:Type[_T]) -> Callable[[Any],_T]:

    def transtruct_with_selector(val:Any) -> _T:
      type_ = static_type
      #print("transtruct_with_selector static_type:", static_type)
      while selector := self.selector_fn_for(type_): # type: ignore[arg-type]
        #print("  selector:", selector)
        subtype = selector(type_, val)
        #print("  subtype:", subtype)
        if subtype is type_:
          break
        if not issubclass(subtype, type_):
          raise TypeError(f'selector {selector} returned non-subtype {subtype} for static type {static_type}')
        type_ = subtype
      transtructor = self.transtructor_post_selector_for(type_) # type: ignore[arg-type]
      return transtructor(val)

    return transtruct_with_selector


  def transtructor_for_unannotated_type(self, class_:Type[_T]) -> Callable[[Any],_T]:

      def transtruct_unannotated_type(args:Any) -> _T:
        if type(args) is class_: return args # Already the correct type. Note that this causes referential aliasing.
        try: return class_(args) # type: ignore[call-arg]
        except Exception as e: raise TranstructorError(e, class_, args)

      return transtruct_unannotated_type


  def transtructor_for_unannotated_namedtuple(self, class_:Type[_T]) -> Callable[[Any],_T]:

      def transtruct_unannotated_namedtuple(args:Any) -> _T:
        if type(args) is class_: return args

        try:
          if is_dataclass(args): return class_(**dataclass_asdict(args))
          if is_namedtuple(args): return class_(**args._asdict())
          if isinstance(args, dict): return class_(**args)

          try: it = iter(args)
          except TypeError: pass
          else: return class_(*it) # type: ignore[call-arg]

          return class_(args) # type: ignore[call-arg]

        except Exception as e: raise TranstructorError(e, class_, args)

      return transtruct_unannotated_namedtuple


  def transtructor_for_annotated_class(self, class_:Type[_T], annotations:dict[str,Type]) -> Callable[[Any], _T]:

    # TODO: this should use __init__ annotations if they exist.
    constructor_annotations = { k:v for k, v in annotations.items()
      if k != 'return' and not k.startswith('_') and get_origin(v) != ClassVar }

    transtructors = { k: self.transtructor_for(v) for k, v in constructor_annotations.items() } # type: ignore[arg-type]

    prefigure_fn = self.prefigure_fn_for(class_) # type: ignore[arg-type]

    def transtruct_annotated_class(args:Any) -> _T:
      if prefigure_fn:
        args = prefigure_fn(class_, args)

      if type(args) is class_: return args # Already the correct type. Note that this causes referential aliasing.

      if is_type_namedtuple(type(args)): args = args._asdict()
      elif is_dataclass(args): args = dataclass_asdict(args)

      if isinstance(args, dict):
        typed_kwargs:dict[str,Any] = {}
        for name, val in args.items():
          try: transtructor = transtructors[name]
          except KeyError: continue # TODO: raise error unless this element is explicitly ignored.
          typed_kwargs[name] = transtructor(val)
        try: return class_(**typed_kwargs)
        except Exception as e: raise TranstructorError(e, class_, typed_kwargs) from e

      if type(args) in primitive_transtructors: # Single primitive arg.
        # TODO: optimize by processing and passing directly?
        args = (args,)

      # Assume `args` is a positional argument sequence.
      try: args_it = iter(args)
      except TypeError as e: raise TranstructorError('argument type is not iterable', class_, args) from e
      typed_args:list[Any] = []
      for idx, (arg, pair) in enumerate(zip_longest(args_it, transtructors.items())):
        if arg is None: break
        if pair is None:
          raise ValueError(f'{class_}: transtruct argument {idx} exceeds parameters: {constructor_annotations}')
        name, transtructor = pair
        typed_args.append(transtructor(arg))
      try:
        if is_type_namedtuple(class_):
          # For named tuple types, the args are passed as a single iterable.
          return class_(typed_args) # type: ignore[call-arg]
        else:
          return class_(*typed_args)
      except TypeError as e:
        raise TranstructorError(e, class_, typed_args) from e

    return transtruct_annotated_class


  def transtructor_for_generic_type(self, t:Type[_T], origin:Type[_T], type_args:tuple[type,...]) -> Callable[[Any],_T]:
    # The origin type is usually a runtime type, but not in the case of Union.

    if origin is Union:
      return self.transtructor_for_union_type(frozenset(type_args))

    if issubclass(origin, tuple):
      return self.transtructor_for_tuple_type(t, origin, type_args)

    if issubclass(origin, dict) and len(type_args) > 1: # Excludes Counter.
      key_type, val_type = type_args
      key_ctor = self.transtructor_for(key_type)
      val_ctor = self.transtructor_for(val_type)

      def transtruct_dict(val:Any) -> _T:
        try: items = val.items()
        except AttributeError: items = val # Attempt to use the value as an iterable of key-value pairs.
        try: return origin((key_ctor(k), val_ctor(v)) for k, v in items) # type: ignore[call-arg]
        except ValueError as e:
          raise TranstructorError(f'failed to transtruct items of type {type(val).__name__!r}', t, val) from e
      return transtruct_dict

    if issubclass(origin, (list, set, frozenset, Counter)):
      assert len(type_args) == 1
      el_type = type_args[0]
      el_ctor = self.transtructor_for(el_type)

      def transtruct_collection(val:Any) -> _T:
        return origin(el_ctor(e) for e in val) # type: ignore[call-arg]

      return transtruct_collection

    # TODO: further handling. At this point it does not make sense to just return origin,
    # because the args probably need to be considered to create well-typed values.
    raise TypeError(f'{t}: transtructor for generic type {t} not implemented.')


  def transtructor_for_tuple_type(self, type_:Type, rtt:Type, types:tuple[Type,...]) -> Callable[[Any],Any]:
    if len(types) == 2 and types[1] is cast(type, Ellipsis):
      el_transtructor = self.transtructor_for(types[0]) # type: ignore[arg-type]
      def transtruct_seq_tuple(args:Any) -> Any:
        return rtt(el_transtructor(a) for a in args)
      return transtruct_seq_tuple

    # TODO: handle sequence tuple definitions.
    transtructors = tuple(self.transtructor_for(t) for t in types) # type: ignore[arg-type]

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


  def transtructor_for_union_type(self, types:frozenset[Type]) -> Callable[[Any],Any]:

    if len(types) == 2 and type(None) in types:
      variant_type = next(t for t in types if t is not type(None))
      transtructor = self.transtructor_for(variant_type) # type: ignore[arg-type]
      def transtruct_union(val:Any) -> Any:
        if val is None: return None
        return transtructor(val)

      return transtruct_union

    raise NotImplementedError('Union types other than Optional are not yet supported.')


  def selector(self, datatype:type) -> Callable[[SelectorFn],SelectorFn]:
    '''
    Function decorator that registers a selector function for the given datatype.
    A selector is a function called on the input data that returns the type to construct.
    This is the method by which transtructors can handle polymorphic input data.
    '''
    def selector_decorator(fn:SelectorFn) -> SelectorFn:
        self.selectors[datatype] = fn
        return fn
    return selector_decorator


  def prefigure(self, datatype:type) -> Callable[[PrefigureFn],PrefigureFn]:
    '''
    Function decorator that registers a prefigure function for the given datatype.
    The decorated function takes input data and manipulates it prior to being passed to the constructor.
    This is the method by which transtructors can handle misshapen or otherwise raw data.
    '''
    def prefigure_decorator(fn:PrefigureFn) -> PrefigureFn:
        self.prefigures[datatype] = fn
        return fn
    return prefigure_decorator


  @cache
  def selector_fn_for(self, datatype:type) -> Optional[SelectorFn]:
    '''
    Returns the selector function for the given datatype, or None if no selector function is registered.
    This method uses the MRO of the datatype to find base class implementations and caches the result.

    This method is cached per constructor instance because it is called by the `transtruct_with_selector` closure.
    '''
    mro = getattr(datatype, '__mro__', (datatype,))
    for t in mro:
      try: return self.selectors[t]
      except KeyError: pass
    return None


  @cache
  def prefigure_fn_for(self, datatype:type) -> Optional[PrefigureFn]:
    '''
    Returns the prefigure function for the given datatype, or None if no prefigure function is registered.
    This method uses the MRO of the datatype to find base class implementations and caches the result.
    '''
    mro = getattr(datatype, '__mro__', (datatype,))
    for t in mro:
      try: return self.prefigures[t]
      except KeyError: pass
    return None


def transtruct_bool(v:Any) -> bool:
  try: return bool_vals[v]
  except KeyError: pass
  return bool(v)


def transtruct_None(v:Any) -> None:
  if v is None: return None
  raise ValueError(f'Expected None, received {v!r}.')


def transtruct_type(v:Any) -> type:
  if isinstance(v, type): return v
  if isinstance(v, str):
    try: return named_types[v.lower()]
    except KeyError: pass
  raise ValueError(f'Expected type name (str), received {v}.')


primitive_transtructors = {
  bool: transtruct_bool,
  int: int,
  float: float,
  str: str,
  type(None): transtruct_None,
  type: transtruct_type,
}


named_types = {
  'blob': bytes,
  'bool': bool,
  'boolean': bool,
  'bytearray': bytearray,
  'bytes': bytes,
  'counter': Counter,
  'date': date,
  'datetime': datetime,
  'defaultdict': defaultdict,
  'dict': dict,
  'double': float,
  'enum': str,
  'float': float,
  'frozenset': frozenset,
  'id': int,
  'int': int,
  'integer': int,
  'list': list,
  'long': int,
  'None': type(None),
  'object': object,
  'set': set,
  'str': str,
  'string': str,
  'tuple': tuple,
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
