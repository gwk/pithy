# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import csv


def write_csv(f, header, rows):
  w = csv.writer(f)
  w.writerow(header)
  w.writerows(rows)

