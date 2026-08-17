# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Pure helpers for the B2 native API: URL construction, file name encoding and validation,
file info header encoding, and upload part planning.
'''

from hashlib import sha1
from typing import BinaryIO, Iterable, Mapping, Sequence
from urllib.parse import quote, unquote


api_version = 'v4'

realm_url = 'https://api.backblazeb2.com'

max_file_name_utf8_len = 1024

max_part_count = 10_000

file_info_header_prefix = 'X-Bz-Info-'

sha1_read_size = 1 << 16


def api_url(base_url:str, endpoint:str, *, version:str=api_version) -> str:
  'URL for a JSON API endpoint under `base_url`, which is the realm URL or the per-account api URL.'
  return f'{base_url}/b2api/{version}/{endpoint}'


def download_by_id_url(download_url:str, file_id:str, *, version:str=api_version) -> str:
  'URL to download a file version by its file id, under the per-account download URL.'
  return f'{download_url}/b2api/{version}/b2_download_file_by_id?fileId={quote(file_id, safe="")}'


def encode_file_name(name:str) -> str:
  'Percent-encode a file name as UTF-8 for the X-Bz-File-Name header. Slashes are left unencoded.'
  return quote(name, safe='/')


def decode_file_name(encoded:str) -> str:
  'Decode a percent-encoded file name from a response header.'
  return unquote(encoded)


def validate_file_name(name:str) -> str:
  '''
  Validate a B2 file name and return it.
  Rules per the B2 documentation: 1 to 1024 UTF-8 bytes; no leading slash or empty segments;
  no control characters (below 32) or DEL (127).
  '''
  if not name: raise ValueError('B2 file name is empty.')
  if len(name.encode()) > max_file_name_utf8_len:
    raise ValueError(f'B2 file name exceeds {max_file_name_utf8_len} UTF-8 bytes: {name[:64]!r}...')
  if name.startswith('/'): raise ValueError(f'B2 file name starts with a slash: {name!r}.')
  if any(not seg for seg in name.split('/')): raise ValueError(f'B2 file name contains an empty segment: {name!r}.')
  if any(ord(c) < 32 or ord(c) == 127 for c in name): raise ValueError(f'B2 file name contains a control character: {name!r}.')
  return name


def encode_file_info_headers(file_info:Mapping[str,str]) -> dict[str,str]:
  'Encode a file info mapping as X-Bz-Info-* headers; values are percent-encoded UTF-8.'
  return { f'{file_info_header_prefix}{key}': quote(val, safe='') for key, val in file_info.items() }


def decode_file_info_headers(headers:Iterable[tuple[str,str]]) -> dict[str,str]:
  'Decode X-Bz-Info-* response headers (matched case-insensitively) into a file info mapping.'
  prefix = file_info_header_prefix.lower()
  info:dict[str,str] = {}
  for name, val in headers:
    if name.lower().startswith(prefix):
      info[name[len(prefix):]] = unquote(val)
  return info


def parse_retry_after(val:str|None) -> float|None:
  'Parse a Retry-After header value in seconds; the HTTP-date form and malformed values yield None.'
  if val is None: return None
  try: seconds = float(val)
  except ValueError: return None
  return seconds if seconds >= 0 else None


def is_large_upload(size:int, *, threshold:int) -> bool:
  'A file strictly larger than the threshold (normally the recommended part size) is uploaded as a large file.'
  return size > threshold


def plan_part_size(size:int, *, min_part_size:int, recommended_part_size:int) -> int:
  '''
  Part size for a large upload: the recommended size, raised to the minimum,
  and raised further if needed to keep the part count within `max_part_count`.
  '''
  part_size = max(min_part_size, recommended_part_size)
  min_for_count = -(-size // max_part_count) # Ceiling division.
  return max(part_size, min_for_count)


def plan_parts(size:int, part_size:int) -> list[tuple[int,int]]:
  'Plan a large upload as a list of (offset, size) parts covering `size` bytes; all parts but the last are `part_size`.'
  if size <= 0: raise ValueError(f'plan_parts size must be positive; received {size!r}.')
  if part_size <= 0: raise ValueError(f'plan_parts part_size must be positive; received {part_size!r}.')
  parts = []
  offset = 0
  while offset < size:
    parts.append((offset, min(part_size, size - offset)))
    offset += part_size
  return parts


def compute_sha1s(f:BinaryIO, parts:Sequence[tuple[int,int]]) -> tuple[str,list[str]]:
  '''
  Compute the whole-file and per-part SHA1 hex digests in a single sequential read.
  `parts` must be contiguous (offset, size) pairs from position zero, as produced by `plan_parts`;
  the caller must first seek `f` to zero.
  '''
  whole = sha1()
  part_digests = []
  for offset, size in parts:
    part_hash = sha1()
    remaining = size
    while remaining > 0:
      chunk = f.read(min(sha1_read_size, remaining))
      if not chunk: raise ValueError(f'compute_sha1s: unexpected EOF at part offset {offset}; {remaining} bytes remaining.')
      part_hash.update(chunk)
      whole.update(chunk)
      remaining -= len(chunk)
    part_digests.append(part_hash.hexdigest())
  return whole.hexdigest(), part_digests
