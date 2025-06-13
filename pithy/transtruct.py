# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import asdict as dataclass_asdict
from datetime import date, datetime
from functools import cache
from itertools import zip_longest
from types import UnionType
from typing import Any, cast, ClassVar, get_args, get_origin, get_type_hints, TypeVar, Union

from .type_utils import is_dataclass_instance, is_namedtuple, is_type_namedtuple


Desired = TypeVar('Desired')
Ctx = Any
Input = Any

type SelectorFn = Callable[[type,Input,Ctx],type] # A function that takes raw input data and returns the appropriate output datatype.
type PrefigureFn = Callable[[type,Input,Ctx],Input] # A function that takes raw input data and modifies or replaces it before transtruction.
type TranstructFn[Desired] = Callable[[Input,Ctx],Desired] # A function thta takes raw input data and returns transtructed output data.


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
  Whether or not the alteration is a mutation of the original input value is up to the programmer to decide.
  Mutating original values can be faster, but care must be taken to avoid aliasing problems.
  For example, mutating a list/dict from a JSON tree is safe so long as the JSON library does not reuse
  substructure, and the transtructor is the only consumer of the tree.
  '''

  def __init__(self) -> None:
    self.selectors:dict[type,SelectorFn] = {}
    self.prefigures:dict[type,PrefigureFn] = {}


  def transtruct(self, desired_type:type[Desired], val:Input, *, ctx:Ctx=None, dbg=False) -> Desired:
    try:
      transtructor:TranstructFn[Desired] = self.transtructor_for(desired_type) # type: ignore[arg-type]
    except TypeError as e:
      e.add_note(f'transtruct argument 1 should be the desired type; received: `{repr(desired_type)[:64]}…`')
      raise
    if dbg: print(f'transtructor for type:{desired_type!r}: {transtructor!r}')
    return transtructor(val, ctx)


  @cache
  def transtructor_for(self, desired_type:type[Desired]) -> TranstructFn[Desired]:
    '''
    Return a "transtructor" function for the desired output type.
    A transtructor function takes a single argument value and returns a transformed value of the desired output type.

    This method is cached per Transtructor instance because the results should be deterministic per type.
    This means that the transtructor instance must not be further customized after the first call to this method.
    '''
    if self.selector_fn_for(desired_type): # type: ignore[arg-type]
      return self.transtructor_for_selector(desired_type)

    return self.transtructor_post_selector_for(desired_type) # type: ignore[arg-type]


  def transtructor_for_selector(self, static_type:type[Desired]) -> TranstructFn[Desired]:

    def transtruct_with_selector(val:Input, ctx:Ctx) -> Desired:
      type_ = static_type
      #print("transtruct_with_selector static_type:", static_type)
      while selector := self.selector_fn_for(type_): # type: ignore[arg-type]
        #print("  selector:", selector)
        subtype = selector(type_, val, ctx)
        #print("  subtype:", subtype)
        if subtype is type_:
          break
        if not issubclass(subtype, type_):
          raise TranstructorError(f'selector {selector} returned non-subtype {subtype} for static type {static_type}', static_type, val)
        type_ = subtype
      transtructor:TranstructFn[Desired] = self.transtructor_post_selector_for(type_) # type: ignore[arg-type]
      return transtructor(val, ctx)

    return transtruct_with_selector


  @cache
  def transtructor_post_selector_for(self, desired_type:type[Desired]) -> TranstructFn[Desired]:
    '''
    Choose a transtructor for the desired output type, but after any selector has been applied.
    This prevents infinite recursion for types whose selectors return the original type,
    which is common for class families.

    This method is cached per Transtructor instance because the results should be deterministic per type.
    It may be called repeatedly at runtime by `transtructor_for_selector`, so the caching is important.

    This means that the transtructor instance must not be further customized after the first call to this method.
    '''

    try: return primitive_transtructors[desired_type] # type: ignore[return-value]
    except KeyError: pass

    prefigure_fn = self.prefigure_fn_for(desired_type)

    origin = get_origin(desired_type)
    type_args = get_args(desired_type)
    if origin and type_args: # Generic types have an origin type and a tuple of type arguments.
      return self.transtructor_for_generic_type(desired_type, prefigure_fn, origin=origin, type_args=type_args)

    if annotations := get_type_hints(desired_type): # Note: annotated NamedTuple will return hints.
      return self.transtructor_for_annotated_class(desired_type, prefigure_fn, annotations)

    if is_type_namedtuple(desired_type):
      return self.transtructor_for_unannotated_namedtuple(desired_type, prefigure_fn)

    return self.transtructor_for_unannotated_type(desired_type, prefigure_fn)


  def transtructor_for_unannotated_type(self, class_:type[Desired], prefigure_fn:PrefigureFn|None
   ) -> TranstructFn[Desired]:

      def transtruct_unannotated_type(val:Input, ctx:Ctx) -> Desired:
        if prefigure_fn: val = prefigure_fn(class_, val, ctx)

        if type(val) is class_: return val # Already the correct type. Note that this causes referential aliasing.
        try: return class_(val) # type: ignore[call-arg]
        except Exception as e: raise TranstructorError(e, class_, val)

      return transtruct_unannotated_type


  def transtructor_for_unannotated_namedtuple(self, class_:type[Desired], prefigure_fn:PrefigureFn|None
   ) -> TranstructFn[Desired]:

      def transtruct_unannotated_namedtuple(args:Any, ctx:Ctx) -> Desired:
        if prefigure_fn: args = prefigure_fn(class_, args, ctx)

        if type(args) is class_: return args

        try:
          if is_dataclass_instance(args): return class_(**dataclass_asdict(args))
          if is_namedtuple(args): return class_(**args._asdict())
          if isinstance(args, Mapping): return class_(**args)

          try: it = iter(args)
          except TypeError: pass
          else: return class_(*it)

          return class_(args) # type: ignore[call-arg]

        except Exception as e: raise TranstructorError(e, class_, args)

      return transtruct_unannotated_namedtuple


  def transtructor_for_annotated_class(self, class_:type[Desired], prefigure_fn:PrefigureFn|None, annotations:dict[str,type]
   ) -> TranstructFn[Desired]:

    # TODO: this should use __init__ annotations if they exist.
    constructor_annotations = { k:v for k, v in annotations.items()
      if k != 'return' and not k.startswith('_') and get_origin(v) != ClassVar }

    transtructors = { k: self.transtructor_for(v) for k, v in constructor_annotations.items() }

    def transtruct_annotated_class(args:Any, ctx:Ctx) -> Desired:
      if prefigure_fn: args = prefigure_fn(class_, args, ctx)

      if type(args) is class_: return args # Already the correct type. Note that this causes referential aliasing.

      if is_type_namedtuple(type(args)): args = args._asdict()
      elif is_dataclass_instance(args): args = dataclass_asdict(args)

      if isinstance(args, Mapping):
        typed_kwargs:dict[str,Any] = {}
        for name, val in args.items():
          try: transtructor = transtructors[name]
          except KeyError: continue # TODO: raise error unless this element is explicitly ignored.
          typed_kwargs[name] = transtructor(val, ctx)
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
        typed_args.append(transtructor(arg, ctx))
      try:
        if is_type_namedtuple(class_):
          # For named tuple types, the args are passed as a single iterable.
          return class_(typed_args) # type: ignore[call-arg]
        else:
          return class_(*typed_args)
      except TypeError as e:
        raise TranstructorError(e, class_, typed_args) from e

    return transtruct_annotated_class


  def transtructor_for_generic_type(self, desired_type:type[Desired], prefigure_fn:PrefigureFn|None, origin:type[Desired],
   type_args:tuple[type,...]) -> TranstructFn[Desired]:

    # The origin type is usually a runtime type, but not in the case of Union.

    if origin in(Union, UnionType):
      return self.transtructor_for_union_type(desired_type, prefigure_fn, frozenset(type_args))

    if issubclass(origin, tuple):
      return self.transtructor_for_tuple_type(desired_type, prefigure_fn, origin, type_args)

    if issubclass(origin, dict) and len(type_args) > 1: # Excludes Counter.
      key_type, val_type = type_args
      key_ctor = self.transtructor_for(key_type)
      val_ctor = self.transtructor_for(val_type)

      def transtruct_dict(val:Input, ctx:Ctx) -> Desired:
        if prefigure_fn: val = prefigure_fn(desired_type, val, ctx)

        try: items = val.items()
        except AttributeError: items = val # Attempt to use the value as an iterable of key-value pairs.
        try: return origin((key_ctor(k, ctx), val_ctor(v, ctx)) for k, v in items) # type: ignore[return-value]
        except ValueError as e:
          raise TranstructorError(f'failed to transtruct items of type {type(val).__name__!r}', desired_type, val) from e

      return transtruct_dict

    if issubclass(origin, (list, set, frozenset, Counter)):
      assert len(type_args) == 1
      el_type = type_args[0]
      el_ttor = self.transtructor_for(el_type)

      def transtruct_collection(val:Input, ctx:Ctx) -> Desired:
        return origin(el_ttor(e, ctx) for e in val) # type: ignore[return-value]

      return transtruct_collection

    if issubclass(origin, Callable): # type: ignore[arg-type]
      return lambda val, ctx: val
      raise NotImplementedError(f'Transtructor for callable type {desired_type} not implemented; origin: {origin}.')

    # TODO: further handling. At this point it does not make sense to just return origin,
    # because the args probably need to be considered to create well-typed values.
    raise NotImplementedError(f'Transtructor for generic type {desired_type} not implemented; origin: {origin}.')


  def transtructor_for_tuple_type(self, type_:type[Desired], prefigure_fn:PrefigureFn|None, rtt:type, types:tuple[type,...]
   ) -> TranstructFn[Desired]:

    if len(types) == 2 and types[1] is cast(type, Ellipsis):
      el_transtructor = self.transtructor_for(types[0])

      def transtruct_seq_tuple(args:Any, ctx) -> Any:
        if prefigure_fn: args = prefigure_fn(type_, args, ctx)
        return rtt(el_transtructor(a, ctx) for a in args)

      return transtruct_seq_tuple

    # TODO: handle sequence tuple definitions.
    transtructors = tuple(self.transtructor_for(t) for t in types)

    def transtruct_tuple(args:Input, ctx:Ctx) -> Any: # TODO: improve type declaration to use Desired?
      if prefigure_fn: args = prefigure_fn(type_, args, ctx)

      typed_args:list[Any] = []
      for idx, (arg, transtructor) in enumerate(zip_longest(args, transtructors)):
        if arg is None:
          raise ValueError(f'{type_}: transtructor received too few arguments: {idx}.')
        if transtructor is None:
          raise ValueError(f'{type_}: transtructor argument {idx} exceeds number of type annotations.')
        typed_args.append(transtructor(arg, ctx))
      return rtt(typed_args)

    return transtruct_tuple


  def transtructor_for_union_type(self, desired_type:type[Desired], prefigure_fn:PrefigureFn|None, types:frozenset[type]
   ) -> TranstructFn[Desired]:

    if len(types) == 2 and type(None) in types:
      variant_type = next(t for t in types if t is not type(None))
      transtructor = self.transtructor_for(variant_type)

      def transtruct_optional(val:Input, ctx:Ctx) -> Any:
        if prefigure_fn: val = prefigure_fn(desired_type, val, ctx)
        if val is None: return None
        return transtructor(val, ctx)

      return transtruct_optional

    non_primitive_types = types.difference(primitive_transtructors)

    if len(non_primitive_types) > 1:
      raise NotImplementedError(f'Union types with more than one primitive type are not yet supported: {desired_type}:\n  members: {types}')

    if len(non_primitive_types) == 1:
      for non_primitive_type in non_primitive_types: break # Get the single variant.
      non_primitive_transtructor = self.transtructor_for(non_primitive_type)
    else:
      non_primitive_transtructor = None

    def transtruct_union(val:Input, ctx:Ctx) -> Any:
      if prefigure_fn: val = prefigure_fn(desired_type, val, ctx)
      if type(val) in primitive_transtructors: return val
      if non_primitive_transtructor is not None: return non_primitive_transtructor(val, ctx)
      type_names = ', '.join(sorted(t.__name__ for t in types))
      raise TranstructorError(f'expected value for type in {{{type_names}}}; received {type(val)!r}', desired_type, val)

    return transtruct_union


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
  def selector_fn_for(self, datatype:type) -> SelectorFn|None:
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


  def prefigure_fn_for(self, datatype:type) -> PrefigureFn|None:
    '''
    Returns the prefigure function for the given datatype, or None if no prefigure function is registered.
    This method uses the MRO of the datatype to find base class implementations and caches the result.
    '''
    mro = getattr(datatype, '__mro__', (datatype,))
    for t in mro:
      try: return self.prefigures[t]
      except KeyError: pass
    return None


def transtruct_bool(v:Input, ctx:Ctx) -> bool:
  try: return bool_vals[v]
  except KeyError: pass
  return bool(v)


def transtruct_bytes(v:Input, ctx:Ctx) -> bytes:
  if isinstance(v, bytes): return v
  raise ValueError(f'Expected bytes; received {v!r}.')


def transtruct_int(v:Input, ctx:Ctx) -> int:
  return int(v)


def transtruct_float(v:Input, ctx:Ctx) -> float:
  return float(v)


def transtruct_None(v:Input, ctx:Ctx) -> None:
  if v is None: return None
  raise ValueError(f'Expected None; received {v!r}.')


def transtruct_object(v:Input, ctx:Ctx) -> object:
  return v


def transtruct_str(v:Input, ctx:Ctx) -> str:
  return str(v)


def transtruct_type(v:Any, ctx:Ctx) -> type:
  if isinstance(v, type): return v
  if isinstance(v, str):
    try: return named_types[v.lower()]
    except KeyError: pass
  raise ValueError(f'Expected type name (str); received {v}.')


def bool_for_val(val:Any) -> bool:
  '''
  Return the corresponding boolean value for the small set of well-known bool, int, float and str values.
  Raises ValueError for all other arguments.
  '''
  try:
    return bool_vals[val]
  except Exception as e:
    raise ValueError(val) from e


def opt_bool(val:Any) -> bool|None:
  if val in (None, ''): return None
  return bool_vals.get(val)


def opt_int(val:Any) -> int|None:
  if val in (None, ''): return None
  return int(val)


NoneType = type(None)

primitive_transtructors = {
  Any: transtruct_object,
  bool: transtruct_bool,
  bytes: transtruct_bytes,
  float: transtruct_float,
  int: transtruct_int,
  NoneType: transtruct_None,
  object: transtruct_object,
  str: transtruct_str,
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
  ('False', False),
  ('Yes', True),
  ('No', False),
  ('On', True),
  ('Off', False),
  ('1', True),
  ('0', False),
  ('T', True),
  ('F', False),
  ('Y', True),
  ('N', False),
]


bool_str_vals:dict[str,bool] = dict([
  ('', False),
  *_bool_cap_items,
  *[(s.lower(), b) for (s, b) in _bool_cap_items],
  *[(s.upper(), b) for (s, b) in _bool_cap_items],
])


bool_vals:dict[Any,bool] = dict([
  (False, False),
  (True, True),
  (0, False), # Also matches 0.0.
  (1, True), # Also matches 1.0.
  *bool_str_vals.items(),
])
