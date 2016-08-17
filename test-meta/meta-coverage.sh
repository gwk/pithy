
set -e
set -x
# run the basic test suite under cove.
cove -output _build/basic.cove -- iotest.py -fail-fast test/basic

# run the meta test suite under cove, with the main iotest process in -coverage mode.
# this produces a .cove file for each child iotest process.
cove -output _build/meta.cove -- iotest.py -coverage -no-coverage-report -fail-fast test/meta

# a few of the meta tests invoke `iotest -coverage` as their test command;
# these will produce cove files where __main__ refers to something else and must be excluded;
# we only want the ones that cover iotest.
iotest_cove_files=$(find _build -name '*.cove' | grep -v coverage-gap)

set +x
# display coverage for those .cove files.
cove -coalesce $iotest_cove_files
