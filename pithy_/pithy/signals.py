# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Unix signal handling.
'''

import os
from signal import SIG_DFL, SIGHUP, SIGINT, signal as register_signal_handler, Signals, SIGQUIT, SIGTERM
from traceback import print_exception
from types import FrameType, TracebackType
from typing import Any, Callable, Iterable, Self


type SignalHandler = Callable[[int,FrameType|None],Any]|int


class DeferSignals:
  '''
  This context manager catches and buffers signals during the execution of its body,
  then upon exit restores previous signal handlers and re-raises caught signals in order.
  '''

  def __init__(self, signals:Iterable[Signals]=(SIGHUP, SIGINT, SIGTERM)) -> None:
    signals = tuple(signals)
    self.signals = signals
    if len(set(signals)) != len(signals): raise ValueError(f'duplicate signals: {signals!r}.')

    self.deferred_signals:list[int] = []
    self.previous_handlers:dict[Signals,SignalHandler] = {}


  def defer_signal(self, sig:int, _current_stack_frame:FrameType|None) -> None:
    'The signal handler that buffers signals.'
    self.deferred_signals.append(sig)


  def __enter__(self) -> DeferSignals:
    # Replace existing handlers with deferred handler.
    for sig in self.signals:
      prev_handler = register_signal_handler(sig, self.defer_signal) or SIG_DFL # use SIG_DFL instead of None.
      assert sig not in self.previous_handlers
      self.previous_handlers[sig] = prev_handler
    return self


  def __exit__(self, *args:Any) -> None:
    # Restore previous handlers.
    for sig, handler in self.previous_handlers.items():
      register_signal_handler(sig, handler)
    # Send deferred signals.
    for deferred_signal in self.deferred_signals:
      os.kill(os.getpid(), deferred_signal)


class HoldSignals:
  '''
  This context manager intercepts and holds a single received stop signal,
  so that a long-running body can stop at a safe point of its own choosing.

  During execution of the context, the HoldSignals handler will receive up to one signal and hold it in `self.held`.
  The body will not be interrupted. The body can poll `is_signal_on_hold` to stop early, but is not required to.
  Regardless, a held signal is delivered to the original handler when the block exits,
  unless the body claims responsibility for it with `discard_held_signal`.

  A second signal ends the hold. All of the previous handlers are restored, and then both signals are delivered in order.
  This reproduces what would have happened without the context manager, only later.
  For SIGTERM the delivery is usually termination; for SIGINT it is a KeyboardInterrupt, which unwinds cleanly.
  Delivering the held signal first means that a later, weaker signal cannot cancel an earlier stop request.
  If that delivery terminates the process or raises, the second signal is never delivered.
  This is not a guaranteed exit; only SIGKILL is.

  Only the stop signals in `HoldSignals.holdable_signals` can be held.
  The rest either have no useful default disposition (SIGCHLD is ignored by default, so delivering it achieves nothing)
  or carry application meanings that holding would corrupt (SIGUSR1, and SIGHUP where a daemon uses it to reload).

  If an exception is propagating when the block exits and delivering the held signal will terminate the process,
  the exception is printed first, because the termination would otherwise discard it.
  When the restored handler is a Python handler no printing is needed,
  because the resulting exception chains to the one in flight and both appear in the traceback.

  Caveats:
  * The block must be entered on the main thread, because only that thread can register handlers.
    `is_signal_on_hold` is safe to call from any thread.
  * The kernel does not queue duplicate standard signals, so two of the same number arriving before the handler runs
    are merged into one. Repeating a signal quickly does not reliably end the hold.
  * `held` is not necessarily the first signal received. Python runs pending handlers in ascending signal number,
    so a SIGTERM followed closely by a SIGINT holds the SIGINT and lets the SIGTERM end the hold.
  * A supervisor's grace period still applies. Both systemd and Kubernetes send SIGKILL after a timeout,
    so the body must reach a stop point well within it.
  '''

  holdable_signals:frozenset[Signals] = frozenset({SIGHUP, SIGINT, SIGQUIT, SIGTERM})
  'The signals that this class will hold. A subclass can widen this, but see the class docstring for why it is narrow.'


  def __init__(self, signals:Iterable[Signals]=(SIGTERM,)) -> None:
    signals = tuple(signals)
    if not signals: raise ValueError('no signals specified.')
    if len(set(signals)) != len(signals): raise ValueError(f'duplicate signals: {signals!r}.')
    if unholdable := [s for s in signals if s not in self.holdable_signals]:
      unholdable_names = ', '.join(Signals(s).name for s in unholdable)
      holdable_names = ', '.join(s.name for s in sorted(self.holdable_signals))
      raise ValueError(f'unholdable signals: {unholdable_names}; {type(self).__name__} holds only stop signals: '
        f'{holdable_names}.')
    self.signals = signals
    self.held:Signals|None = None
    self.previous_handlers:dict[Signals,SignalHandler] = {}


  def hold_signal(self, sig:int, _current_stack_frame:FrameType|None) -> None:
    '''
    The signal handler that holds the signal.
    It does not log, because it can run in the middle of the interrupted thread's own logging call.
    '''
    if self.held is None:
      self.held = Signals(sig)
      return
    # A second signal ends the hold. Clear it and restore every handler first, so that the manager is out of the way
    # before either signal is delivered; the block exit then has nothing left to do.
    held = self.held
    self.held = None
    self.restore_handlers()
    os.kill(os.getpid(), held) # If this terminates the process or raises, `sig` is never delivered.
    os.kill(os.getpid(), sig)


  def restore_handlers(self) -> None:
    'Restore the handlers that were in place before this context manager replaced them.'
    for sig, handler in self.previous_handlers.items():
      register_signal_handler(sig, handler)


  def is_signal_on_hold(self) -> bool:
    'True once a signal is being held. Poll this inside of the context manager block at points where stopping is safe.'
    return self.held is not None


  def discard_held_signal(self) -> Signals|None:
    '''
    Take responsibility for the held signal so that it is not delivered when the block exits; return it, or None.
    Use this only when the block has honored the signal by other means, e.g. by terminating the process itself.
    '''
    held = self.held
    self.held = None
    return held


  def __enter__(self) -> Self:
    if self.previous_handlers: raise ValueError('this HoldSignals is already active; create a separate instance.')
    self.held = None
    try:
      for sig in self.signals:
        self.previous_handlers[sig] = register_signal_handler(sig, self.hold_signal) or SIG_DFL # Use SIG_DFL instead of None.
    except BaseException: # Registration can fail, e.g. off the main thread; do not leave the handlers partially replaced.
      self.restore_handlers()
      self.previous_handlers.clear()
      raise
    return self


  def __exit__(self, exc_type:type[BaseException]|None, exc_value:BaseException|None, traceback:TracebackType|None) -> None:
    self.restore_handlers() # Idempotent; a second signal will already have restored them.
    held = self.held
    if held is None: # Either no signal arrived, or the body discarded it, or a second signal ended the hold.
      self.previous_handlers.clear()
      return
    self.held = None
    previous_handler = self.previous_handlers[held]
    self.previous_handlers.clear()
    if exc_value is not None and previous_handler == SIG_DFL:
      # Delivering the signal will terminate the process, discarding the exception in flight, so report it first.
      print_exception(exc_value)
    os.kill(os.getpid(), held)
