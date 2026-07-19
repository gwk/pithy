# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import asdict as dataclass_asdict
from datetime import date, datetime, time
from functools import cache
from itertools import zip_longest
from types import UnionType
from typing import Any, cast, ClassVar, get_args, get_origin, get_type_hints, TypeVar, Union

from .frozendicts import frozendict
from .type_utils import is_dataclass_instance, is_namedtuple, is_type_namedtuple


Desired = TypeVar('Desired')
Ctx = Any
Input = Any

type SelectorFn = Callable[[type,Input,Ctx],type] # Takes the desired type, raw input, and context; returns the concrete output type to construct.
type PrefigureFn = Callable[[type,Input,Ctx],Input] # Takes the desired type, raw input, and context; returns input reshaped for transtruction.
type TranstructFn[Desired] = Callable[[Input,Ctx],Desired] # Takes raw input and context; returns transtructed output of the desired type.


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

  The `strict` flag controls handling of unrecognized keys in mapping input for struct-like desired types.
  Strict transtructors raise TranstructorError; lax ones ignore them.

  A Transtructor instance is first (optionally) configured in order to customize the transformation.
  It is then invoked using `transtructor_for` or `transtruct`.

  `transtructor_for` takes a desired type and returns a transtructor function.
  A transtructor function takes a generic value, e.g. a JSON value or a CSV row, and returns a well typed value.

  `transtruct` simply calls `transtructor_for` and then invokes the transtructor function on the provided value.

  Use @transtructor.selector and @transtructor.prefigure to register custom helper functions on a transtructor instance.
  Both dispatch on the desired (output) type, not on the runtime type of the input value.
  Registration is keyed by a type, and lookup walks that desired type's MRO, so a function registered on a base class
  also applies when constructing its subclasses.

  Selectors are functions that choose the concrete output type from the raw input value.
  These are necessary for polymorphic outputs such as an attribute whose declared type is a union or base class:
  the declared type alone does not determine what to construct, so the selector inspects the input to decide.
  A selector receives the current desired type, the raw input, and the context, and returns the type to construct.
  Selection iterates: the returned subtype is itself looked up for a selector, allowing progressive refinement,
  until a selector returns the type it was passed or no further selector is registered.

  Prefigures are functions that reshape the raw input value before the desired type is constructed.
  A prefigure receives the desired type, the raw input, and the context, and returns the altered input.
  Whether or not the alteration is a mutation of the original input value is up to the programmer to decide.
  Mutating original values can be faster, but care must be taken to avoid aliasing problems.
  For example, mutating a list/dict from a JSON tree is safe so long as the JSON library does not reuse
  substructure, and the transtructor is the only consumer of the tree.
  '''

  def __init__(self, *, strict:bool) -> None:
    self.strict = strict
    self.selectors:dict[type,SelectorFn] = {}
    self.prefigures:dict[type,PrefigureFn] = {}


  def transtruct(self, desired_type:type[Desired], val:Input, *, ctx:Ctx|None=None, dbg:bool=False) -> Desired:
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

    return try_transtruct(self.transtructor_post_selector_for(desired_type), desired_type) # type: ignore[arg-type]


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

    # Primitive types are excluded from prefigure because they are the hottest path
    # and it usually does not make sense to alter their handling across an entire value tree.
    try: return primitive_transtructors[desired_type] # type: ignore[return-value]
    except KeyError: pass

    prefigure_fn = self.prefigure_fn_for(desired_type)

    # Other scalar types (e.g. date/datetime/time) can be customized via prefigure.
    try: scalar_fn = scalar_transtructors[desired_type]
    except KeyError: pass
    else:
      if prefigure_fn:
        def prefigure_and_transtruct_scalar(val:Input, ctx:Ctx) -> Any:
          val = prefigure_fn(desired_type, val, ctx)
          return scalar_fn(val, ctx)
        return prefigure_and_transtruct_scalar
      else:
        return scalar_fn

    origin = get_origin(desired_type)
    type_args = get_args(desired_type)
    if origin and type_args: # Generic types have an origin type and a tuple of type arguments.
      return self.transtructor_for_generic_type(desired_type, prefigure_fn, origin=origin, type_args=type_args)

    init = getattr(desired_type, '__init__', None)
    if init and init is not object.__init__:
      init_hints = get_type_hints(init)
      init_hints.pop('return', None)
      if init_hints:
        return self.transtructor_for_annotated_class(desired_type, prefigure_fn, init_hints)

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

    constructor_annotations = { k:v for k, v in annotations.items()
      if k != 'return' and not k.startswith('_') and get_origin(v) != ClassVar }

    transtructors = { k: self.transtructor_for(v) for k, v in constructor_annotations.items() }

    # Plain annotation-only classes (have neither __init__ nor __new__) must be constructed manually.
    is_bare = class_.__init__ is object.__init__ and class_.__new__ is object.__new__

    strict = self.strict

    def transtruct_annotated_class(args:Any, ctx:Ctx) -> Desired:
      if prefigure_fn: args = prefigure_fn(class_, args, ctx)

      if type(args) is class_: return args # Already the correct type. Note that this causes referential aliasing.

      if is_type_namedtuple(type(args)): args = args._asdict()
      elif is_dataclass_instance(args): args = dataclass_asdict(args)

      if isinstance(args, Mapping):
        typed_kwargs:dict[str,Any] = {}
        for name, val in args.items():
          try: transtructor = transtructors[name]
          except KeyError:
            if strict: raise TranstructorError(f'unrecognized key {name!r}', class_, args) from None
            continue
          typed_kwargs[name] = transtructor(val, ctx)
        if is_bare: return _instantiate_bare(class_, constructor_annotations, typed_kwargs)
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
      if is_bare: return _instantiate_bare(class_, constructor_annotations, dict(zip(constructor_annotations, typed_args)))
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

    if issubclass(origin, (dict, frozendict)) and len(type_args) > 1: # Excludes Counter.
      key_type, val_type = type_args
      key_ctor = self.transtructor_for(key_type)
      val_ctor = self.transtructor_for(val_type)

      def transtruct_dict(val:Input, ctx:Ctx) -> Desired:
        if prefigure_fn: val = prefigure_fn(desired_type, val, ctx)

        try: items = val.items()
        except AttributeError: items = val # Attempt to use the value as an iterable of key-value pairs.
        try: return origin((key_ctor(k, ctx), val_ctor(v, ctx)) for k, v in items)
        except (ValueError, TypeError) as e:
          raise TranstructorError(f'failed to transtruct items of type {type(val).__name__!r}', desired_type, val) from e

      return transtruct_dict

    if issubclass(origin, (list, set, frozenset, Counter)):
      assert len(type_args) == 1
      el_type = type_args[0]
      el_ttor = self.transtructor_for(el_type)

      def transtruct_collection(val:Input, ctx:Ctx) -> Desired:
        return origin(el_ttor(e, ctx) for e in val)

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

      def transtruct_seq_tuple(args:Any, ctx:Ctx) -> Any:
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
    Function decorator that registers a selector function for the given desired (output) type.
    Dispatch is on the desired type, not the input value: the selector is consulted whenever a value is
    transtructed to `datatype` or one of its subclasses (lookup walks the desired type's MRO).
    The selector is called with the current desired type, the raw input value, and the context, and returns the
    concrete type to construct; it must return `datatype`, a subclass of it, or the type it was passed (to stop
    refinement).
    This is the method by which transtructors can handle polymorphic output, e.g. an attribute whose declared type
    is a union or base class.
    '''
    def selector_decorator(fn:SelectorFn) -> SelectorFn:
        self.selectors[datatype] = fn
        return fn
    return selector_decorator


  def prefigure(self, datatype:type) -> Callable[[PrefigureFn],PrefigureFn]:
    '''
    Function decorator that registers a prefigure function for the given desired (output) type.
    Dispatch is on the desired type, not the input value: the prefigure is applied whenever a value is
    transtructed to `datatype` or one of its subclasses (lookup walks the desired type's MRO).
    The decorated function is called with the desired type, the raw input value, and the context, and returns input
    reshaped for the constructor (for example, a dict of keyword arguments).
    This is the method by which transtructors can handle misshapen or otherwise raw data.
    '''
    def prefigure_decorator(fn:PrefigureFn) -> PrefigureFn:
        self.prefigures[datatype] = fn
        return fn
    return prefigure_decorator


  @cache
  def selector_fn_for(self, datatype:type) -> SelectorFn|None:
    '''
    Returns the selector function for the given desired type, or None if no selector function is registered.
    This method uses the MRO of the desired type to find base class implementations, so a selector registered on a
    base class applies to its subclasses.

    This method is cached per Transtructor instance because it is called repeatedly by the `transtruct_with_selector`
    closure.
    '''
    mro = getattr(datatype, '__mro__', (datatype,))
    for t in mro:
      try: return self.selectors[t]
      except KeyError: pass
    return None


  def prefigure_fn_for(self, datatype:type) -> PrefigureFn|None:
    '''
    Returns the prefigure function for the given desired type, or None if no prefigure function is registered.
    This method uses the MRO of the desired type to find base class implementations, so a prefigure registered on a
    base class applies to its subclasses.
    '''
    mro = getattr(datatype, '__mro__', (datatype,))
    for t in mro:
      try: return self.prefigures[t]
      except KeyError: pass
    return None


