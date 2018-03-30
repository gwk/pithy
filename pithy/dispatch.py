# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
from typing import Any, Callable, Dict


class DispatchTypeError(TypeError): pass

class MethodDispatch:
  '''
  Create a single dispatch method family that dispatches on the type of the first argument.
  Note that the implementation currently dispatches on exact types only.
  TODO: MRO resolution as in singledispatch.

  Usage:
  | class C():
  |   class describe(MethodDispatch): pass
  |
  |  @describe
  |  def _(self, item:int) -> None: print(f'int: {item}')
  |
  |  @describe
  |  def _(self, item:str) -> None: print(f'str: {item}')
  |
  |  describe = describe.method() # Rebind the name from the decorator to the method descriptor.


  References:
  * https://stackoverflow.com/questions/24601722/how-can-i-use-functools-singledispatch-with-instance-methods
  * https://medium.com/@vadimpushtaev/decorator-inside-python-class-1e74d23107f6.
  TODO: better typing.
  '''

  class Descriptor:
    '''
    The descriptor gives us object-oriented method binding for both class and instance property access.
    '''
    def __init__(self, methods):
      self.methods = methods

    def __get__(self, instance, owner):
      methods = self.methods
      if instance is None:
        def dispatch(instance, arg, *args, **kwargs):
          try: method = methods[type(arg)]
          except KeyError as e: raise DispatchTypeError(type(arg)) from e
          return method(instance, arg, *args, **kwargs)
      else:
        def dispatch(arg, *args, **kwargs):
          try: method = methods[type(arg)]
          except KeyError as e: raise DispatchTypeError(type(arg)) from e
          return method(instance, arg, *args, **kwargs)
      return dispatch


  def __new__(cls, method: Callable):
    try: methods: Dict[type, Callable] = cls.methods # type: ignore
    except AttributeError:
      methods = {}
      cls.methods = methods
    sig = inspect.signature(method)
    pars = list(sig.parameters.values())
    par_self = pars[0]
    par_node = pars[1]
    assert par_self.name == 'self'
    methods[par_node.annotation] = method

  @classmethod
  def method(self):
    '''
    Create the descriptor that gives us the final appropriate dispatching method object.
    '''
    return self.Descriptor(self.methods)
