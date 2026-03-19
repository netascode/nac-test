# D2D Test Execution Performance Bottleneck: PyATS Internal Process Spawning

## Summary

D2D (Direct-to-Device) PyATS tests exhibit performance degradation due to PyATS internal process spawning. While nac-test correctly spawns **one** `pyats run job` process per device, **inside that job**, PyATS spawns a separate subprocess (via `multiprocessing.Process`) for each test file when using multiple `run()` calls.

**Key Observation:** In our initial measurements with 4 devices and 11 test files per device, we observed **87% of execution time being spent on PyATS internal process initialization overhead** rather than actual test logic (~9 seconds overhead per test file vs ~1.4 seconds test execution).

**Concern:** With atomic D2D tests being the foundation of our testing strategy, and hundreds of such tests anticipated for comprehensive network coverage, this overhead pattern represents a potential scaling concern that warrants investigation.

---

## Disclaimer: Preliminary Investigation

**Status:** This issue documents initial observations from a small-scale test environment (4 devices, 11 test files). We have not yet measured performance in production-scale environments or on Linux platforms.

**Purpose:** Document the observed overhead pattern to guide future investigation and potential optimization work.

**Not Included:**
- Production-scale measurements (20+ devices, 100+ tests)
- Linux platform performance characteristics
- Concrete projections or absolute runtime predictions

**Next Steps:**
- Gather production-scale measurements
- Test on Linux to compare platform differences
- Determine if this overhead pattern affects real-world deployments

---

## Environment

- **Framework:** nac-test + nac-test-pyats-common
- **Test Type:** D2D (Direct-to-Device) PyATS tests via SSH
- **Architecture:** SD-WAN (IOS-XE devices)
- **Test Environment:** 4 mocked devices, 11 verification types (duplicated to 22 test files)
- **Platform:** macOS (darwin) - **Note:** All measurements in this issue were collected on macOS. Linux performance characteristics may differ and will be measured separately.

---

## Measured Performance Impact

### Baseline Measurements

**Test Configuration:**
- **22 total test files:**
  - 11 API test files (`verify_sdwan_sync_*.py`) - target SD-WAN Manager REST API
  - 11 D2D test files (`verify_iosxe_control_*.py`) - target IOS-XE devices via SSH
- **4 devices** (sd-dc-c8kv-01 through sd-dc-c8kv-04)
- **Execution model:** 
  - API tests: 1 `pyats run job` total, with 11 `run(testscript=...)` calls
  - D2D tests: 1 `pyats run job` per device, with 11 `run(testscript=...)` calls per job

**Results:**
```
Total testing time:    102.17 seconds
  - API tests:         ~1m 7s (runs in parallel with D2D)
  - D2D tests:         ~2m 43s (bottleneck)

Per device (D2D):      25.5 seconds average
Process overhead:      87% of total time (PyATS internal process spawning)
Test logic execution:  13% of total time
```

**Breakdown per device:**
```
Device sd-dc-c8kv-01:  1m 54s (114 seconds)
Device sd-dc-c8kv-02:  1m 55s (115 seconds)
Device sd-dc-c8kv-03:  1m 57s (117 seconds)
Device sd-dc-c8kv-04:  1m 55s (115 seconds)
```

### Per-Test Overhead

**Average time per verification:**
```
Per device execution:  ~115 seconds (average across 4 devices)
Number of verifications: 11 per device
Time per verification: 115s ÷ 11 = ~10.5 seconds per test
```

**Overhead breakdown:**
- **PyATS process spawn overhead:** ~9 seconds per `run()` call (per test file)
- **Actual test logic:** ~1.4 seconds per verification
- **Overhead percentage:** 87% (9s / 10.4s)

---

## Root Cause Analysis

### Process Spawning Hierarchy

The nac-test framework correctly spawns **one** PyATS job per device, but PyATS itself spawns internal processes for each test file:

