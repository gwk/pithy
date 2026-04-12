# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.idx_masks import idx_mask_for_length, idx_mask_for_range, idx_ranges_for_mask
from utest import utest


# idx_mask_for_range.
utest(0, idx_mask_for_range, range(0, 0))
utest(0, idx_mask_for_range, range(1, 1))
utest(0b1, idx_mask_for_range, range(0, 1))
utest(0b110, idx_mask_for_range, range(1, 3))
utest(0b11100, idx_mask_for_range, range(2, 5))
utest(0b10101, idx_mask_for_range, range(0, 5, 2))

# idx_ranges_for_mask.
utest([], idx_ranges_for_mask, 0)
utest([range(0, 1)], idx_ranges_for_mask, 0b1)
utest([range(1, 3), range(5,6)], idx_ranges_for_mask, 0b100110)

# idx_mask_for_length.
utest(0, idx_mask_for_length, 0)
utest(0b1, idx_mask_for_length, 1)
utest(0b11, idx_mask_for_length, 2)
utest(0b111, idx_mask_for_length, 3)
