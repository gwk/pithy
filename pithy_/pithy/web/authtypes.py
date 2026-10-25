# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Authentication results and access requirements, shared without depending on request or handler classes.

Import these names from `pithy.web.auth` in application code.
'''

from dataclasses import dataclass


_context_keywords_ = ['anonymous', 'authentication', 'authorization', 'privileges']


type Privileges = frozenset[str]
'Application privilege names, matched exactly with no reserved names or namespace syntax.'


@dataclass(frozen=True)
class AuthenticationResult:
  '''
  Validated authentication state and effective application privileges.

  An unauthenticated caller must have no privileges. An authenticated caller may have none.
  The server copies both fields to the Request before resolving its destination.
  '''
  is_authenticated:bool = False
  'Whether the caller has authenticated, independently of its privileges.'

  privileges:Privileges = frozenset()
  'Effective application privileges granted to the caller.'

  def __post_init__(self) -> None:
    if not isinstance(self.is_authenticated, bool): raise TypeError('is_authenticated must be a bool.')
    _validate_privileges(self.privileges)
    if not self.is_authenticated and self.privileges:
      raise ValueError('Unauthenticated callers cannot have privileges.')


@dataclass(frozen=True)
class Access:
  '''
  Validated route requirements for authentication and application privileges.

  Public access requires neither authentication nor privileges. Nonempty privileges require authentication.
  Use the access decorators in application code, or construct Access directly for custom destinations.
  '''
  requires_authentication:bool = False
  'Whether the caller must authenticate; False means public access.'

  privileges:Privileges = frozenset()
  'Every application privilege that the caller must hold.'

  def __post_init__(self) -> None:
    if not isinstance(self.requires_authentication, bool): raise TypeError('requires_authentication must be a bool.')
    _validate_privileges(self.privileges)
    if not self.requires_authentication and self.privileges:
      raise ValueError('Requiring privileges also requires authentication.')


def _validate_privileges(privileges:Privileges) -> None:
  if not isinstance(privileges, frozenset): raise TypeError('Privileges must be a frozenset of privilege names.')
  if any(not isinstance(name, str) or not name for name in privileges):
    raise TypeError('Privilege names must be nonempty strings.')
