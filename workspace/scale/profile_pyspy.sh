#!/bin/bash
# Profile nac-test execution with py-spy (sampling profiler)
# Captures CPU hotspots with subprocess support

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/profiling_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$OUTPUT_DIR"

echo "======================================"
echo "py-spy Profiling (Sampling)"
echo "======================================"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Profile with subprocess support
echo "Running py-spy with subprocess tracking..."
py-spy record \
    --subprocesses \
    --rate 100 \
    --format speedscope \
    --output "$OUTPUT_DIR/profile_${TIMESTAMP}.json" \
    -- bash "$SCRIPT_DIR/start_test.sh"

# Also generate SVG flame graph
echo ""
echo "Generating flame graph..."
py-spy record \
    --subprocesses \
    --rate 100 \
    --output "$OUTPUT_DIR/flamegraph_${TIMESTAMP}.svg" \
    -- bash "$SCRIPT_DIR/start_test.sh"

echo ""
echo "✅ Profiling complete!"
echo ""
echo "View results:"
echo "  - Speedscope (interactive): https://www.speedscope.app/"
echo "    Upload: $OUTPUT_DIR/profile_${TIMESTAMP}.json"
echo "  - Flame graph (SVG): open $OUTPUT_DIR/flamegraph_${TIMESTAMP}.svg"
echo ""
