#!/bin/bash
# Profile nac-test execution with VizTracer (execution tracer)
# Captures async/multiprocess timeline with automatic aggregation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/profiling_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$OUTPUT_DIR"

echo "======================================"
echo "VizTracer Profiling (Execution Trace)"
echo "======================================"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Change to scale directory and set up environment
cd "$SCRIPT_DIR"

# Profile with multiprocess and async support
echo "Running VizTracer with multi-process + async tracking..."
echo "NOTE: This may take longer than normal execution due to tracing overhead"
echo ""

# Set up the same environment as start_test.sh
PORT=5678
MOCK_DIR=$HOME/Documents/DD/nac-test/tests/e2e/mocks
RESULT_DIR=./results

export SDWAN_URL=http://127.0.0.1:$PORT
export SDWAN_USERNAME=mock_user
export SDWAN_PASSWORD=mock_pass
export IOSXE_USERNAME=mock_user
export IOSXE_PASSWORD=mock_pass
export PYATS_MAX_WORKERS=5

# Start mock server
python $MOCK_DIR/start_server.py --port $PORT || { echo "Failed to start mock server"; exit 1; }
trap 'python $MOCK_DIR/stop_server.py' EXIT INT ERR

# Run VizTracer
viztracer \
    --log_multiprocess \
    --log_async \
    --max_stack_depth 10 \
    --output_file "$OUTPUT_DIR/trace_${TIMESTAMP}.json" \
    -- nac-test -d data -t templates/tests --testbed testbed.yaml \
       -o $RESULT_DIR --pyats --verbosity INFO

echo ""
echo "✅ Profiling complete!"
echo ""
echo "View results:"
echo "  vizviewer $OUTPUT_DIR/trace_${TIMESTAMP}.json"
echo ""
echo "The interactive timeline will open in your browser showing:"
echo "  - Parallel subprocess execution"
echo "  - Asyncio task switches"
echo "  - I/O waits vs CPU time"
echo ""
