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
echo "Running nac-test with Phase Timing"
echo "======================================"
echo ""
echo "Watch for timing logs showing:"
echo "  - Starting phase: [phase_name]"
echo "  - Completed phase: [phase_name] (duration)"
echo ""

# Run with INFO verbosity to see timing logs
nac-test -d data -t templates_consolidated/tests --testbed testbed.yaml \
    -o $RESULT_DIR --pyats --verbosity INFO 2>&1 | tee timing_output.log

echo ""
echo "✅ Execution complete!"
echo ""
echo "Timing log saved to: timing_output.log"
echo "You can analyze phase durations with:"
echo "  grep 'Completed phase' timing_output.log"
echo ""
