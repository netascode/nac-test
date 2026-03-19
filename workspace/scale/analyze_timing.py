#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
Granular D2D Timing Analysis Script

Parses debug logs to extract component-level timing information:
1. PyATS process spawning overhead
2. SSH connection establishment
3. Test execution breakdown
4. Connection broker overhead
5. Per-test variance analysis
"""

import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple
import json


class TimingAnalyzer:
    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        self.events = []
        self.tests = defaultdict(dict)
        self.connections = defaultdict(dict)
        self.broker_events = []

    def parse_timestamp(self, line: str) -> datetime | None:
        """Extract timestamp from log line."""
        # Format: 2026-02-08 08:47:39.497
        match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})", line)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S.%f")
        return None

    def parse_log(self):
        """Parse log file and extract timing events."""
        print(f"📖 Parsing log file: {self.log_file}")

        with open(self.log_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                ts = self.parse_timestamp(line)

                # Test execution events
                if "EXECUTING" in line:
                    match = re.search(r"EXECUTING (\w+)", line)
                    if match:
                        test_name = match.group(1)
                        self.events.append(
                            {
                                "type": "test_start",
                                "test": test_name,
                                "timestamp": ts,
                                "line": line_num,
                            }
                        )

                elif "PASSED" in line or "FAILED" in line:
                    match = re.search(
                        r"(PASSED|FAILED) (\w+) in ([\d.]+) seconds", line
                    )
                    if match:
                        status, test_name, duration = match.groups()
                        self.events.append(
                            {
                                "type": "test_end",
                                "test": test_name,
                                "status": status,
                                "duration": float(duration),
                                "timestamp": ts,
                                "line": line_num,
                            }
                        )

                # Connection events
                elif "Creating NEW connection" in line:
                    match = re.search(r"Creating NEW connection for ([\w-]+)", line)
                    if match:
                        device = match.group(1)
                        self.connections[device]["connection_start"] = ts

                elif "Successfully connected to device" in line:
                    match = re.search(
                        r"Successfully connected to device: ([\w-]+)", line
                    )
                    if match:
                        device = match.group(1)
                        self.connections[device]["connection_end"] = ts

                # Broker events
                elif "BROKER_STATISTICS" in line:
                    match = re.search(
                        r"connection_hits=(\d+), connection_misses=(\d+), command_hits=(\d+), command_misses=(\d+)",
                        line,
                    )
                    if match:
                        self.broker_events.append(
                            {
                                "connection_hits": int(match.group(1)),
                                "connection_misses": int(match.group(2)),
                                "command_hits": int(match.group(3)),
                                "command_misses": int(match.group(4)),
                                "timestamp": ts,
                            }
                        )

                # Phase timing events
                elif "Completed phase:" in line:
                    match = re.search(
                        r"Completed phase: ([\w\s]+) \(([\d.]+\s*\w+)\)", line
                    )
                    if match:
                        phase_name, duration_str = match.groups()
                        self.events.append(
                            {
                                "type": "phase_complete",
                                "phase": phase_name.strip(),
                                "duration": duration_str,
                                "timestamp": ts,
                                "line": line_num,
                            }
                        )

        print(
            f"✅ Parsed {len(self.events)} events, {len(self.connections)} connections"
        )

    def analyze_tests(self) -> Dict:
        """Analyze per-test timing."""
        print("\n📊 Analyzing test execution timing...")

        test_timings = defaultdict(list)

        for event in self.events:
            if event["type"] == "test_end":
                test_name = event["test"]
                duration = event["duration"]
                test_timings[test_name].append(duration)

        analysis = {}
        for test_name, durations in sorted(test_timings.items()):
            if durations:
                analysis[test_name] = {
                    "count": len(durations),
                    "min": min(durations),
                    "max": max(durations),
                    "avg": sum(durations) / len(durations),
                    "total": sum(durations),
                }

        return analysis

    def analyze_connections(self) -> Dict:
        """Analyze SSH connection timing."""
        print("\n📊 Analyzing SSH connection timing...")

        conn_analysis = {}
        for device, events in self.connections.items():
            if "connection_start" in events and "connection_end" in events:
                duration = (
                    events["connection_end"] - events["connection_start"]
                ).total_seconds()
                conn_analysis[device] = {
                    "duration": duration,
                    "start": events["connection_start"].strftime("%H:%M:%S.%f")[:-3],
                    "end": events["connection_end"].strftime("%H:%M:%S.%f")[:-3],
                }

        return conn_analysis

    def analyze_phases(self) -> Dict:
        """Analyze phase timing."""
        print("\n📊 Analyzing phase timing...")

        phases = {}
        for event in self.events:
            if event["type"] == "phase_complete":
                phases[event["phase"]] = event["duration"]

        return phases

    def analyze_first_vs_subsequent(self) -> Dict:
        """Compare first test vs subsequent tests."""
        print("\n📊 Analyzing first vs subsequent test performance...")

        # Group by base test name (ignore _01, _02 suffixes)
        base_tests = defaultdict(list)

        for event in self.events:
            if event["type"] == "test_end":
                test_name = event["test"]
                # Remove numeric suffix
                base_name = re.sub(r"_\d+$", "", test_name)
                base_tests[base_name].append(
                    {
                        "name": test_name,
                        "duration": event["duration"],
                        "timestamp": event["timestamp"],
                    }
                )

        analysis = {}
        for base_name, tests in base_tests.items():
            if len(tests) > 1:
                # Sort by timestamp
                tests_sorted = sorted(tests, key=lambda x: x["timestamp"])
                first_test = tests_sorted[0]
                subsequent_tests = tests_sorted[1:]

                analysis[base_name] = {
                    "first": {
                        "name": first_test["name"],
                        "duration": first_test["duration"],
                    },
                    "subsequent": {
                        "count": len(subsequent_tests),
                        "durations": [t["duration"] for t in subsequent_tests],
                        "avg": sum(t["duration"] for t in subsequent_tests)
                        / len(subsequent_tests),
                        "min": min(t["duration"] for t in subsequent_tests),
                        "max": max(t["duration"] for t in subsequent_tests),
                    },
                    "speedup": first_test["duration"]
                    / (
                        sum(t["duration"] for t in subsequent_tests)
                        / len(subsequent_tests)
                    )
                    if subsequent_tests
                    else 0,
                }

        return analysis

    def print_summary(self):
        """Print comprehensive timing summary."""
        print("\n" + "=" * 80)
        print("📊 D2D GRANULAR TIMING ANALYSIS")
        print("=" * 80)

        # Phase timing
        phases = self.analyze_phases()
        if phases:
            print("\n🕐 PHASE TIMING:")
            print("-" * 80)
            for phase, duration in phases.items():
                print(f"  {phase:40s} {duration:>15s}")

        # Connection timing
        connections = self.analyze_connections()
        if connections:
            print("\n🔌 SSH CONNECTION ESTABLISHMENT:")
            print("-" * 80)
            for device, info in sorted(connections.items()):
                print(
                    f"  {device:30s} {info['duration']:>8.1f}s  ({info['start']} → {info['end']})"
                )

            avg_conn_time = sum(c["duration"] for c in connections.values()) / len(
                connections
            )
            print(f"\n  Average connection time: {avg_conn_time:.1f}s")

        # Test timing summary
        tests = self.analyze_tests()
        if tests:
            print("\n📝 TEST EXECUTION TIMING:")
            print("-" * 80)
            print(
                f"  {'Test Name':40s} {'Count':>6s} {'Min':>8s} {'Max':>8s} {'Avg':>8s} {'Total':>10s}"
            )
            print("-" * 80)

            total_time = 0
            total_count = 0

            for test_name, stats in sorted(tests.items()):
                print(
                    f"  {test_name:40s} "
                    f"{stats['count']:>6d} "
                    f"{stats['min']:>8.1f}s "
                    f"{stats['max']:>8.1f}s "
                    f"{stats['avg']:>8.1f}s "
                    f"{stats['total']:>10.1f}s"
                )
                total_time += stats["total"]
                total_count += stats["count"]

            print("-" * 80)
            print(
                f"  {'TOTAL':40s} {total_count:>6d} {'':<8s} {'':<8s} {'':<8s} {total_time:>10.1f}s"
            )

        # First vs subsequent analysis
        first_vs_sub = self.analyze_first_vs_subsequent()
        if first_vs_sub:
            print("\n⚡ FIRST TEST vs SUBSEQUENT TESTS:")
            print("-" * 80)
            print(
                f"  {'Test Type':30s} {'First':>10s} {'Avg Sub':>10s} {'Speedup':>10s}"
            )
            print("-" * 80)

            for base_name, analysis in sorted(first_vs_sub.items()):
                first_dur = analysis["first"]["duration"]
                avg_sub = analysis["subsequent"]["avg"]
                speedup = analysis["speedup"]

                print(
                    f"  {base_name:30s} "
                    f"{first_dur:>10.1f}s "
                    f"{avg_sub:>10.1f}s "
                    f"{speedup:>10.2f}×"
                )

        # Broker statistics
        if self.broker_events:
            print("\n🔄 CONNECTION BROKER STATISTICS:")
            print("-" * 80)
            stats = self.broker_events[-1]  # Latest stats
            total_conn = stats["connection_hits"] + stats["connection_misses"]
            total_cmd = stats["command_hits"] + stats["command_misses"]

            conn_hit_rate = (
                (stats["connection_hits"] / total_conn * 100) if total_conn > 0 else 0
            )
            cmd_hit_rate = (
                (stats["command_hits"] / total_cmd * 100) if total_cmd > 0 else 0
            )

            print(
                f"  Connection reuse: {stats['connection_hits']}/{total_conn} ({conn_hit_rate:.1f}% hit rate)"
            )
            print(
                f"  Command cache:    {stats['command_hits']}/{total_cmd} ({cmd_hit_rate:.1f}% hit rate)"
            )

        print("\n" + "=" * 80)

    def export_json(self, output_file: str):
        """Export analysis results to JSON."""
        results = {
            "phases": self.analyze_phases(),
            "connections": self.analyze_connections(),
            "tests": self.analyze_tests(),
            "first_vs_subsequent": self.analyze_first_vs_subsequent(),
            "broker": self.broker_events[-1] if self.broker_events else {},
        }

        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n📄 Exported analysis to: {output_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_timing.py <log_file>")
        print("\nExample:")
        print("  python analyze_timing.py timing_output.log")
        sys.exit(1)

    log_file = sys.argv[1]

    if not Path(log_file).exists():
        print(f"❌ Error: Log file not found: {log_file}")
        sys.exit(1)

    analyzer = TimingAnalyzer(log_file)
    analyzer.parse_log()
    analyzer.print_summary()

    # Export to JSON
    json_output = log_file.replace(".log", "_analysis.json")
    analyzer.export_json(json_output)


if __name__ == "__main__":
    main()
