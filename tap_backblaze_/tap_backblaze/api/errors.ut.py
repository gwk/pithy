# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from tap_backblaze.api.errors import (b2_error_for_response, B2Error, B2ExpiredAuthToken, B2NotFound, B2ServerError,
  B2ServiceUnavailable, B2TooManyRequests, B2Unauthorized, is_retryable, max_retry_delay, retry_delay)
from utest import utest, utest_type, utest_val


# Error body to exception class mapping.

utest_type(B2Unauthorized, b2_error_for_response, 401, '{"status": 401, "code": "unauthorized", "message": "no"}')
utest_type(B2Unauthorized, b2_error_for_response, 401, '{"status": 401, "code": "bad_auth_token", "message": "bad token"}')
utest_type(B2ExpiredAuthToken, b2_error_for_response, 401, '{"status": 401, "code": "expired_auth_token", "message": "e"}')
utest_type(B2NotFound, b2_error_for_response, 404, '{"status": 404, "code": "not_found", "message": "gone"}')
utest_type(B2TooManyRequests, b2_error_for_response, 429, '{"status": 429, "code": "too_many_requests", "message": "slow"}')
utest_type(B2ServiceUnavailable, b2_error_for_response, 503, '{"status": 503, "code": "service_unavailable", "message": "s"}')
utest_type(B2ServerError, b2_error_for_response, 500, '{"status": 500, "code": "internal_error", "message": "oops"}')
utest_type(B2Error, b2_error_for_response, 400, '{"status": 400, "code": "bad_request", "message": "bad"}')

err = b2_error_for_response(400, '{"status": 400, "code": "bad_request", "message": "no such bucket"}')
utest_val(400, err.status, 'status')
utest_val('bad_request', err.code, 'code')
utest_val('no such bucket', err.message, 'message')
utest_val("B2 API error: status 400; code 'bad_request'; no such bucket", str(err), 'str')

# A non-JSON body is tolerated; the raw body becomes the message.
err = b2_error_for_response(503, '<html>Service Unavailable</html>')
utest_val('', err.code, 'code of non-JSON body')
utest_val('<html>Service Unavailable</html>', err.message, 'message of non-JSON body')
utest_type(B2ServiceUnavailable, lambda: err)

# A body missing `code` is tolerated.
err = b2_error_for_response(500, '{"message": "m"}')
utest_val('', err.code, 'missing code')
utest_val('m', err.message, 'message')

# Retry-After is carried on the error.
err = b2_error_for_response(429, '{"code": "too_many_requests", "message": "m"}', retry_after=7.0)
utest_val(7.0, err.retry_after, 'retry_after')


# is_retryable for each status.

def retryable_for(status:int) -> bool: return is_retryable(b2_error_for_response(status, '{}'))

utest(False, retryable_for, 400)
utest(False, retryable_for, 401)
utest(False, retryable_for, 403)
utest(False, retryable_for, 404)
utest(True, retryable_for, 429)
utest(True, retryable_for, 500)
utest(True, retryable_for, 502)
utest(True, retryable_for, 503)


# retry_delay: monotonicity, cap, and Retry-After precedence.

utest(1.0, retry_delay, 0)
utest(2.0, retry_delay, 1)
utest(4.0, retry_delay, 2)
prev = 0.0
for attempt in range(12):
  delay = retry_delay(attempt)
  assert delay >= prev, (attempt, delay, prev)
  assert delay <= max_retry_delay, (attempt, delay)
  prev = delay
utest(max_retry_delay, retry_delay, 100)
utest(7.5, retry_delay, 0, 7.5) # Retry-After takes precedence.
utest(7.5, retry_delay, 9, 7.5)
utest(0.0, retry_delay, 3, 0.0) # An explicit zero Retry-After is honored.
