# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.url import url_assuming_netloc
from utest import utest


utest('https://a.com', url_assuming_netloc, 'https://a.com')
utest('//a.com', url_assuming_netloc, '//a.com')
utest('/a.com', url_assuming_netloc, '/a.com')
utest('//a.com', url_assuming_netloc, 'a.com')
