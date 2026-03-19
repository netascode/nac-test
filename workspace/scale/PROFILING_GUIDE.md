# nac-test Performance Profiling Guide

## Overview

This guide provides three complementary approaches to profile and analyze performance of the nac-test scale test environment:

1. **Phase Timing** (lightweight, code instrumentation)
2. **py-spy** (external sampling profiler, CPU hotspots)
3. **VizTracer** (execution tracer, async/multiprocess timeline)

---

## Current Baseline

- **Environment**: 4 mocked devices (sd-dc-c8kv-01 through 04), ~15 test files
- **Current Duration**: 2-3 minutes
- **Target**: Under 30 seconds
- **Network**: Local mocking (no network latency)

---

## Profiling Approaches

### 1. Phase Timing (Instrumented Logs)

**What it measures**: Duration of key orchestration phases

**How to run**:
```bash
cd /Users/oboehmer/Documents/DD/nac-test/workspace/scale
./run_with_timing.sh
```

**Output**: `timing_output.log` with phase durations

**What you'll see**:
```
Starting phase: Worker Calculation
Completed phase: Worker Calculation (45.2 ms)

Starting phase: Test Discovery
Completed phase: Test Discovery (1.2 s)

Starting phase: Device Execution [sd-dc-c8kv-01]
Completed phase: Device Execution [sd-dc-c8kv-01] (18.3 s)
```

**Analyze with**:
```bash
# View all phase durations
grep "Completed phase" timing_output.log

# Find longest phases
grep "Completed phase" timing_output.log | sort -t '(' -k2 -rn | head -10
```

**Pros**:
- No external dependencies
- Production-safe (minimal overhead)
- Per-device visibility

**Cons**:
- Doesn't show *why* phases are slow
- No call stack visibility

---

### 2. py-spy (Sampling Profiler)

**What it measures**: CPU time per function (hotspots)

**How to run**:
```bash
cd /Users/oboehmer/Documents/DD/nac-test/workspace/scale
./profile_pyspy.sh
```

**Output**: 
- `profiling_results/profile_YYYYMMDD_HHMMSS.json` (speedscope format)
- `profiling_results/flamegraph_YYYYMMDD_HHMMSS.svg` (flame graph)

**How to view**:
- **Speedscope** (interactive): Upload JSON to https://www.speedscope.app/
- **Flame graph**: `open profiling_results/flamegraph_*.svg` in browser

**What to look for**:
- **Wide bars**: Functions consuming most CPU time
- **Subprocess overhead**: Time spent in `subprocess.py`, `_posixsubprocess`, or Python interpreter startup
- **I/O waits**: If functions show low CPU usage, bottleneck is I/O not CPU

**Example findings**:
- If `subprocess.run` or `os.fork` dominates → subprocess spawning overhead
- If `yaml.load` or `jinja2.render` dominates → data processing bottleneck
- If `asyncio.sleep` or I/O functions dominate → waiting on I/O

**Pros**:
- Zero code changes
- Multi-process support
- Can attach to production processes

