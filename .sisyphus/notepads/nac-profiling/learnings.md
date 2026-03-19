## Python Profiling Research Findings (2026-02-07)

### Top Recommendations for Multi-Process + Asyncio + Subprocess Applications

1. **py-spy** - Best for production, zero overhead, simple usage
   - Use `--subprocesses` flag for multi-process profiling
   - Creates separate flame graphs per process
   - Can attach to running processes

2. **VizTracer** - Best for async visualization and automatic aggregation
   - `--log_multiprocess` automatically combines all process traces
   - `--log_async` shows task switches and waiting states
   - Interactive timeline view

3. **Tachyon (Python 3.15+)** - Future-proof built-in solution
   - Zero overhead sampling profiler built into Python 3.15+
   - `--subprocesses` and `--async-aware` flags
   - Multiple modes: wall/cpu/gil/exception
   - Currently in alpha (stable October 2026)

### Key Insights

- **I/O vs CPU Detection:** Compare wall-clock mode vs CPU mode profiles
  - High in both = CPU-bound (optimize algorithms)
  - High in wall, low in CPU = I/O-bound (use async/caching)

- **Multi-process Profiling:**
  - py-spy and Tachyon create separate files per subprocess
  - VizTracer automatically aggregates into single file
  - OpenTelemetry offers distributed tracing but high complexity

- **Production Safety:**
  - Sampling profilers (py-spy, Tachyon) have ~0% overhead
  - Tracing profilers (VizTracer) have ~5-10% overhead
  - Both safe for production with appropriate settings

### Subprocess Orchestration (pabot, pyats)

- Use `py-spy record --subprocesses` to profile parent + all workers
- Each worker process gets separate profile: `profile_<pid>.svg`
- Analyze worker profiles individually to find bottlenecks
- VizTracer timeline shows parallel execution visually

### Implementation Recommendation

For Python ≤3.14:
```bash
pip install py-spy viztracer
py-spy record --subprocesses -o profile.svg -- python your_cli.py
viztracer --log_multiprocess --log_async -- python your_cli.py
```

For Python 3.15+:
```bash
python3.15 -m profiling.sampling run --subprocesses --async-aware --flamegraph your_cli.py
```


## Performance Analysis Completed (2026-02-07)

### Scale Test Instrumentation Results

**Baseline Run:** 2m 47s total runtime (target: 30 seconds)

**Phase Breakdown:**
- D2D Device Execution: 2m 43s (98% - BOTTLENECK)
- API Test Execution: 1m 7s (40% - parallel with D2D)
- Device Inventory Discovery: 3.3s (2%)
- Report Generation: 592ms (<1%)
- Job/Testbed Generation: <20ms per device (<1%)

**Per-Device Breakdown (4 devices in parallel):**
```
sd-dc-c8kv-01: 1m 54s (Job Gen: 0.9ms, Testbed Gen: 1.9ms, Exec: 1m 54s)
sd-dc-c8kv-02: 1m 55s (Job Gen: 13.4ms, Testbed Gen: 19.7ms, Exec: 1m 55s)
sd-dc-c8kv-03: 1m 57s (Job Gen: 1.2ms, Testbed Gen: 6.2ms, Exec: 1m 57s)
sd-dc-c8kv-04: 1m 55s (Job Gen: 1.2ms, Testbed Gen: 3.4ms, Exec: 1m 55s)
```

**Key Findings:**
- ✅ Parallelization working perfectly (4 devices complete within 3s window)
- ✅ Connection broker efficient (91% cache hit rate)
- ✅ Generation overhead negligible (<20ms per device)
- ❌ Device execution bottleneck: ~115 seconds per device for 11 tests

### Root Cause Identified

**Problem:** D2D job files missing `runtime.max_workers` configuration
- API tests: Set `runtime.max_workers = 5` → 11 tests in 3 parallel batches = 67s
- D2D tests: No `max_workers` set → PyATS defaults to sequential = 115s per device

**Evidence:**
- Examined generated job files in `/workspace/scale/results/pyats_results/`
- API job: Line 26 has `runtime.max_workers = 5` ✅
- D2D job: Missing `runtime.max_workers` entirely ❌
- Both use same for-loop calling `run()` 11 times (spawns 11 subprocesses)

**Per-Test Timing:**
```
API: 67s ÷ 11 tests = ~6s per test (with parallelization)
D2D: 115s ÷ 11 tests = ~10.4s per test (sequential)
Difference: ~50 seconds of subprocess startup overhead per device
```

### Solution

**File:** `nac_test/pyats_core/execution/job_generator.py`
**Method:** `generate_device_centric_job()` (line ~140)
**Change:** Add 2 lines after `runtime.connection_manager = ...`:
```python
# Set max workers for parallel test execution
runtime.max_workers = {self.max_workers}
```

**Expected Impact:**
- D2D per-device: 115s → 60-70s (1.7-1.9x faster)
- Total runtime: 2m 47s → ~1m 30s (1.8x faster)
- Moves toward 30-second target

**Risk Assessment:**
- LOW: API tests already use this pattern successfully
- Connection broker handles concurrent sessions
- Start conservative with `max_workers=3`, increase if stable

### Instrumentation Tools Created

**Files Created:**
- `nac_test/utils/timing.py` - Timing utilities with `timed_phase()` context manager
- `workspace/scale/run_with_timing.sh` - Execute with phase timing
- `workspace/scale/profile_pyspy.sh` - CPU profiling with flame graphs
- `workspace/scale/profile_viztracer.sh` - Timeline tracing
- `workspace/scale/PROFILING_GUIDE.md` - Complete profiling documentation
- `workspace/scale/PERFORMANCE_ANALYSIS.md` - Full analysis report
- `workspace/scale/ROOT_CAUSE_ANALYSIS.md` - Root cause and solution

**Files Modified:**
- `nac_test/pyats_core/orchestrator.py` - Added 7 timing phases
- `nac_test/pyats_core/execution/device/device_executor.py` - Added 3 per-device timing phases

### Lessons Learned

1. **PyATS Subprocess Model:**
   - Each `pyats.easypy.run()` call spawns new Python subprocess
   - Subprocess overhead: ~5 seconds (interpreter + framework + plugins)
   - Setting `runtime.max_workers` enables parallel execution within job

2. **Instrumentation Strategy:**
   - Phase timing with `timed_phase()` context manager highly effective
   - Minimal overhead, clear output, easy to add
   - Revealed bottleneck immediately without deep profiling

3. **Performance Analysis Priority:**
   - Start with high-level phase timing (fastest, cheapest)
   - Drill down with profilers only if root cause unclear
   - In this case, phase timing was sufficient to identify fix

4. **Architecture Asymmetry:**
   - API and D2D jobs structurally identical (both use for-loops with `run()`)
   - Only difference: API sets `max_workers`, D2D doesn't
   - Small configuration differences can have massive performance impact

### Connection Broker Performance

**Statistics from baseline run:**
```
Cache Hits: 44
Cache Misses: 4
Hit Rate: 91.67%
```

- ✅ Broker working well - high cache hit rate
- ✅ Connection reuse effective
- ✅ No connection overhead detected
- ✅ Scales well to 4 parallel devices

### Next Steps (NOT YET IMPLEMENTED)

1. Add `runtime.max_workers` to D2D job generator
2. Test with conservative `max_workers=3`
3. Validate with timing instrumentation
4. Gradually increase to `max_workers=5` if stable
5. Consider additional optimizations if still short of 30s target

**Status:** Analysis complete, solution documented, awaiting implementation decision
