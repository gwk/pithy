
set -e

# run the entire test suite under cove, with iotest as the main target.
# iotest itself runs in coverage mode, but suppresses report output.
cove -output _build/iotest.cove -- iotest.py -coverage -no-coverage-report

# then, display coverage output, including the .cove files produced by the meta-test runs.
cove -coalesce $(find _build -name '*.cove')
