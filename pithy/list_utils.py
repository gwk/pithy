'list utilities.'


def sorted_list_index(a, x):
  '''
  Locate the leftmost value exactly equal to x.
  From stdlib bisect documentation.
  '''
  i = bisect_left(a, x)
  if i != len(a) and a[i] == x:
    return i
  raise ValueError

def sorted_list_find_lt(a, x):
  '''
  Find rightmost value less than x.
  From stdlib bisect documentation.
  '''
  i = bisect_left(a, x)
  if i:
    return a[i-1]
  raise ValueError

def sorted_list_find_le(a, x):
  '''
  Find rightmost value less than or equal to x.
  From stdlib bisect documentation.
  '''
  i = bisect_right(a, x)
  if i:
    return a[i-1]
  raise ValueError

def sorted_list_find_gt(a, x):
  '''
  Find leftmost value greater than x.
  From stdlib bisect documentation.
  '''
  i = bisect_right(a, x)
  if i != len(a):
    return a[i]
  raise ValueError

def sorted_list_find_ge(a, x):
  '''Find leftmost item greater than or equal to x.
  From stdlib bisect documentation.
  '''
  i = bisect_left(a, x)
  if i != len(a):
    return a[i]
  raise ValueError
