
set -e
set -x

# Remove any old cove files.
find _build -name '*.coven' | xargs rm

# Run the basic test suite under cove.
coven -output _build/basic.coven -- iotest.py -fail-fast test/basic

# Run the meta test suite under cove, with the main iotest process in -coverage mode.
# This produces a .cove file for each child iotest process.
coven -output _build/meta.coven -- iotest.py -coverage -no-coverage-report -fail-fast test/meta

# A few of the meta tests invoke `iotest -coverage` as their test command;
# These will produce cove files where __main__ refers to something else and must be excluded;
# We only want the ones that cover iotest.
# Tests to exclude:
#   test-meta/coverage-gap.
iotest_cove_files=$(find _build -name '*.coven' | grep -v test-meta/coverage-gap)

# Display coverage for those .cove files.
coven -coalesce $iotest_cove_files
