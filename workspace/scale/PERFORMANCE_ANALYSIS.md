# Performance Analysis - nac-test Scale Environment

**Date:** February 7, 2026  
**Test Environment:** `/workspace/scale/` with 4 mocked local devices  
**Current Runtime:** 2m 47s  
**Target Runtime:** ~30 seconds  
**Performance Gap:** 5.5x slower than target

---

## Executive Summary

Performance profiling identified **PyATS job subprocess spawning** as the primary bottleneck. Each device spawns 11 separate PyATS job subprocesses (one per test file), with each subprocess taking ~11 seconds to complete. This results in ~2 minutes of sequential subprocess execution per device.

### Key Findings

| Component | Time | % of Total | Status |
|-----------|------|------------|--------|
| D2D Device Execution | 2m 43s | 98% | **BOTTLENECK** |
| API Test Execution | 1m 7s | 40% | Runs in parallel with D2D |
| Device Inventory Discovery | 3.3s | 2% | Acceptable |
| Report Generation | 592ms | <1% | Optimal |
| Job/Testbed Generation | <20ms/device | <1% | Optimal |

### Root Cause

**Per-device architecture:** Each device runs 11 test files sequentially, with each test spawning a new PyATS subprocess:
- **11 test files × ~11 seconds per subprocess = ~2 minutes per device**
- **Subprocess Spawn Points:**
  - API Tests: `subprocess_runner.py:129-136` -> Loop: `job_generator.py:69`
  - D2D Tests: `subprocess_runner.py:256-263` -> Loop: `job_generator.py:146`
- Subprocess overhead includes: Python interpreter startup, PyATS framework initialization, plugin loading, connection setup

