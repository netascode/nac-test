#!/bin/bash
# Run nac-test with enhanced timing output (instrumented phases)
# This uses the phase timing instrumentation added to the code

set -e

PORT=5678
MOCK_DIR=$HOME/Documents/DD/nac-test/tests/e2e/mocks
RESULT_DIR=./results

# Activate virtualenv
test "$VIRTUAL_ENV" || source $HOME/Documents/DD/nac-test/.venv/bin/activate

# Clear environment variables
set -- $(env | egrep '^[A-Z]+_(URL|USERNAME|PASSWORD)=' | sed 's/=.*//')
for var in $* ; do 
    unset $var
done

# Set up environment
export SDWAN_URL=http://127.0.0.1:$PORT
export SDWAN_USERNAME=mock_user
export SDWAN_PASSWORD=mock_pass
export IOSXE_USERNAME=mock_user
export IOSXE_PASSWORD=mock_pass
export PYATS_MAX_WORKERS=5

# Start mock server
python $MOCK_DIR/start_server.py --port $PORT || { echo "Failed to start mock API server on port $PORT"; exit 1; }
trap 'python $MOCK_DIR/stop_server.py' EXIT INT ERR

cd /Users/oboehmer/Documents/DD/nac-test/workspace/scale

echo "======================================"
echo "Running nac-test PoC with Dynamic Loop Marking"
echo "======================================"
echo ""
echo "This PoC demonstrates:"
echo "  - Consolidated test pattern using aetest.loop.mark()"
echo "  - Multiple verification types in SINGLE subprocess"
echo "  - Reduced subprocess overhead (11 → 1)"
echo ""

# Run with INFO verbosity to see timing logs
nac-test -d data -t templates-poc/tests --testbed testbed.yaml \
    -o $RESULT_DIR --pyats --verbosity INFO 2>&1 | tee timing_output_poc.log

echo ""
echo "✅ PoC Execution complete!"
echo ""
echo "Timing log saved to: timing_output_poc.log"
echo "You can analyze phase durations with:"
echo "  grep 'Completed phase' timing_output_poc.log"
echo ""
