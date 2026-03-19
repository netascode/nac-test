#!/bin/bash

LOG="timing_output_debug_macos.log"

echo "================================================================================"
echo "📊 macOS D2D GRANULAR TIMING ANALYSIS"
echo "================================================================================"
echo ""

# Phase timing
echo "🕐 PHASE TIMING:"
echo "--------------------------------------------------------------------------------"
grep "Completed phase:" "$LOG" | sed -E 's/.*Completed phase: ([^(]+) \(([^)]+)\)/  \1: \2/'
echo ""

# Extract all D2D test timings
echo "📝 D2D TEST EXECUTION TIMING (verify_iosxe_control):"
echo "--------------------------------------------------------------------------------"

# Get first test (verify_iosxe_control without suffix)
echo "First test (includes SSH connection setup):"
grep "PASSED verify_iosxe_control in" "$LOG" | grep -v "_0" | while read line; do
    duration=$(echo "$line" | grep -oE '[0-9]+\.[0-9]+ seconds' | cut -d' ' -f1)
    echo "  $duration seconds"
done | head -4
echo ""

# Get average of first 4 tests
first_avg=$(grep "PASSED verify_iosxe_control in" "$LOG" | grep -v "_0" | head -4 | \
    grep -oE '[0-9]+\.[0-9]+ seconds' | cut -d' ' -f1 | \
    awk '{sum+=$1; count++} END {if(count>0) printf "%.1f", sum/count}')
echo "  Average first test: $first_avg seconds"
echo ""

# Get subsequent tests (verify_iosxe_control_01)
echo "Second test (connection reuse):"
grep "PASSED verify_iosxe_control_01 in" "$LOG" | while read line; do
    duration=$(echo "$line" | grep -oE '[0-9]+\.[0-9]+ seconds' | cut -d' ' -f1)
    echo "  $duration seconds"
done
echo ""

# Calculate average of subsequent tests
sub_avg=$(grep "PASSED verify_iosxe_control_01 in" "$LOG" | \
    grep -oE '[0-9]+\.[0-9]+ seconds' | cut -d' ' -f1 | \
    awk '{sum+=$1; count++} END {if(count>0) printf "%.1f", sum/count}')
echo "  Average subsequent test: $sub_avg seconds"
echo ""

# Calculate speedup
if [ -n "$first_avg" ] && [ -n "$sub_avg" ]; then
    speedup=$(echo "scale=2; $first_avg / $sub_avg" | bc)
    echo "  Speedup from connection reuse: ${speedup}x"
fi
echo ""

# API test timings for comparison
echo "📊 API TEST EXECUTION TIMING (verify_sdwan_sync):"
echo "--------------------------------------------------------------------------------"
grep "PASSED verify_sdwan_sync" "$LOG" | grep "in [0-9]" | \
    grep -oE '[0-9]+\.[0-9]+ seconds' | cut -d' ' -f1 | \
    awk '{
        sum+=$1; 
        count++; 
        if(min=="" || $1<min) min=$1; 
        if($1>max) max=$1;
    } 
    END {
        if(count>0) {
            avg=sum/count;
            printf "  Count: %d tests\n", count;
            printf "  Min: %.1fs, Max: %.1fs, Avg: %.1fs\n", min, max, avg;
            printf "  Total: %.1fs\n", sum;
        }
    }'
echo ""

# Broker statistics
echo "🔄 CONNECTION BROKER STATISTICS:"
echo "--------------------------------------------------------------------------------"
broker_line=$(grep "BROKER_STATISTICS" "$LOG" | tail -1)
if [ -n "$broker_line" ]; then
    conn_hits=$(echo "$broker_line" | grep -oE 'connection_hits=[0-9]+' | cut -d= -f2)
    conn_miss=$(echo "$broker_line" | grep -oE 'connection_misses=[0-9]+' | cut -d= -f2)
    cmd_hits=$(echo "$broker_line" | grep -oE 'command_hits=[0-9]+' | cut -d= -f2)
    cmd_miss=$(echo "$broker_line" | grep -oE 'command_misses=[0-9]+' | cut -d= -f2)
    
    conn_total=$((conn_hits + conn_miss))
    cmd_total=$((cmd_hits + cmd_miss))
    
    if [ $conn_total -gt 0 ]; then
        conn_pct=$(echo "scale=1; $conn_hits * 100 / $conn_total" | bc)
        echo "  Connection reuse: $conn_hits/$conn_total ($conn_pct% hit rate)"
    fi
    
    if [ $cmd_total -gt 0 ]; then
        cmd_pct=$(echo "scale=1; $cmd_hits * 100 / $cmd_total" | bc)
        echo "  Command cache: $cmd_hits/$cmd_total ($cmd_pct% hit rate)"
    fi
fi
echo ""

# Overall timing
echo "⏱️  OVERALL TIMING:"
echo "--------------------------------------------------------------------------------"
grep "Total testing:\|Total runtime:" "$LOG" | sed 's/^/  /'
echo ""

echo "================================================================================"
