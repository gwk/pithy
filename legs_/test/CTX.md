# Legs Tests

`just check` does not run these tests. `just test-full` runs all of them.
The tests of the supplied languages are in `legs_/langs`; run those with `just test-legs-langs`.

* `0/` holds grammars that compile. Most tests run `legs-test` on input strings and compare the tokens of the generated lexers.
  Run these first: `iotest legs_/test/0`.
* `2/` holds grammars that contain errors. Each `.err` file is the expected diagnostic output.
* `props/` runs `legs-test -props` on grammars from this directory and `wu_/wu`.
* `ut/` holds unit tests that are too slow for the routine checks. Run them with `just utest-slow` or `python3 -m utest legs_/test/ut`.

In `0/` and `2/`, `_default.iot` gives the command for each grammar that has no `.iot` file of its own.
