# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from dataclasses import dataclass, field
from typing import Mapping, Self

from b2sdk._internal.application_key import FullApplicationKey
from pithy.frozendicts import frozendict
from pithy.json import JsonDict, load_json, write_json
from pithy.secrets import SecretStr
from pithy.transtruct import Transtructor


hex_re = re.compile(r'^[0-9a-fA-F]+$')
b64_re = re.compile(r'^[0-9a-zA-Z+/=]+$')


@dataclass(frozen=True)
class B2Creds:
  '''
  Backblaze B2 credentials and associated metadata.
  '''
  key_name: str
  key_id: str
  key_secret: SecretStr
  #endpoint: str
  buckets: frozendict[str,str] = field(default_factory=frozendict)
  capabilities: tuple[str,...] = ()


  def __post_init__(self) -> None:
    'Validate the capabilities.'
    if not hex_re.fullmatch(self.key_id):
      raise ValueError(f'Invalid key ID (not hex): {self.key_id!r}.')
    if not b64_re.fullmatch(self.key_secret.val):
      raise ValueError(f'Invalid key secret (not base64): {self.key_secret.val!r}.')


  @classmethod
  def from_b2(cls, key:FullApplicationKey, buckets:Mapping[str,str]) -> Self:
    'Create credentials from the `b2sdk` `FullApplicationKey` type.'

    return cls(
      key_name=key.key_name,
      key_id=key.id_,
      key_secret=SecretStr(key.application_key),
      buckets=frozendict(buckets),
      capabilities=tuple(sorted(key.capabilities)))


  @classmethod
  def load(cls, path:str) -> Self:
    'Load credentials from a JSON file.'

    with open(path) as f:
      creds_dict = load_json(f)

    return Transtructor(strict=False).transtruct(cls, creds_dict)


  def save(self, path:str) -> None:
    'Save credentials to a JSON file.'
    with open(path, 'w') as f:
      write_json(f, self.as_dict())


  def as_dict(self) -> JsonDict:
    'Return credentials as a dictionary.'
    return dict(
      key_name=self.key_name,
      key_id=self.key_id,
      key_secret=self.key_secret.val,
      #endpoint=self.endpoint,
      buckets=dict(self.buckets),
      capabilities=list(self.capabilities))