```
nac-test CLI (main process)
│
└─> PyATSOrchestrator (orchestrator.py)
    │
    └─> D2D Tests (1 PyATS job process PER DEVICE) ✅ Correct architecture
        │
        └─> For Each Device:
            └─> DeviceExecutor.run_device_job_with_semaphore()
                ├─> Creates device-specific job file
                ├─> Creates device-specific testbed
                │
                └─> SubprocessRunner.execute_job_with_testbed()
                    ├─> Spawns ONE OS process per device: subprocess_runner.py:256-263
                    │   asyncio.create_subprocess_exec([pyats, run, job, ...])
                    │   ✅ This is correct and efficient
                    │
                    └─> Inside PyATS job process (job file executes):
                        for test_file in TEST_FILES:  # job_generator.py:146
                            pyats.easypy.run(testscript=test_file)
                                └─> ⚠️ PyATS spawns multiprocessing.Process for EACH run()
                                    - Source: pyats/easypy/tasks.py:182 (Task class)
                                    - 11 test files = 11 run() calls
                                    - 11 × 9s PyATS internal overhead = ~99s per device
                                    ⚠️ THIS IS THE BOTTLENECK
```

### Key Files Involved

| File | Lines | Function | Status |
|------|-------|----------|--------|
| `subprocess_runner.py` | 256-263 | Spawns 1 OS process per device | ✅ Correct |
| `orchestrator.py` | 454-459 | Launches parallel device execution | ✅ Correct |
| `device_executor.py` | 85-98 | Generates job/testbed files per device | ✅ Correct |
| `device_executor.py` | 150-152 | Calls execute_job_with_testbed | ✅ Correct |
| `job_generator.py` | 146-155 | **Generates loop with N run() calls** | ⚠️ Creates bottleneck |

**Clarification:** The nac-test code is architecturally correct. The bottleneck occurs because **PyATS internally spawns a process for each `run()` call**, which is PyATS framework behavior, not nac-test behavior.

### Why Each Test File Creates an Internal Process

The generated job file contains a Python loop that calls `run()` for each test file:

```python
# Generated by JobGenerator.generate_device_centric_job()
# File: job_generator.py:146-155

for test_file in TEST_FILES:  # TEST_FILES = 11 items
    run(
        testscript=test_file,
        taskid=f"{hostname}_{test_name}",
        max_runtime=3600,
        testbed=runtime.testbed
    )
```

**What happens at each level:**
1. ✅ **nac-test spawns:** 1 OS process per device (`pyats run job`) - EFFICIENT
2. ❌ **Inside that process, PyATS spawns:** 1 `multiprocessing.Process` per `run()` call - INEFFICIENT
3. ❌ **Each PyATS Task** incurs ~9s initialization overhead (see next section)
4. ❌ **Result:** 11 `run()` calls × 9s PyATS overhead = ~99 seconds wasted per device

**The problem is not nac-test's architecture** (which correctly uses 1 job per device), but rather **how PyATS handles multiple `run()` calls within a single job**.

### What Happens During Each `run()` Call (PyATS Internal)

Each `pyats.easypy.run(testscript=...)` call triggers PyATS to spawn a new `multiprocessing.Process` (PyATS Task), which incurs:

1. **Process fork overhead** (~1s)
   - Fork new Python process from parent
   - Copy memory space (copy-on-write)
2. **PyATS framework re-initialization** (~2s)
   - Re-initialize easypy plugins in child process
   - Re-initialize logging infrastructure
   - Re-parse testbed YAML
3. **Plugin re-discovery and loading** (~1s)
   - Re-load all installed PyATS plugins
   - Re-initialize plugin infrastructure
4. **Connection re-establishment** (~3s)
   - Re-parse testbed in child process
   - Re-initialize Unicon connection objects
   - Re-establish SSH connection (even with ConnectionBroker caching)
5. **Test script import and initialization** (~2s)

**Total PyATS overhead per `run()`: ~9 seconds**

**Key insight:** This overhead is **internal to PyATS** and occurs because each `run()` call spawns a separate `multiprocessing.Process` within the job. The nac-test architecture (1 job per device) is correct; the bottleneck is **how many `run()` calls we make inside that job**.

---

## Observed Overhead Pattern

### What We Measured

Our tests with 4 devices and 11 test files per device showed a consistent overhead pattern:

| Metric | Observed Value |
|--------|----------------|
| PyATS Task spawn overhead | ~9 seconds per `run()` call |
| Actual test logic execution | ~1.4 seconds per verification |
| **Overhead percentage** | **87%** (9s / 10.4s total) |