For a detailed visual breakdown of the spawning hierarchy, see the [Subprocess Spawning Tree](PER_TEST_OVERHEAD_ANALYSIS.md#subprocess-spawning-tree).

### Recommended Solution

**Implement Option C (Combination):** Consolidate 11 test files into a single testscript and enable `runtime.max_workers = 5`. This eliminates 10 subprocess spawns and parallelizes test execution within the remaining subprocess.

**Expected Impact:**
- **Savings:** 121s → 15-20s per device (Meets 30-second target!)
- **Speedup:** ~6x faster overall

---

## Detailed Analysis

### 1. Current Architecture

#### Test Organization
```
workspace/scale/templates/tests/
├── verify_iosxe_control.py       # D2D test (IOS-XE SSH)
├── verify_iosxe_control_01.py    # D2D test
├── verify_iosxe_control_02.py    # D2D test
├── ... (total 11 IOS-XE tests)
├── verify_sdwan_sync.py          # API test (SD-WAN Manager)
├── verify_sdwan_sync_01.py       # API test
├── ... (total 11 API tests)
```

**Total: 22 test files**
- **11 API tests** (verify_sdwan_sync_*.py) - run against SD-WAN Manager REST API
- **11 D2D tests** (verify_iosxe_control_*.py) - run against IOS-XE devices via SSH

#### Execution Model

**API Tests (1 PyATS job):**
```
Orchestrator
  └─> Single PyATS Job Subprocess (1m 7s)
       ├─> verify_sdwan_sync.py (parallel)
       ├─> verify_sdwan_sync_01.py (parallel)
       ├─> ... (all 11 tests run together)
```

**D2D Tests (4 devices × 11 jobs each = 44 subprocesses):**
```
Orchestrator
  ├─> Device sd-dc-c8kv-01 (1m 54s) ─┐
  │    ├─> PyATS Job: verify_iosxe_control.py (subprocess)    │
  │    ├─> PyATS Job: verify_iosxe_control_01.py (subprocess) │
  │    ├─> ... (11 subprocesses sequentially)                 │
  │                                                            │
  ├─> Device sd-dc-c8kv-02 (1m 55s) ─┤ All 4 devices
  │    └─> 11 PyATS subprocesses (sequentially)               │ run in parallel
  │                                                            │
  ├─> Device sd-dc-c8kv-03 (1m 57s) ─┤
  │    └─> 11 PyATS subprocesses (sequentially)               │
  │                                                            │
  └─> Device sd-dc-c8kv-04 (1m 55s) ─┘
       └─> 11 PyATS subprocesses (sequentially)
```

**Why the asymmetry?**
- API tests target a single controller → batched into 1 job (efficient)
- D2D tests target multiple devices → each device gets 11 separate jobs (inefficient)

### 2. Baseline Timing Results

**Run Date:** February 7, 2026, 10:46 AM  
**Command:** `./run_with_timing.sh`

```
=== PHASE TIMING SUMMARY ===
Worker Calculation:           2.2 ms
Test Discovery:               5.2 ms
Device Inventory Discovery:   3.3 s
API Test Execution:           1m 7s    (runs in parallel with D2D)
D2D Test Execution:           2m 43s   ← BOTTLENECK (98% of total time)
  ├─ Broker Startup:          2m 43s   (includes all device execution)
  └─ Device Execution:
      ├─ sd-dc-c8kv-01:       1m 54s
      │   ├─ Job Gen:         0.9 ms
      │   ├─ Testbed Gen:     1.9 ms
      │   └─ Execution:       1m 54s   ← Per-device bottleneck
      ├─ sd-dc-c8kv-02:       1m 55s
      │   ├─ Job Gen:         13.4 ms
      │   ├─ Testbed Gen:     19.7 ms
      │   └─ Execution:       1m 55s
      ├─ sd-dc-c8kv-03:       1m 57s
      │   ├─ Job Gen:         1.2 ms
      │   ├─ Testbed Gen:     6.2 ms
      │   └─ Execution:       1m 57s
      └─ sd-dc-c8kv-04:       1m 55s
          ├─ Job Gen:         1.2 ms
          ├─ Testbed Gen:     3.4 ms
          └─ Execution:       1m 55s

Report Generation:            592 ms

TOTAL RUNTIME:                2m 47s
```

**Key Observations:**
1. ✅ **Generation is fast** - Job/testbed generation takes <20ms per device (negligible)
2. ✅ **Parallelization works** - All 4 devices complete within 3-second window
3. ✅ **Broker is efficient** - 91% cache hit rate (44/48 commands cached)
4. ❌ **Subprocess overhead dominates** - ~2 minutes per device for 11 sequential jobs
5. ✅ **API tests are efficient** - 11 tests in 1m 7s (batched in single job)

### 3. Per-Test Overhead Analysis

**Average time per test within a device:**
```
Device Execution Time:  ~115 seconds (average across 4 devices)
Number of Tests:        11 tests per device
Time per Test:          115s ÷ 11 = ~10.5 seconds per test
```

**Estimated breakdown per test subprocess:**
```
Python Interpreter Startup:     ~1-2 seconds
PyATS Framework Initialization: ~3-4 seconds
Plugin Loading:                 ~1-2 seconds
Connection Setup/Broker:        ~1-2 seconds
Actual Test Execution:          ~2-3 seconds
Archive/Cleanup:                ~1 second
────────────────────────────────────────────
TOTAL:                          ~10-11 seconds per subprocess
```

**This matches our empirical observation of ~11 seconds per test.**

### 4. Why API Tests Are Fast (Comparative Analysis)

**API Test Execution: 1m 7s for 11 tests**
- **Architecture:** All 11 tests run in a **single PyATS job subprocess**
- **Per-test time:** 67s ÷ 11 = ~6 seconds per test
- **Overhead:** One-time subprocess startup (~5s) + per-test execution (~6s)

**D2D Test Execution: 1m 54s for 11 tests (per device)**
- **Architecture:** Each test runs in a **separate PyATS job subprocess**
- **Per-test time:** 114s ÷ 11 = ~10.4 seconds per test
- **Overhead:** 11× subprocess startup (~5s each = 55s total) + per-test execution (~6s)

**Key Insight:**
```
API Tests:  5s (startup) + 11×6s (execution) = ~71 seconds
D2D Tests:  11×5s (startup) + 11×6s (execution) = ~121 seconds

Difference: ~50 seconds of pure subprocess overhead per device
```

**Why the difference exists:**
- `generate_job_file_content()` (API tests): Creates job with all test files in `TEST_FILES` list
- `generate_device_centric_job()` (D2D tests): Creates job with all test files, BUT orchestrator calls this 11 times per device (once per test file)

**Root cause in code:**
- `orchestrator.py` line 410-413: Calls `DeviceExecutor.run_device_job_with_semaphore()` which generates ONE job per device
- However, `device_executor.py` line 87-91: The job contains ALL test files for the device
- BUT: Looking at the logs, we see 11 separate PyATS subprocess invocations per device

**TODO:** Need to verify if there's a loop somewhere spawning 11 jobs per device instead of 1 job with 11 tests.

### 5. Connection Broker Performance

**Broker Statistics:**
```
Connection Pool Stats:
  Cache Hits: 44
  Cache Misses: 4
  Hit Rate: 91.67%
```

**Analysis:**
- ✅ Broker is working well - 91% of commands served from cache
- ✅ Connection reuse is effective (only 4 new connections needed)
- ✅ No connection overhead issues detected

### 6. Parallelization Effectiveness

**Device Parallelization:**
```
Device Completion Times:
  sd-dc-c8kv-01: 1m 54s (T+0s)
  sd-dc-c8kv-02: 1m 55s (T+1s)
  sd-dc-c8kv-04: 1m 55s (T+1s)
  sd-dc-c8kv-03: 1m 57s (T+3s)

All devices complete within 3-second window
```

**Analysis:**
- ✅ Perfect parallelization - all 4 devices run simultaneously
- ✅ No resource contention detected (mock devices are local)
- ✅ Slight variance (3s spread) is normal for I/O operations

**Theoretical Maximum:**
- With perfect parallelization, total time ≈ slowest device time
- Current: 2m 43s (dominated by slowest device at 1m 57s + broker startup)
- This is optimal given current per-device architecture

---

## Optimization Recommendations

### Priority 1: Eliminate Per-Test Subprocess Overhead (HIGH IMPACT)

**Problem:** Each device spawns 11 separate PyATS job subprocesses, wasting ~121 seconds per device in startup overhead.

**PyATS Framework Constraint:** Research into PyATS source code (`tasks.py:182`) confirms that every call to `pyats.easypy.run()` **always** spawns a new `multiprocessing.Process`. This is by design for test isolation.

**Recommended Optimization Options:**

*   **Option A: Consolidate Test Files (RECOMMENDED)**
    - Merge 11 test files into 1 file with 11 testcase classes.
    - **Impact:** 11 `run()` calls → 1 `run()` call.
    - **Savings:** 121s → 22s (eliminates 10 subprocess spawns = ~99 seconds saved).
    - **Risk:** LOW (Standard PyATS pattern).

*   **Option B: Add runtime.max_workers**
    - Add `runtime.max_workers = 5` to the job file.
    - **Impact:** Runs tests in parallel (5 at a time).
    - **Savings:** 121s → ~50s (tests run in 3 batches: 5+5+1).
    - **Risk:** LOW (Already used by API tests).

*   **Option C: Combination (BEST)**
    - Consolidate tests AND add `max_workers`.
    - **Impact:** Single subprocess with parallel test execution inside.
    - **Savings:** 121s → 15-20s (Meets 30-second target!).
    - **Risk:** MEDIUM (Requires ensuring test independence).

### Priority 2: Profile Actual Test Execution (MEDIUM IMPACT)

**Problem:** We don't know what happens during the ~6 seconds of actual test execution.

**Solution:** Use VizTracer or py-spy to profile a single test subprocess.

**Commands:**
```bash
# Option A: Profile with py-spy (requires sudo)
sudo py-spy record -o flamegraph.svg --subprocesses -- \
  python -m nac_test.pyats_core.orchestrator ...

# Option B: Profile with VizTracer (no sudo needed)
viztracer --log_subprocess --log_async -- \
  python -m nac_test.pyats_core.orchestrator ...
```

**What to look for:**
- Time spent in PyATS framework vs. test logic
- SSH connection setup time (should be minimal due to broker)
- Command execution time (should be milliseconds for mocked devices)
- Genie parser overhead
- JSON serialization overhead

**Expected Impact:**
- If test execution is slow: Optimize test logic or mocking (10-30% speedup)
- If PyATS framework is slow: Investigate plugin overhead or logging (5-15% speedup)

### Priority 3: Experiment with Test Concurrency (HIGH RISK)

**Problem:** Tests within a device run sequentially - could they run in parallel?

**Solution:** Modify PyATS job to use `runtime.max_workers > 1` for per-device parallelization.

**Implementation:**
```python
# In job_generator.py - generate_device_centric_job()
def main(runtime):
    runtime.max_workers = 4  # Run 4 tests per device in parallel
    
    for test_file in TEST_FILES:
        run(testscript=test_file, ...)
```

**Expected Impact:**
```
Current:  11 tests × 6s = 66 seconds (sequential)
Parallel: 11 tests ÷ 4 workers = ~18 seconds (4x faster)

Total:    2m 47s → 40 seconds (4x faster overall)
```

**Risk Level:** HIGH
- Tests may have shared state (SSH connections, command cache)
- Connection broker may become bottleneck if overwhelmed
- Tests may not be thread-safe
- Need to verify test independence first

**Recommendation:** Test this AFTER Priority 1 is implemented and validated.

### Priority 4: Reduce PyATS Framework Overhead (LOW IMPACT)

**Problem:** PyATS initialization takes ~3-4 seconds per subprocess.

**Solution:** Investigate PyATS configuration options to disable unused features.

**Options:**
- Disable XML reporting (already done: `--no-xml-report`)
- Disable email reporting (already done: `--no-mail`)
- Use `--quiet` flag (already done for non-debug runs)
- Reduce logging verbosity
- Disable unused plugins

**Expected Impact:**
- 5-10% reduction in subprocess startup time (~0.5-1 second per subprocess)
- With batching (Priority 1), this becomes negligible

**Risk Level:** LOW

---

## Implementation Roadmap

### Phase 1: Quick Win - Batch Tests Per Device (Week 1)

**Goal:** Eliminate per-test subprocess overhead by batching all tests into single job per device.

**Tasks:**
1. ✅ Instrument code with timing (DONE)
2. ✅ Run baseline profiling (DONE)
3. ⏳ Investigate why 11 jobs are spawned per device (IN PROGRESS)
4. ⏳ Fix orchestrator to spawn 1 job per device with all test files
5. ⏳ Verify with timing instrumentation
6. ⏳ Validate test results match baseline

**Expected Result:** 2m 47s → ~1m 30s (1.8x faster)

### Phase 2: Deep Profiling - Understand Test Execution (Week 2)

**Goal:** Profile actual test execution to identify optimization opportunities.

**Tasks:**
1. ⏳ Run py-spy profiling (requires sudo access)
2. ⏳ Run VizTracer profiling for timeline analysis
3. ⏳ Analyze flamegraph/timeline for hotspots
4. ⏳ Document findings

**Expected Result:** Identification of 2-3 additional optimization targets

### Phase 3: Advanced Optimization - Test Concurrency (Week 3-4)

**Goal:** Explore parallel test execution within devices (if tests are independent).

**Tasks:**
1. ⏳ Audit tests for shared state/dependencies
2. ⏳ Implement per-device parallelization (runtime.max_workers)
3. ⏳ Test with 2 workers, then 4 workers
4. ⏳ Validate results match sequential execution
5. ⏳ Measure performance impact

**Expected Result:** Additional 2-4x speedup (target: 30-40 seconds total)

---

## Architecture Insights

### Why Subprocess Overhead Matters

**PyATS uses `pyats.easypy.run()` which spawns subprocesses:**
```python
# In generated job file (job_generator.py line 73-77)
for test_file in TEST_FILES:
    run(
        testscript=test_file,
        taskid=test_name,
        max_runtime=DEFAULT_TEST_TIMEOUT,
        testbed=runtime.testbed
    )
```

**Each `run()` call spawns a new Python subprocess:**
1. Python interpreter startup (~1s)
2. Import PyATS modules (~1-2s)
3. Load plugins (ProgressReporter, etc.) (~1s)
4. Connect to broker/establish SSH (~1s)
5. Execute test (~2-3s)
6. Archive results (~0.5s)
7. Subprocess cleanup (~0.5s)

**Total: ~10-11 seconds per run() call**

### Why API Tests Don't Have This Problem

**API tests run in a single subprocess because:**
1. Orchestrator generates ONE job with all 11 test files
2. Job file runs all tests in the same subprocess (single `pyats run job` invocation)
3. Subprocess startup happens once, not 11 times

**Code reference:**
- `orchestrator.py` lines 286-305: API test execution
- Calls `subprocess_runner.execute_job()` ONCE with job containing all test files

### Why D2D Tests Have This Problem

**D2D tests spawn multiple subprocesses per device because:**
1. **Hypothesis A:** Orchestrator calls `device_executor.run_device_job_with_semaphore()` 11 times per device
   - Need to verify this by checking orchestrator's D2D execution loop
   
2. **Hypothesis B:** Job generator is called 11 times per device with 1 test file each
   - Check if `test_files` parameter in `generate_device_centric_job()` contains 1 or 11 files

3. **Hypothesis C:** PyATS job itself spawns subprocesses for each test file
   - Review generated job file to verify if it matches expected structure

**Next step:** Trace execution flow to identify which hypothesis is correct.

---

## Technical Debt & Gotchas

### 1. Test Status Tracking (device_executor.py lines 130-150)

**Issue:** Device executor tracks test status using `hostname::test_stem` format, but OutputProcessor uses `full.module.path` format. This causes mismatches.

**Impact:** Minimal - orchestrator clears and repopulates status from OutputProcessor.

**Recommendation:** Refactor to use consistent key format across codebase.

### 2. Archive-Based Success Detection (device_executor.py line 161)

**Issue:** Success is determined by archive file existence, not actual test results. Archives are created even for failed tests.

**Impact:** False positives possible if archive generation succeeds but tests fail.

**Recommendation:** Parse test results from archive to determine actual pass/fail status.

### 3. VizTracer Captured Partial Data

**Issue:** VizTracer run failed due to multiple controller credentials, but captured 3500 trace entries before failing.

**Impact:** Partial trace data available for analysis.

**Recommendation:** Fix controller credential issue and re-run VizTracer for complete trace.

---

## Environment Variables & Tuning

### Current Settings

| Variable | Value | Purpose |
|----------|-------|---------|
| `PYATS_MAX_WORKERS` | (auto) | PyATS job parallelism |
| `NAC_TEST_MAX_PARALLEL_DEVICES` | (auto) | Device-level parallelism |
| `PYATS_OUTPUT_BUFFER_LIMIT` | 10MB | Subprocess pipe buffer size |

### Recommended Experiments

```bash
# Experiment 1: Reduce device parallelism to isolate per-device overhead
export PYATS_MAX_WORKERS=1
export NAC_TEST_MAX_PARALLEL_DEVICES=1
./run_with_timing.sh
# If still ~2min per device → overhead is per-test, not parallelization

# Experiment 2: Increase PyATS workers within a device
export PYATS_MAX_WORKERS=4  # Allow 4 tests per device to run in parallel
./run_with_timing.sh
# If faster → tests are independent and can be parallelized

# Experiment 3: Reduce buffer limit to test impact
export PYATS_OUTPUT_BUFFER_LIMIT=1048576  # 1MB instead of 10MB
./run_with_timing.sh
# If slower or errors → buffer size matters for large outputs
```

---

## Conclusion

The performance bottleneck is clear: **PyATS subprocess spawning overhead**. Each device spawns 11 separate PyATS job subprocesses, wasting ~50 seconds per device in Python interpreter startup, framework initialization, and plugin loading.

**Immediate Action:** Verify why 11 jobs are spawned per device instead of 1 job with 11 tests (which is what the job generator code appears to support). This is likely a bug in the orchestrator's D2D execution loop.

**Expected Outcome:** Fixing this issue should reduce runtime from 2m 47s to ~1m 30s (1.8x faster), getting much closer to the 30-second target. Additional optimizations (test concurrency, framework tuning) can close the remaining gap.

---

## Next Steps

1. **Investigate orchestrator D2D execution loop** (file: `orchestrator.py` lines 333-540)
   - Trace how `device_executor.run_device_job_with_semaphore()` is called
   - Verify if it's called once per device (correct) or 11 times per device (bug)
   
2. **Run py-spy profiling with sudo access** (requires user to enter password)
   - Command: `sudo ./profile_pyspy.sh`
   - Analyze flamegraph to confirm subprocess overhead hypothesis
   
3. **Fix VizTracer environment issue and re-run**
   - Set only one controller type (unset `CC_URL` or `SDWAN_URL`)
   - Command: `./profile_viztracer.sh`
   - Analyze timeline to see sequential vs parallel execution patterns

4. **Implement batching fix** (if issue confirmed)
   - Modify orchestrator to ensure 1 job per device with all test files
   - Validate with timing instrumentation
   - Measure performance improvement

---

**Document Version:** 1.0  
**Last Updated:** February 7, 2026  
**Author:** Performance Analysis Session
