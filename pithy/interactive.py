# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
import sys
from code import InteractiveInterpreter
from typing import ContextManager, List

from .io import errSL
from .typing import OptBaseExc, OptTraceback, OptTypeBaseExc


class Interpreter(InteractiveInterpreter):
  '''
  Similar to code.InteractiveConsole.
  '''

  def __init__(self, locals=None, filename='<interact>') -> None:
    super().__init__(locals=locals)
    self.buffer:List[str] = []
    self.filename = filename


  def interact(self, banner='Entering interactive loop...', exit_msg='Exited interactive loop.') -> None:
    try: sys.ps1
    except AttributeError: sys.ps1 = '> '
    try: sys.ps2
    except AttributeError: sys.ps2 = '… '
    self.write(f'{banner}\n')
    needs_more_input = 0
    while 1:
      prompt = sys.ps2 if needs_more_input else sys.ps1
      try:
        line = self.raw_input(prompt)
      except EOFError:
        self.write('\n')
        break
      except KeyboardInterrupt:
        self.write('\nKeyboardInterrupt\n')
        self.buffer.clear()
        needs_more_input = 0
      else:
        needs_more_input = self.push(line)
    if exit_msg is None:
      self.write('now exiting %s...\n' % self.__class__.__name__)
    elif exit_msg != '':
      self.write('%s\n' % exit_msg)

  def push(self, line:str) -> bool:
    '''
    Push a line to the interpreter and process if it is complete.
    '''
    self.buffer.append(line)
    source = '\n'.join(self.buffer)
    needs_more_input = self.runsource(source, self.filename)
    if not needs_more_input:
      self.buffer.clear()
      return False
    return True

  def raw_input(self, prompt:str) -> str:
    '''Write a prompt and read a line.

    The returned line does not include the trailing newline.
    When the user enters the EOF key sequence, EOFError is raised.

    The base implementation uses the built-in function
    input(); a subclass may replace this with a different
    implementation.

    '''
    return input(prompt)


def interact(banner=None, locals=None):
  if locals is None:
    stack = inspect.stack()
    parent_frame_info = stack[1]
    locals = parent_frame_info.frame.f_locals
  errSL('locals:')
  for k, v in locals.items():
    rv = repr(v)
    max_width = 128
    if len(rv) > max_width:
      rv = rv[:max_width-1] + '…'
    errSL(f'  {k:<16}: {rv}')
  interpreter = Interpreter(locals=locals)
  interpreter.interact()


class ExitOnKeyboardInterrupt(ContextManager):

  def __init__(self, dbg:bool=False) -> None:
    self.dbg = dbg

  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    if isinstance(exc_value, KeyboardInterrupt) and not self.dbg:
      exit(' Keyboard interrupt.')
