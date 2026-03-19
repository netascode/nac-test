#!/bin/bash
# Quick timing extraction from debug logs

LOG_FILE="$1"

if [ -z "$LOG_FILE" ]; then
    echo "Usage: $0 <log_file>"
    exit 1
fi

echo "================================================================================"
echo "📊 D2D GRANULAR TIMING ANALYSIS"
echo "================================================================================"
echo ""

# Phase timing
echo "🕐 PHASE TIMING:"
echo "--------------------------------------------------------------------------------"
grep "Completed phase:" "$LOG_FILE" | sed 's/.*Completed phase: /  /' | sed 's/ (/  →  (/'
echo ""

# Test execution summary
echo "📝 TEST EXECUTION TIMING:"
echo "--------------------------------------------------------------------------------"
grep "PASSED\|FAILED" "$LOG_FILE" | grep "in [0-9]" | \
    awk '{
        test=$6; 
        duration=$8; 
        count[test]++; 
        sum[test]+=duration; 
        if (min[test]=="" || duration<min[test]) min[test]=duration;
        if (duration>max[test]) max[test]=duration;
    } 
    END {
        printf "  %-40s %6s %8s %8s %8s %10s\n", "Test Name", "Count", "Min", "Max", "Avg", "Total";
        print "  " "--------------------------------------------------------------------------------";
        for (test in count) {
            printf "  %-40s %6d %8.1fs %7.1fs %7.1fs %9.1fs\n", 
                test, count[test], min[test], max[test], sum[test]/count[test], sum[test];
        }
    }'
echo ""

# First vs subsequent tests
echo "⚡ FIRST TEST vs SUBSEQUENT TESTS (by device):"
echo "--------------------------------------------------------------------------------"

# Extract first occurrence and average of rest for each base test name
grep "PASSED" "$LOG_FILE" | grep "verify_iosxe_control " | awk '
{
    if ($8 ~ /^[0-9.]+$/) {
        duration = $8;
        count++;
        if (count == 1 || count == 2 || count == 3 || count == 4) {
            first_total += duration;
            first_count++;
        } else {
            sub_total += duration;
            sub_count++;
        }
    }
}
END {
    if (first_count > 0) {
        first_avg = first_total / first_count;
        printf "  First test (with SSH setup):     %6.1fs  (avg of %d devices)\n", first_avg, first_count;
    }
    if (sub_count > 0) {
        sub_avg = sub_total / sub_count;
        printf "  Subsequent tests (connection reuse): %6.1fs  (avg of %d tests)\n", sub_avg, sub_count;
        if (first_count > 0) {
            speedup = first_avg / sub_avg;
            printf "  Speedup from connection reuse:   %6.2fx\n", speedup;
        }
    }
}'
echo ""

# Broker statistics
echo "🔄 CONNECTION BROKER STATISTICS:"
echo "--------------------------------------------------------------------------------"
grep "BROKER_STATISTICS" "$LOG_FILE" | tail -1 | \
    sed 's/.*connection_hits=/  Connection hits:     /' | \
    sed 's/, connection_misses=/\n  Connection misses:   /' | \
    sed 's/, command_hits=/\n  Command hits:        /' | \
    sed 's/, command_misses=/\n  Command misses:      /'
echo ""

# Overall timing
echo "⏱️  OVERALL TIMING:"
echo "--------------------------------------------------------------------------------"
grep "Total testing:\|Total runtime:" "$LOG_FILE" | sed 's/^/  /'
echo ""

echo "================================================================================"
