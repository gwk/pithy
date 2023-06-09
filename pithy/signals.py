
import os
from signal import Handlers, SIG_DFL, SIGHUP, SIGINT, signal as register_signal_handler, Signals, SIGTERM
from types import FrameType
from typing import Any, Callable, Iterable


class DeferSignals:
  '''
  This context manager catches and buffers signals  during the execution of its body,
  then upon exit restores previous signal handlers and re-raises caught signals in order.
  '''

  def __init__(self, signals:Iterable[Signals]=(SIGHUP, SIGINT, SIGTERM)) -> None:
    signals = tuple(signals)
    self.signals = signals
    if len(set(signals)) != len(signals): raise ValueError(f'duplicate signals: {signals!r}.')

    self.deferred_signals:list[int] = []
    self.previous_handlers:dict[Signals,Callable[[int,FrameType|None],Any]|int] = {}


  def defer_signal(self, sig:int, _current_stack_frame:FrameType|None):
    'The signal handler that buffers signals.'
    self.deferred_signals.append(sig)


  def __enter__(self):
    # Replace existing handlers with deferred handler.
    for sig in self.signals:
      prev_handler = register_signal_handler(sig, self.defer_signal) or SIG_DFL # use SIG_DFL instead of None.
      assert sig not in self.previous_handlers
      self.previous_handlers[sig] = prev_handler
    return self


  def __exit__(self, *args):
    # Restore previous handlers.
    for sig, handler in self.previous_handlers.items():
      register_signal_handler(sig, handler)
    # Send deferred signals.
    for deferred_signal in self.deferred_signals:
      os.kill(os.getpid(), deferred_signal)
