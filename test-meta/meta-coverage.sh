
set -e
set -x
# Run the basic test suite under cove.
cove -output _build/basic.cove -- iotest.py -fail-fast test/basic

# Run the meta test suite under cove, with the main iotest process in -coverage mode.
# This produces a .cove file for each child iotest process.
cove -output _build/meta.cove -- iotest.py -coverage -no-coverage-report -fail-fast test/meta

# A few of the meta tests invoke `iotest -coverage` as their test command;
# These will produce cove files where __main__ refers to something else and must be excluded;
# We only want the ones that cover iotest.
# Tests to exclude:
#   test-meta/coverage-gap.
iotest_cove_files=$(find _build -name '*.cove' | grep -v test-meta/coverage-gap)

# Display coverage for those .cove files.
cove -coalesce $iotest_cove_files