**Cons**:
- Separate files per subprocess (manual correlation)
- CPU-only (doesn't show I/O wait time)

---

### 3. VizTracer (Execution Tracer)

**What it measures**: Complete execution timeline with async/multiprocess coordination

**How to run**:
```bash
cd /Users/oboehmer/Documents/DD/nac-test/workspace/scale
./profile_viztracer.sh
```

**Output**: `profiling_results/trace_YYYYMMDD_HHMMSS.json`

**How to view**:
```bash
vizviewer profiling_results/trace_*.json
```

Opens interactive timeline in browser.

**What to look for**:
- **Parallel gaps**: Are subprocesses running simultaneously or sequentially?
- **Idle time**: Gaps indicate waiting (semaphore, broker, I/O)
- **Async switches**: Task coordination overhead
- **Green bars**: Active CPU time
- **Gaps**: I/O wait or idle

**Example findings**:
- If devices run sequentially → batching or semaphore issue
- If long gaps between device starts → broker or job generation slowness
- If short execution with long startup → Python interpreter overhead

**Pros**:
- Best asyncio/subprocess visualization
- Automatic multi-process aggregation
- Clear distinction between CPU vs I/O

**Cons**:
- ~5-10% performance overhead
- Large output files for long runs

---

## Recommended Workflow

### Step 1: Quick Baseline (5 min)
```bash
# Get phase timing baseline
./run_with_timing.sh
grep "Completed phase" timing_output.log
```

**Goal**: Identify which phase is slowest (e.g., "Device Execution: 90s")

---

### Step 2: CPU Analysis (10 min)
```bash
# Profile CPU hotspots
./profile_pyspy.sh

# Open flame graph
open profiling_results/flamegraph_*.svg
```

**Goal**: Understand *why* the slow phase is slow
- High CPU in subprocess functions → subprocess overhead
- Low CPU overall → I/O bound (waiting)

---

### Step 3: Timeline Analysis (15 min - if needed)
```bash
# Deep dive into concurrency
./profile_viztracer.sh

# View timeline
vizviewer profiling_results/trace_*.json
```

**Goal**: Verify parallelization and identify coordination bottlenecks
- Are devices running in parallel?
- Is broker causing serialization?
- Where are the idle gaps?

---

## Common Bottlenecks & Solutions

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| **Phase timing shows "Device Execution" taking 90%** | Per-device subprocess overhead | Reduce worker count, batch smaller |
| **Flame graph shows `subprocess.run` dominating** | Python interpreter startup | Use persistent workers or lighter subprocess model |
| **Timeline shows sequential device execution** | Semaphore/batching too restrictive | Increase `PYATS_MAX_WORKERS` or `--max-parallel-devices` |
| **Phase timing shows "Job Generation" taking 20%+ | File I/O or template rendering | Cache job files or optimize generation |
| **Timeline shows long gaps between starts** | Broker or testbed generation slow | Profile broker separately or optimize testbed gen |
| **Low CPU in flame graph but long duration** | I/O bound (broker, mock server, disk) | Check mock server response time, broker stats |

---

## Environment Variables for Tuning

| Variable | Default | Effect |
|----------|---------|--------|
| `PYATS_MAX_WORKERS` | Auto-calculated | Override worker capacity (lower = fewer parallel devices) |
| `NAC_TEST_MAX_PARALLEL_DEVICES` | None | Cap device parallelism (CLI: `--max-parallel-devices`) |
| `PYATS_OUTPUT_BUFFER_LIMIT` | 65536 | Subprocess output buffer size (larger = fewer overruns) |
| `NAC_TEST_PIPE_DRAIN_DELAY` | 0.1s | macOS pipe drain delay (increase if losing output) |
| `NAC_TEST_PIPE_DRAIN_TIMEOUT` | 2.0s | Drain timeout (increase for slow systems) |

**Example: Reduce parallelism**
```bash
export PYATS_MAX_WORKERS=2
./run_with_timing.sh
```

---

## Next Steps

1. **Run baseline timing** to identify slow phase
2. **Profile with py-spy** to find CPU hotspots
3. **If unclear, use VizTracer** for timeline analysis
4. **Iterate**:
   - Adjust worker counts
   - Optimize identified bottlenecks
   - Re-profile to verify improvement

---

## Output Directory Structure

```
workspace/scale/
├── start_test.sh              # Original test script
├── run_with_timing.sh         # Phase timing (instrumented)
├── profile_pyspy.sh           # CPU profiling
├── profile_viztracer.sh       # Timeline tracing
├── timing_output.log          # Phase timing results
└── profiling_results/
    ├── profile_*.json         # py-spy speedscope format
    ├── flamegraph_*.svg       # py-spy flame graphs
    └── trace_*.json           # VizTracer timeline
```

---

## Questions?

- **Phase timing shows 0.1s for everything**: Increase verbosity to DEBUG or check logger configuration
- **py-spy fails with permission error**: Run with sudo or adjust ptrace permissions
- **VizTracer output too large**: Use `--min-duration 0.001` to filter short functions
- **Subprocess not captured by py-spy**: Ensure `--subprocesses` flag is used

---

## Tools Reference

- **py-spy docs**: https://github.com/benfred/py-spy
- **VizTracer docs**: https://viztracer.readthedocs.io/
- **Speedscope viewer**: https://www.speedscope.app/

