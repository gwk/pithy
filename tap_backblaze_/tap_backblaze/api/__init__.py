# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
A client for the Backblaze B2 native API: a plain JSON-over-HTTP API.
This package covers the subset of the API that tap_backblaze uses:
authorization, buckets, uploads (small and large), downloads, file versions, and application keys.
'''

from .client import B2Client, Progress
from .errors import (b2_error_for_response, B2Error, B2ExpiredAuthToken, B2IntegrityError, B2NotFound, B2ServerError,
  B2ServiceUnavailable, B2TooManyRequests, B2Unauthorized, is_retryable, retry_delay)
from .types import (B2AllowedBucket, B2ApplicationKey, B2Auth, B2Bucket, B2CreatedApplicationKey, B2FileVersion, B2ParseError,
  B2UploadUrl)


# Silence linter by referencing imported names.

_:tuple = (B2Client, Progress,
  b2_error_for_response, B2Error, B2ExpiredAuthToken, B2IntegrityError, B2NotFound, B2ServerError,
  B2ServiceUnavailable, B2TooManyRequests, B2Unauthorized, is_retryable, retry_delay,
  B2AllowedBucket, B2ApplicationKey, B2Auth, B2Bucket, B2CreatedApplicationKey, B2FileVersion, B2ParseError, B2UploadUrl)
