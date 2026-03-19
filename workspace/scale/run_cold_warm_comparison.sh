#!/bin/bash
# Run nac-test cold start vs warm start comparison
# Captures detailed timing for issue #432 analysis

set -e

PORT=5678

if [[ "$OSTYPE" == "darwin"* ]]; then
    BASE_DIR=$HOME/Documents/DD/nac-test
    # Activate virtualenv
    test "$VIRTUAL_ENV" || source $BASE_DIR/.venv/bin/activate
else
    BASE_DIR=/DD/nac-test
    test "$VIRTUAL_ENV" || source /tmp/venv/bin/activate
fi

MOCK_DIR=$BASE_DIR/tests/e2e/mocks
export MOCK_DIR     # referenced in testbed.yaml
RESULT_DIR=./results

export PYATS_DEBUG=1

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
python3 $MOCK_DIR/start_server.py --port $PORT || { echo "Failed to start mock API server on port $PORT"; exit 1; }
trap 'python3 $MOCK_DIR/stop_server.py' EXIT INT ERR

cd $BASE_DIR/workspace/scale

echo "================================================================================"
echo "🔬 COLD START vs WARM START COMPARISON (Issue #432)"
echo "================================================================================"
echo ""
echo "This script runs nac-test twice to measure:"
echo "  1. COLD START: First execution (Python imports, dependency loading)"
echo "  2. WARM START: Second execution (cached imports, warmed up)"
echo ""
echo "Timing captured at multiple levels:"
echo "  - Overall execution time (bash time command)"
echo "  - Phase timing (nac-test instrumentation)"
echo "  - Process spawning overhead (PyATS subprocess creation)"
echo ""

# ==============================================================================
# RUN 1: COLD START
# ==============================================================================
echo "================================================================================"
echo "🥶 RUN 1: COLD START"
echo "================================================================================"
echo ""
echo "Starting cold start test at: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

COLD_START=$(date +%s)
/usr/bin/time -p nac-test -d data -t templates/tests --testbed testbed.yaml \
    -o $RESULT_DIR --pyats --verbosity DEBUG 2>&1 | tee timing_output_cold_start.log
COLD_END=$(date +%s)
COLD_DURATION=$((COLD_END - COLD_START))

echo ""
echo "✅ Cold start complete!"
echo "Duration: ${COLD_DURATION}s"
echo "Log: timing_output_cold_start.log"
echo ""

# Wait a bit to let system settle
sleep 2

# ==============================================================================
# RUN 2: WARM START
# ==============================================================================
echo "================================================================================"
echo "🔥 RUN 2: WARM START"
echo "================================================================================"
echo ""
echo "Starting warm start test at: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

WARM_START=$(date +%s)
/usr/bin/time -p nac-test -d data -t templates/tests --testbed testbed.yaml \
    -o $RESULT_DIR --pyats --verbosity DEBUG 2>&1 | tee timing_output_warm_start.log
WARM_END=$(date +%s)
WARM_DURATION=$((WARM_END - WARM_START))

echo ""
echo "✅ Warm start complete!"
echo "Duration: ${WARM_DURATION}s"
echo "Log: timing_output_warm_start.log"
echo ""

# ==============================================================================
# ANALYSIS
# ==============================================================================
echo "================================================================================"
echo "📊 COLD START vs WARM START ANALYSIS"
echo "================================================================================"
echo ""

DIFF=$((COLD_DURATION - WARM_DURATION))
if [ $WARM_DURATION -gt 0 ]; then
    SPEEDUP=$(echo "scale=2; $COLD_DURATION / $WARM_DURATION" | bc)
else
    SPEEDUP="N/A"
fi

echo "Overall Timing:"
echo "  Cold start: ${COLD_DURATION}s"
echo "  Warm start: ${WARM_DURATION}s"
echo "  Difference: ${DIFF}s"
echo "  Speedup: ${SPEEDUP}x"
echo ""

echo "Phase Breakdown (Cold Start):"
grep "Completed phase:" timing_output_cold_start.log | sed -E 's/.*Completed phase: ([^(]+) \(([^)]+)\)/  \1: \2/' | head -10
echo ""

echo "Phase Breakdown (Warm Start):"
grep "Completed phase:" timing_output_warm_start.log | sed -E 's/.*Completed phase: ([^(]+) \(([^)]+)\)/  \1: \2/' | head -10
echo ""

echo "First Test Timing (Cold Start):"
grep "PASSED verify_iosxe_control in" timing_output_cold_start.log | grep -v "_0" | head -1 | \
    sed -E 's/.*(PASSED .* in ([0-9]+\.[0-9]+) seconds).*/  \2s/'
echo ""

echo "First Test Timing (Warm Start):"
grep "PASSED verify_iosxe_control in" timing_output_warm_start.log | grep -v "_0" | head -1 | \
    sed -E 's/.*(PASSED .* in ([0-9]+\.[0-9]+) seconds).*/  \2s/'
echo ""

echo "================================================================================"
echo "💾 Files Generated:"
echo "================================================================================"
echo "  timing_output_cold_start.log   - Full cold start execution log"
echo "  timing_output_warm_start.log   - Full warm start execution log"
echo ""
echo "Analysis commands:"
echo "  ./analyze_macos.sh timing_output_cold_start.log"
echo "  ./analyze_macos.sh timing_output_warm_start.log"
echo ""
echo "✅ Cold/warm start comparison complete!"
echo ""