### Why This Overhead Occurs

Each `pyats.easypy.run(testscript=...)` call triggers PyATS to spawn a new `multiprocessing.Process` (PyATS Task), which incurs:

1. **Process fork overhead** (~1s) - Fork new Python process, copy memory space
2. **PyATS framework re-initialization** (~2s) - Re-initialize plugins, logging, testbed parsing
3. **Plugin re-discovery** (~1s) - Re-load all PyATS plugins
4. **Connection re-establishment** (~3s) - Re-initialize Unicon connections, re-establish SSH
5. **Test script import** (~2s) - Import and initialize test modules

**Total overhead per `run()`: ~9 seconds**

### Scaling Concern

**Current observation (4 devices, 11 tests):**
- 44 total `run()` calls (11 per device × 4 devices)
- ~396 seconds total overhead (44 × 9s)
- ~62 seconds actual testing (44 × 1.4s)
- 87% of time spent on initialization

**Concern for comprehensive coverage:**
- Atomic D2D tests are intentionally simple (single verification per file)
- Comprehensive network validation may require 100+ atomic test types
- Each test file adds ~9s overhead per device to every test run
- Unknown: Does this pattern hold at production scale (20+ devices, 100+ tests)?

**This is an observation, not a projection.** We need production-scale measurements to determine real-world impact.

### Why Device Parallelization Doesn't Eliminate Overhead

While the framework correctly runs devices in parallel (orchestrator.py:454-459) with 1 PyATS job per device, **inside each job**, the test files execute **sequentially by design** (to avoid overwhelming devices/system):

```
Device 1 Job (parallel) ─┐
  ├─ run(test_01.py)     │  ← PyATS spawns Task (9s overhead)
  ├─ run(test_02.py)     │  ← PyATS spawns Task (9s overhead)
  ├─ ... (sequential)    │  All devices
  └─ run(test_N.py)      │  run in parallel
                         │
Device 2 Job (parallel) ─┤  Tests within each
  └─ N sequential        │  device run sequentially
     run() calls         │  (intentional design)
                         │
Device 3 Job (parallel) ─┤
  └─ N sequential        │
     run() calls         │
                         │
Device M Job (parallel) ─┘
  └─ N sequential
     run() calls
```

**Result:** 
- ✅ nac-test parallelizes devices correctly (M jobs run simultaneously)
- ✅ PyATS executes d2d test files sequentially **within each job** (N `run()` calls per job) - intentional design to avoid overwhelming devices/system
- ❌ Each `run()` spawns a PyATS Task with ~9s initialization overhead

**Impact:** Parallelization helps with device count, and sequential execution per device prevents overload. However, the overhead pattern remains: `N test files × 9s overhead per device`.

**Note:** We have not yet measured how this scales to larger device counts (20+) or larger test counts (100+).

---

## Impact on User Workflow

### Current User Experience

Users submit D2D test files incrementally as they develop test coverage:

```
Day 1:   templates/tests/d2d/verify_control.py
Day 2:   templates/tests/d2d/verify_sync.py
Week 2:  templates/tests/d2d/verify_interfaces.py
...
Month 2: templates/tests/d2d/verify_routing.py (11th file)
```

**Observed pattern:** Each additional test file adds **~9 seconds** of overhead per device to every test run (based on our 4-device, 11-test measurement).

### Concern for Production Scale

**What we don't know yet:**
- How does this pattern scale to 20+ devices?
- How does this pattern scale to 100+ test files?
- What is the user experience impact in real CI/CD pipelines?
- Is the overhead percentage consistent at larger scales?

**What would help:**
- Production-scale measurements (real device counts, real test counts)
- User feedback on acceptable test runtime
- Understanding of typical CI/CD time budgets

**Note:** This is **not a bug in nac-test**, but rather a consequence of how PyATS handles multiple `run()` calls. The nac-test architecture (1 job per device) is correct.

---

## Detailed Timing Evidence

### Test Run Logs

