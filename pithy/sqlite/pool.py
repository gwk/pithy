# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from sys import stderr
from threading import Lock, Semaphore
from typing import Callable, Union

from . import Conn


class PoolExhaustedError(Exception): pass


@dataclass
class ConnLease:
  '''
  Temporary context manager for a Conn from a ConnPool.
  When the lease context is exited, the Conn is returned to the pool.
  '''

  pool:Union['ConnPool',None]
  conn:Conn


  def __del__(self) -> None:
    '__del__ complains unmanaged/leaked leases and attempts to release them.'
    if self.pool:
      print(f'WARNING: ConnLease.__del__: lease should have been released already: id={id(self)}.', file=stderr)
      self.release()


  def __enter__(self) -> Conn:
    'The lease returns the connection (not itself) when the context is entered.'
    return self.conn


  def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    'The lease releases the connection back to the pool (if it has not been already) when the context is exited.'
    self.release()


  def release(self) -> None:
    '''
    Release the Conn back to the pool. This operation is idempotent.
    This is useful if you want to release the Conn early, but it is not necessary if you use the context manager.
    '''
    if pool := self.pool:
      self.pool = None
      pool.release(self)




class ConnPool:
  '''
  A simple, threadsafe pool for Conn objects.
  `max_connections` is a hard limit to the total number of connections that can be created.
  `timeout` is the maximum time to wait for a connection to become available.

  ConnPool uses an internal Semaphore to limit the number of total connections created.
  When that limit is reached, further calls to acquire() will block until a connection is returned or `timeout` elapses.
  '''

  def __init__(self, *, connect:Callable[[], Conn], max_connections:int, timeout:float|None) -> None:
    self.connect = connect
    self.max_connections = max_connections
    self.timeout = timeout
    self._connections:list[Conn] = []
    self._connections_lock = Lock()
    self._semaphore = Semaphore(value=max_connections)


  def acquire(self) -> ConnLease:
    '''
    Get a ConnLease from the pool.
    The lease is intended to be used as a context manager to guarantee that it is properly released.

    This will reuse an existing connection or else create a new one by invoking `connect()`.
    If max_connections is reached, the Pool will wait for `timeout` seconds, and then raise a PoolExhaustedError.
    '''
    if not self._semaphore.acquire(timeout=self.timeout):
      raise PoolExhaustedError('ConnPool timed out.')
    # Lock access to the connections list. Technically pop() is atomic in CPython, but we want to be safe.
    with self._connections_lock:
      try: conn = self._connections.pop()
      except IndexError: conn = None
    # Release the lock before calling connect(), which is complex and subject to OS level delays/errors.
    if conn is None: conn = self.connect()
    return ConnLease(pool=self, conn=conn)


  def release(self, lease:ConnLease) -> None:
    '''
    Return a Conn to the pool.
    '''
    with self._connections_lock:
      self._connections.append(lease.conn)
    self._semaphore.release()
