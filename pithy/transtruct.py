# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from collections import Counter, defaultdict
from functools import cache, wraps
from itertools import zip_longest
from re import S, sub
from typing import Any, Callable, ClassVar, NamedTuple, Optional, Type, TypeVar, Union, get_args, get_origin, get_type_hints

from .io import errD


_T = TypeVar('_T')


SelectorFn = Callable[[type,Any],type] # A function that takes raw input data and returns the appropriate datatype.
PrefigureFn = Callable[[type,Any],Any]


class TranstructorError(Exception):

  def __init__(self, error:Exception, class_:type, args:Any) -> None:
    super().__init__(f'{error};\n  class: {class_};\n  args: {args!r}')



class Transtructor:
  '''
  A transtructor is an object that takes a desired type and a raw input value and returns a well-typed value.
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


  def transtruct(self, t:Type[_T], val:Any) -> _T:
    transtructor = self.transtructor_for(t) # type: ignore
    return transtructor(val)


  @cache
  def transtructor_for(self, t:Type[_T]) -> Callable[[Any],_T]:
    '''
    Return a "transtructor" function for the given type.
    A transtructor takes a generic value, e.g. a JSON value or a CSV row, and returns a well typed value.
    Transtructors are recursive functions meant to alleviate the tedium of type checking parsed but softly typed data values.
    This method is cached per Transtructor instance.
    '''
    if self.selector_fn_for(t): # type: ignore
      return self.transtructor_for_selector(t)

    return self.transtructor_post_selector_for(t) # type: ignore


  @cache
  def transtructor_post_selector_for(self, t:Type[_T]) -> Callable[[Any],_T]:
    '''
    Choose a transtructor for the given type, but after any selector has been applied.
    This prevents infinite recursion for types whose selectors return the original type,
    which is common for class families.
    '''

    try: return primitive_transtructors[t] # type: ignore
    except KeyError: pass

    origin = get_origin(t)
    type_args = get_args(t)
    if origin and type_args: # Generic types have an origin type and a tuple of type arguments.
      return self.transtructor_for_generic_type(t, origin=origin, type_args=type_args)

    if annotations := get_type_hints(t): # Note: annotated NamedTuple will return hints.
      return self.transtructor_for_annotated_class(t, annotations)

    return t


  def transtructor_for_selector(self, static_type:Type[_T]) -> Callable[[Any],_T]:

    def transtruct_with_selector(val:Any) -> _T:
      type_ = static_type
      #print("transtruct_with_selector static_type:", static_type)
      while selector := self.selector_fn_for(type_): # type: ignore
        #print("  selector:", selector)
        subtype = selector(type_, val)
        #print("  subtype:", subtype)
        if subtype is type_:
          break
        if not issubclass(subtype, type_):
          raise TypeError(f'selector {selector} returned non-subtype {subtype} for static type {static_type}')
        type_ = subtype
      transtructor = self.transtructor_post_selector_for(type_) # type: ignore
      return transtructor(val)

    return transtruct_with_selector


  def transtructor_for_annotated_class(self, class_:Type[_T], annotations:dict[str,Type]) -> Callable[[Any], _T]:

    # TODO: this should use __init__ annotations if they exist.
    constructor_annotations = { k:v for k, v in annotations.items()
      if k != 'return' and not k.startswith('_') and get_origin(v) != ClassVar }

    transtructors = { k: self.transtructor_for(v) for k, v in constructor_annotations.items() } # type: ignore[arg-type]

    prefigure_fn = self.prefigure_fn_for(class_) # type: ignore
    print("prefigure_fn:", class_, prefigure_fn)
    def transtruct_annotated_class(args:Any) -> _T:
      if isinstance(args, dict):
        if prefigure_fn:
          args = prefigure_fn(class_, args)
        typed_kwargs:dict[str,Any] = {}
        for name, val in args.items():
          try: transtructor = transtructors[name]
          except KeyError: continue
          typed_kwargs[name] = transtructor(val)
        try: return class_(**typed_kwargs)
        except Exception as e: raise TranstructorError(e, class_, typed_kwargs) from e

      if type(args) in primitive_transtructors: # Single primitive arg.
        # TODO: optimize by processing and passing directly?
        args = (args,)

      # Assume `args` is a positional argument sequence.
      if prefigure_fn:
        args = prefigure_fn(class_, args)
      typed_args:list[Any] = []
      for idx, (arg, pair) in enumerate(zip_longest(args, transtructors.items())):
        if arg is None: break
        if pair is None:
          raise ValueError(f'{class_}: transtruct argument {idx} exceeds parameters: {constructor_annotations}')
        name, transtructor = pair
        typed_args.append(transtructor(arg))
      try:
       if issubclass(class_, NamedTuple): return class_(typed_args) # type: ignore # For named tuple types, the args are passed as a single iterable.
       else: return class_(*typed_args)
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
        return origin((key_ctor(k), val_ctor(v)) for k, v in items) # type: ignore

      return transtruct_dict

    if issubclass(origin, (list, set, frozenset, Counter)):
      assert len(type_args) == 1
      el_type = type_args[0]
      el_ctor = self.transtructor_for(el_type)

      def transtruct_collection(val:Any) -> _T:
        return origin(el_ctor(e) for e in val) # type: ignore

      return transtruct_collection

    # TODO: further handling. At this point it does not make sense to just return origin,
    # because the args probably need to be considered to create well-typed values.
    raise TypeError(f'{t}: transtructor for generic type {t} not implemented.')


  def transtructor_for_tuple_type(self, type_:Type, rtt:Type, types:tuple[Type,...]) -> Callable[[Any],Any]:
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
      transtructor = self.transtructor_for(variant_type) # type: ignore
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
    The decorated function takes input data and manipulates it prior to being passed to the  constructor.
    This is the method by which transtructors can handle misshapen data.
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


def transtructor_bool(v:Any) -> bool:
  try: return bool_vals[v]
  except KeyError: pass
  return bool(v)


def transtructor_None(v:Any) -> None:
  if v is None: return None
  raise ValueError(f'Expected None, got {v!r}.')


def transtructor_type(v:Any) -> type:
  try: return named_types[v]
  except KeyError: pass
  raise ValueError(f'Expected type name (str), got {v}.')


primitive_transtructors = {
  bool: transtructor_bool,
  int: int,
  float: float,
  str: str,
  type(None): transtructor_None,
  type: transtructor_type,
}


named_types = {
  'bool': bool,
  'bytearray': bytearray,
  'bytes': bytes,
  'Counter': Counter,
  'defaultdict': defaultdict,
  'dict': dict,
  'float': float,
  'frozenset': frozenset,
  'int': int,
  'list': list,
  'None': type(None),
  'set': set,
  'str': str,
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