def _instantiate_bare(class_:type[Desired], annotations:dict[str,type], typed_kwargs:dict[str,Any]) -> Desired:
  '''
  Instantiate an annotation-only class (no custom __init__ or __new__) and set converted values as attributes.
  Annotations absent from the input fall back to class-level defaults; an annotation with neither raises TranstructorError,
  consistent with the required-argument behavior of constructor-based classes.
  '''
  obj = class_()
  for name in annotations:
    try: val = typed_kwargs[name]
    except KeyError:
      if not hasattr(class_, name):
        raise TranstructorError(f'missing required key {name!r}', class_, typed_kwargs) from None
      continue
    setattr(obj, name, val)
  return obj


def try_transtruct(tf:TranstructFn, desired_type:type) -> TranstructFn:
  '''
  A function wrapper that takes an existing transtruct function wraps it in a try clause.
  If an exception is raised, attach a note describing the desired type and the input.
  '''
  def _try_transtruct(v:Input, ctx:Ctx) -> Any:
    try: return tf(v, ctx)
    except Exception as e:
      v_desc = repr(v)
      if len(v_desc) >= 100: v_desc = f'{v_desc[:99]}…'
      e.add_note(f'note: {tf.__name__}: desired: {desired_type}; input: {v_desc}')
      raise
  return _try_transtruct