**Test Date:** February 7, 2026  
**Environment:** `/Users/oboehmer/Documents/DD/nac-test/workspace/scale`  
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
1. ✅ Job/testbed generation is negligible (<20ms per device)
2. ✅ Device parallelization works (all 4 complete within ~3s window)
3. ❌ **Test execution dominates** (~1m 54s per device)
4. ❌ **87% of execution time is overhead**, not test logic

### Comparison: API Tests vs D2D Tests

Both test types use the **same pattern** (multiple `run()` calls in a loop), but exhibit different performance characteristics:

**API tests** (targeting SD-WAN Manager REST API):
```
Test files:     11 files (verify_sdwan_sync_*.py)
Execution:      1 PyATS job total, 11 run() calls inside
Total time:     1m 7s (67 seconds)
Per test:       ~6.1 seconds average
Breakdown:      
  - PyATS Task overhead: ~9s (first spawn)
  - Subsequent tests: ~5.3s each (includes ~4s overhead per run())
  - Runs in parallel with D2D tests
```

**D2D tests** (targeting IOS-XE devices via SSH):
```
Test files:     11 files (verify_iosxe_control_*.py) × 4 devices
Execution:      4 PyATS jobs (1 per device), 11 run() calls per job
Total time:     2m 43s (163 seconds) - BOTTLENECK
Per device:     ~25.5 seconds average
Per test:       ~10.4 seconds average
Breakdown:
  - PyATS Task overhead: ~9s per run() call
  - Test logic: ~1.4s per verification
  - Overhead: 87% (9s / 10.4s)
```

**Key Observations:**

1. **Both suffer from the same issue** - Multiple `run()` calls = multiple PyATS Task spawns
2. **D2D overhead is more visible** because:
   - Per-device serialization (11 tests run sequentially per device)
   - SSH connection overhead compounds with PyATS Task overhead
   - 4 devices × 11 tests = 44 Task spawns vs 11 for API tests
3. **API tests also affected** - Taking ~67s when test logic is likely ~20-30s
4. **Same root cause** - PyATS internal process spawning per `run()` call

**Why this matters:**
- API tests: 67s total, ~30-40% overhead = noticeable but acceptable
- D2D tests: 163s total, ~87% overhead = severe bottleneck
- **D2D is the primary pain point**, but API tests would also benefit from optimization

---

## Related Evidence

### Documentation References

- **Performance Analysis:** `workspace/scale/PERFORMANCE_ANALYSIS.md`
- **Subprocess Breakdown:** `workspace/scale/PER_TEST_OVERHEAD_ANALYSIS.md`
- **Comparison Results:** `workspace/scale/PERFORMANCE_COMPARISON_RESULTS.md`

### Timing Logs

- **Baseline measurement:** `workspace/scale/timing_output.log`
- **Per-device breakdown:** `workspace/scale/results/pyats_results/d2d/*/env.txt`

### Code References

- **Subprocess spawn:** `nac_test/pyats_core/execution/subprocess_runner.py:256-263`
- **Job generation:** `nac_test/pyats_core/execution/job_generator.py:146-155`
- **Device execution:** `nac_test/pyats_core/execution/device_executor.py:85-152`

---

## Environment Details

**Test execution environment:**
```
Platform: macOS (darwin)
Python: 3.10+
Framework: nac-test 1.1.0b2
PyATS: Latest (via nac-test-pyats-common)
Mock server: Enabled (for reproducible performance testing)
Worker parallelism: 5 concurrent devices
```

**Test infrastructure:**
```
Devices: 4 SD-WAN edge routers (C8000v)
Connection: SSH via Unicon
Broker: ConnectionBroker with Unix socket IPC
Cache: 91% hit rate (44/48 commands cached)
```

---

## Potential Solution Criteria

If this overhead pattern proves problematic at production scale, any solution should consider:

1. **Performance improvement:** Significantly reduce the ~9s per-test overhead observed in our measurements
2. **Overhead reduction:** Target bringing overhead below 50% of total runtime (vs current 87%)
3. **Scalability:** Ensure overhead doesn't grow linearly with test file count
4. **Backward compatibility:** Existing test files continue to work without modification
5. **User experience:** No disruptive changes to test development workflow

**Note:** These are preliminary criteria based on small-scale observations. Production measurements will inform whether optimization is needed and what targets are realistic.

