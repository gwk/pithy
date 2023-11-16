# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.regex import find_match_text_interleaved, find_matches_interleaved
from utest import utest_seq, utest_val


utest_seq(['a', '1', 'b', '2', '3'], find_match_text_interleaved, r'\d', 'a1b23')
