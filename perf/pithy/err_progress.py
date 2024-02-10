from sys import argv
from pithy.io import err_progress

n = int(argv[1])
every = int(argv[2])
frequency = float(argv[3])

s = 0
for i in err_progress(range(n), every=every, frequency=frequency):
    s += i
print(s)