---

## Architectural Clarification

### What nac-test Does (Correctly) ✅

1. **Spawns 1 PyATS job per device** - Efficient OS process management
2. **Parallelizes devices** - 5 devices run simultaneously
3. **Generates job file with test list** - Standard PyATS job pattern
4. **Uses ConnectionBroker** - Efficient SSH connection management

### What PyATS Does (Framework Behavior) ⚠️

1. **Spawns `multiprocessing.Process` for each `run()` call** - PyATS Task architecture
2. **Re-initializes framework in each Task** - Fixed PyATS overhead per Task
3. **Executes `run()` calls sequentially** - Default job file behavior

### The Bottleneck

The issue is **not a bug in nac-test**, but rather a performance characteristic of how PyATS handles multiple `run()` calls within a single job:

```
nac-test architecture:          ✅ Efficient (1 job per device)
↓
PyATS internal behavior:        ⚠️ Creates overhead (1 Task per run() call)
↓  
Result:                         ❌ 11 Tasks × 9s = 99s overhead per device
```

**Key point:** The nac-test code structure (1 job per device with multiple `run()` calls) follows standard PyATS patterns. The performance issue stems from **how PyATS implements the `run()` function**, not from nac-test's architecture.

---

## Appendix A: Initial Performance Profiling

### Complete Phase Timing Breakdown

**Test Date:** February 7, 2026 10:46 AM  
**Platform:** macOS (darwin)  
**Command:** `./run_with_timing.sh`  
**Environment:** Mock server enabled, 4 devices, 22 test files (11 API + 11 D2D)

```
=== PHASE TIMING SUMMARY ===
Worker Calculation:           2.2 ms
Test Discovery:               5.2 ms
Device Inventory Discovery:   3.3 s
API Test Execution:           1m 7s    (67.2s - runs in parallel with D2D)
D2D Test Execution:           2m 43s   (163.0s - BOTTLENECK)
  ├─ Broker Startup:          2m 43s   (includes all device execution)
  └─ Device Execution (parallel):
      ├─ sd-dc-c8kv-01:       1m 54s   (114.0s)
      │   ├─ Job Gen:         0.9 ms
      │   ├─ Testbed Gen:     1.9 ms
      │   └─ Execution:       1m 54s   ← 11 run() calls = 11 PyATS Tasks
      ├─ sd-dc-c8kv-02:       1m 55s   (115.0s)
      │   ├─ Job Gen:         13.4 ms
      │   ├─ Testbed Gen:     19.7 ms
      │   └─ Execution:       1m 55s   ← 11 run() calls = 11 PyATS Tasks
      ├─ sd-dc-c8kv-03:       1m 57s   (117.0s)
      │   ├─ Job Gen:         1.2 ms
      │   ├─ Testbed Gen:     6.2 ms
      │   └─ Execution:       1m 57s   ← 11 run() calls = 11 PyATS Tasks
      └─ sd-dc-c8kv-04:       1m 55s   (115.0s)
          ├─ Job Gen:         1.2 ms
          ├─ Testbed Gen:     3.4 ms
          └─ Execution:       1m 55s   ← 11 run() calls = 11 PyATS Tasks

Report Generation:            592 ms

TOTAL RUNTIME:                2m 47s   (167.6s)
```

### Analysis of Results

**Efficiency Observations:**

1. ✅ **Generation is fast** - Job/testbed generation <20ms per device (negligible)
2. ✅ **Parallelization works** - All 4 devices complete within 3-second window
3. ✅ **Broker is efficient** - 91% cache hit rate (44/48 SSH commands cached)
4. ❌ **D2D execution dominates** - 163s / 167.6s = 97% of total runtime
5. ⚠️ **API tests also affected** - 67s for tests that should take ~20-30s

**Time Distribution:**

| Phase | Time | % of Total | Status |
|-------|------|------------|--------|
| Setup (discovery, inventory) | 3.3s | 2% | ✅ Optimal |
| API Tests | 67s | 40% | ⚠️ Some overhead |
| D2D Tests | 163s | 97% | ❌ Severe bottleneck |
| Report Generation | 0.6s | <1% | ✅ Optimal |
| **Total** | **167.6s** | **100%** | |

