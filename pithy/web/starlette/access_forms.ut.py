# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.date import Date, Time
from pithy.web.starlette import (get_form_bool, get_form_int, get_form_str, req_form_bool, req_form_date, req_form_int,
  req_form_str, req_form_time_12hmp)
from starlette.datastructures import FormData
from starlette.exceptions import HTTPException
from utest import utest, utest_exc


fd = FormData({'k': '1', 'j': '0', 'z': ''})
# TODO: also test against UploadFile values, which should throw HTTPException.

utest('1', get_form_str, fd, 'k')
utest(None, get_form_str, fd, 'x')
utest('d', get_form_str, fd, 'x', default='d')

utest('1', req_form_str, fd, 'k')
utest_exc(HTTPException, req_form_str, fd, 'x')

utest(True, get_form_bool, fd, 'k')
utest(False, get_form_bool, fd, 'j')
utest(None, get_form_bool, fd, 'x')
utest(None, get_form_bool, fd, 'z')
utest(True, get_form_bool, fd, 'x', default=True)
utest(False, get_form_bool, fd, 'x', default=False)
utest(True, get_form_bool, fd, 'z', default=True)
utest(False, get_form_bool, fd, 'z', default=False)

utest(True, req_form_bool, fd, 'k')
utest(False, req_form_bool, fd, 'j')
utest_exc(HTTPException, req_form_bool, fd, 'x')
utest_exc(HTTPException, req_form_bool, fd, 'z')

utest(1, get_form_int, fd, 'k')
utest(None, get_form_int, fd, 'x')
utest(None, get_form_int, fd, 'z')
utest(1, get_form_int, fd, 'x', default=1)
utest(1, get_form_int, fd, 'z', default=1)

utest(1, req_form_int, fd, 'k')
utest_exc(HTTPException, req_form_int, fd, 'x')
utest_exc(HTTPException, req_form_int, fd, 'z')

utest(Date(2000, 1, 1), req_form_date, FormData({'d': '2000-01-01'}), 'd')
utest_exc(HTTPException, req_form_date, FormData({'d': '!2000-01-01'}), 'd')
utest_exc(HTTPException, req_form_date, FormData(), 'x')

utest(Time(12, 34), req_form_time_12hmp, FormData({'t': '12:34PM'}), 't')
utest_exc(HTTPException, req_form_time_12hmp, FormData({'t': '!12:34PM'}), 't')
utest_exc(HTTPException, req_form_time_12hmp, FormData(), 'x')