def transtruct_bool(v:Input, ctx:Ctx) -> bool:
  try: return bool_vals[v]
  except (KeyError, TypeError):
    raise ValueError(f'Expected bool; received {type(v).__qualname__}: {v!r}.')


def transtruct_bytes(v:Input, ctx:Ctx) -> bytes:
  if isinstance(v, bytes): return v
  raise ValueError(f'Expected bytes; received {v!r}.')


def transtruct_int(v:Input, ctx:Ctx) -> int:
  if isinstance(v, float) and not v.is_integer():
    raise ValueError(f'Expected int; received non-integral float: {v!r}.')
  return int(v)


def transtruct_float(v:Input, ctx:Ctx) -> float:
  return float(v)


def transtruct_None(v:Input, ctx:Ctx) -> None:
  if v is None: return None
  raise ValueError(f'Expected None; received {v!r}.')


def transtruct_object(v:Input, ctx:Ctx) -> object:
  return v


def transtruct_str(v:Input, ctx:Ctx) -> str:
  if isinstance(v, str): return v
  raise ValueError(f'Expected str; received {type(v).__qualname__}: {v!r}.')


def transtruct_date(v:Input, ctx:Ctx) -> date:
  if isinstance(v, datetime): return v.date() # datetime is a date subclass; truncate to a pure date.
  if isinstance(v, date): return v
  if isinstance(v, str): return date.fromisoformat(v)
  raise ValueError(f'Expected date; received {type(v).__qualname__}: {v!r}.')


def transtruct_datetime(v:Input, ctx:Ctx) -> datetime:
  if isinstance(v, datetime): return v
  if isinstance(v, str): return datetime.fromisoformat(v)
  raise ValueError(f'Expected datetime; received {type(v).__qualname__}: {v!r}.')


def transtruct_time(v:Input, ctx:Ctx) -> time:
  if isinstance(v, time): return v
  if isinstance(v, str): return time.fromisoformat(v)
  raise ValueError(f'Expected time; received {type(v).__qualname__}: {v!r}.')


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


# Scalar types whose default transtructor parses a canonical format but which, unlike primitives,
# allow a prefigure to reshape the raw input first. Keyed on the exact type (no MRO walk),
# so e.g. `datetime` does not resolve to `date`'s entry by inheritance.
scalar_transtructors:dict[type,TranstructFn[Any]] = {
  date: transtruct_date,
  datetime: transtruct_datetime,
  time: transtruct_time,
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
  'frozendict': frozendict,
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
  'time': time,
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
