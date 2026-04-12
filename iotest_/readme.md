
# IOTest

iotest is a small tool for testing command line programs. By default it writes the stdout and stderr of the program under test to files, and then compares them to expected results using `git diff`. Here are some reasons I like it:
- Specify complicated, multiline text expectations without fiddling with escape characters in test code.
- Clearly differentiate between stdout and stderr.
- Specify success/failure exit code expectations, or by default expect zero and no stderr output, or some stderr expectation and a nonzero exit code.
- Tests are run and test output is placed in a dedicated subdirectory of `_build` for easy inspection when tests fail.
- Test cases can inherit from prototype cases.

IOTest is available via pip for easy distribution. Alternatively, the script can be freely copied into a project; there is a single python dependency (pithy utility library), also available through pip.


# License

iotest dedicated to the public domain. It is written and maintained by George King.


# Usage

To run all tests in the `test` directory:
$ iotest test/

iotest will look for test cases, which are indicated by the presence of a `.iot`, `.out`, or `.err` file. The filename stem (the part before dot/extension) indicates the name of the test case. This is then used to find a test executable with the matching stem. For example, if we have a test case file `thing.iot` and corresponding executable file `thing.py`, iotest will run `thing.py` and compare its output to the expectations specified in `thing.iot`. If there is more than one test case file, e.g. `thing.iot` and `thing.err`, then they will be combined together as long as they do not conflict (in other words, `thing.iot` cannot also specify a stderr expectation).


# Issues

Please file issues to the github repository: github.com/gwk/pithy.