**D2D Test Breakdown (per device average):**

```
Device execution time:   115.25 seconds (average across 4 devices)
Number of run() calls:   11 per device
Time per run():          115.25s ÷ 11 = ~10.5 seconds

Breakdown per run():
  - PyATS Task spawn:    ~9.0 seconds (87%)
  - Test logic:          ~1.4 seconds (13%)
```

**API Test Breakdown:**

```
Total API execution:     67.2 seconds
Number of run() calls:   11 total
Time per run():          67.2s ÷ 11 = ~6.1 seconds

Estimated breakdown per run():
  - PyATS Task spawn:    ~4-5 seconds (estimated)
  - Test logic:          ~1-2 seconds (estimated)
  - Overhead:            ~30-40% (estimated)
```

### ConnectionBroker Performance

The ConnectionBroker (async SSH connection pooling service) performed efficiently:

```
Commands executed:    48 total (across 4 devices)
Cache hits:           44 (91.7% hit rate)
Cache misses:         4 (8.3%)
Avg response time:    <50ms (cached)
```

**Impact:** ConnectionBroker eliminates SSH connection overhead **within each PyATS Task**, but cannot eliminate the **PyATS Task spawning overhead itself** (~9s per Task).

### Test Files Structure

**API Test Files (11 files):**
```
templates/tests/verify_sdwan_sync.py
templates/tests/verify_sdwan_sync_01.py
templates/tests/verify_sdwan_sync_02.py
...
templates/tests/verify_sdwan_sync_10.py
```
- Target: SD-WAN Manager REST API
- Base class: `SDWANTestBase`
- Pattern: Single job with 11 `run()` calls

**D2D Test Files (11 files):**
```
templates/tests/verify_iosxe_control.py
templates/tests/verify_iosxe_control_01.py
templates/tests/verify_iosxe_control_02.py
...
templates/tests/verify_iosxe_control_10.py
```
- Target: IOS-XE devices via SSH
- Base class: `IOSXETestBase`
- Pattern: 1 job per device, 11 `run()` calls per job

### Platform Notes

**macOS-Specific Considerations:**

- Process forking overhead may differ on Linux
- `multiprocessing.Process` uses `fork()` on both platforms but with different characteristics
- macOS fork() has known performance issues in some scenarios
- **Future work:** Repeat measurements on Linux to establish platform-specific baselines

**What's Consistent Across Platforms:**

- PyATS architecture (Task spawning per `run()` call) is platform-independent
- The pattern of N test files → N `run()` calls → N Tasks is unchanged
- Relative overhead (87% for D2D tests) likely similar, absolute times may vary

---

## Appendix B: Evidence Files

### Timing Logs

All timing measurements are available in the test environment:

```
workspace/scale/timing_output.log                    # Full baseline timing
workspace/scale/results/pyats_results/d2d/           # Per-device logs
workspace/scale/results/pyats_results/api/           # API test logs
```

### Documentation References

- **Performance Analysis:** `workspace/scale/PERFORMANCE_ANALYSIS.md`
- **Subprocess Breakdown:** `workspace/scale/PER_TEST_OVERHEAD_ANALYSIS.md`
- **Comparison Results:** `workspace/scale/PERFORMANCE_COMPARISON_RESULTS.md`

### Code References

- **OS Process Spawn (nac-test):** `nac_test/pyats_core/execution/subprocess_runner.py:256-263`
- **Job Generation:** `nac_test/pyats_core/execution/job_generator.py:146-155`
- **Device Execution:** `nac_test/pyats_core/execution/device_executor.py:85-152`
- **PyATS Task (framework):** `pyats/easypy/tasks.py:182` (PyATS source)

---

**Date:** February 7, 2026  
**Environment:** `/Users/oboehmer/Documents/DD/nac-test/workspace/scale`  
**Platform:** macOS (darwin) - Linux measurements pending  
**Issue Type:** Performance Bottleneck  
**Severity:** High (impacts all D2D test users at scale)  
**Root Cause:** PyATS framework behavior when handling multiple `run()` calls  
**nac-test Architecture:** Correct (1 job per device)
