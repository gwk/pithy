# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from hashlib import sha1
from io import BytesIO

from tap_backblaze.api.util import (api_url, compute_sha1s, decode_file_info_headers, decode_file_name, download_by_id_url,
  encode_file_info_headers, encode_file_name, is_large_upload, max_part_count, parse_retry_after, plan_part_size, plan_parts,
  realm_url, validate_file_name)
from utest import utest, utest_exc, utest_val


# URL construction.

utest('https://api.backblazeb2.com/b2api/v4/b2_authorize_account', api_url, realm_url, 'b2_authorize_account')
utest('https://api123.backblazeb2.com/b2api/v4/b2_list_buckets', api_url, 'https://api123.backblazeb2.com', 'b2_list_buckets')
utest('https://api123.backblazeb2.com/b2api/v9/b2_list_buckets', api_url, 'https://api123.backblazeb2.com', 'b2_list_buckets',
  version='v9')

utest('https://f001.backblazeb2.com/b2api/v4/b2_download_file_by_id?fileId=4_abc',
  download_by_id_url, 'https://f001.backblazeb2.com', '4_abc')
utest('https://f001.backblazeb2.com/b2api/v4/b2_download_file_by_id?fileId=a%2Fb%2Bc',
  download_by_id_url, 'https://f001.backblazeb2.com', 'a/b+c')


# File name encoding: unicode, spaces, '+', and '/'.

utest('simple.db', encode_file_name, 'simple.db')
utest('dir/sub/name.db', encode_file_name, 'dir/sub/name.db')
utest('a%20b', encode_file_name, 'a b')
utest('a%2Bb', encode_file_name, 'a+b')
utest('%E2%98%83.txt', encode_file_name, '☃.txt')

for name in ('simple.db', 'dir/sub/name.db', 'a b', 'a+b', '☃.txt', 'percent%41.txt'):
  utest(name, decode_file_name, encode_file_name(name), _utest_label=name)


# File info header encode and decode round trip.

utest({'X-Bz-Info-large_file_sha1': 'abc123', 'X-Bz-Info-note': 'two%20words'},
  encode_file_info_headers, {'large_file_sha1': 'abc123', 'note': 'two words'})

utest({'large_file_sha1': 'abc123', 'note': 'two words'},
  decode_file_info_headers, [('x-bz-info-large_file_sha1', 'abc123'), ('X-Bz-Info-note', 'two%20words'),
    ('Content-Type', 'application/octet-stream')])

info = {'large_file_sha1': 'ff00', 'src': 'a+b c/d'}
utest(info, decode_file_info_headers, list(encode_file_info_headers(info).items()))


# File name validation.

utest('a/b.db', validate_file_name, 'a/b.db')
utest('a'*1024, validate_file_name, 'a'*1024)
utest_exc(ValueError, validate_file_name, '')
utest_exc(ValueError, validate_file_name, 'a'*1025)
utest_exc(ValueError, validate_file_name, '☃'*342) # 342 * 3 = 1026 UTF-8 bytes.
utest_exc(ValueError, validate_file_name, '/leading')
utest_exc(ValueError, validate_file_name, 'trailing/')
utest_exc(ValueError, validate_file_name, 'a//b')
utest_exc(ValueError, validate_file_name, 'a\nb')
utest_exc(ValueError, validate_file_name, 'a\x7fb')


# Retry-After parsing.

utest(None, parse_retry_after, None)
utest(2.0, parse_retry_after, '2')
utest(1.5, parse_retry_after, '1.5')
utest(0.0, parse_retry_after, '0')
utest(None, parse_retry_after, '-1')
utest(None, parse_retry_after, 'Wed, 21 Oct 2026 07:28:00 GMT')


# The small-versus-large decision at the boundary.

utest(False, is_large_upload, 99, threshold=100)
utest(False, is_large_upload, 100, threshold=100)
utest(True, is_large_upload, 101, threshold=100)


# Part size planning.

utest(100, plan_part_size, 1000, min_part_size=50, recommended_part_size=100)
utest(50, plan_part_size, 1000, min_part_size=50, recommended_part_size=25) # The minimum wins over a small recommendation.
# A huge file raises the part size to stay within the part count cap.
utest(200, plan_part_size, 200*max_part_count, min_part_size=50, recommended_part_size=100)
utest(101, plan_part_size, 100*max_part_count + 1, min_part_size=50, recommended_part_size=100)


# Part planning.

utest([(0, 100), (100, 100), (200, 50)], plan_parts, 250, 100)
utest([(0, 100), (100, 100)], plan_parts, 200, 100)
utest([(0, 1)], plan_parts, 1, 100)
utest_exc(ValueError, plan_parts, 0, 100)
utest_exc(ValueError, plan_parts, 100, 0)


# Single-pass whole-file and per-part SHA1s.

data = b'abcdefghij'
whole, parts = compute_sha1s(BytesIO(data), [(0, 4), (4, 4), (8, 2)])
utest_val(sha1(data).hexdigest(), whole, 'whole-file sha1')
utest_val([sha1(b'abcd').hexdigest(), sha1(b'efgh').hexdigest(), sha1(b'ij').hexdigest()], parts, 'per-part sha1s')

utest((sha1(data).hexdigest(), [sha1(data).hexdigest()]), compute_sha1s, BytesIO(data), [(0, len(data))])

utest_exc(ValueError, compute_sha1s, BytesIO(b'short'), [(0, 100)]) # Unexpected EOF.
