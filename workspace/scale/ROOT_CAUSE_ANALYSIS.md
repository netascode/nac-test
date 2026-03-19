# Root Cause Analysis - D2D Test Performance Issue

**Date:** February 7, 2026  
**Issue:** D2D tests take 1m 54s per device vs API tests 1m 7s for same workload  
**Root Cause:** D2D job files missing `runtime.max_workers` configuration

---

## Problem Statement

Performance testing revealed that D2D (device-to-device) tests run significantly slower than API tests, despite having identical test structure:

| Test Type | # Tests | Runtime | Per-Test Time |
|-----------|---------|---------|---------------|
| API Tests | 11 | 1m 7s | ~6s |
| D2D Tests (per device) | 11 | 1m 54s | ~10.4s |

**Gap:** D2D tests are **1.7x slower** than API tests for the same workload.

---

## Investigation Findings

### Generated Job Files Comparison

**API Job File** (`/workspace/scale/results/pyats_results/api/tmp7_xh3iiw_api_job.py`):
```python
def main(runtime):
    """Main job file entry point"""
    # Set max workers
    runtime.max_workers = 5  # ✅ Allows 5 tests to run in parallel
    
    # Run all test files
    for idx, test_file in enumerate(TEST_FILES):
        test_name = Path(test_file).stem
        run(
            testscript=test_file,
            taskid=test_name,
            max_runtime=21600,
            testbed=runtime.testbed
        )
```

**D2D Job File** (`/workspace/scale/results/pyats_results/d2d/sd-dc-c8kv-01/tmp1yjgi44i.py`):
```python
def main(runtime):
    """Main job file entry point for device-centric execution"""
    # Set up environment variables that SSHTestBase expects
    os.environ['DEVICE_INFO'] = json.dumps(DEVICE_INFO)
    
    # Create and attach connection manager to runtime
    runtime.connection_manager = DeviceConnectionManager(max_concurrent=1)
    
    # ❌ MISSING: runtime.max_workers is never set
    #    PyATS defaults to sequential execution (max_workers=1)
    
    # Run all test files for this device
    for idx, test_file in enumerate(TEST_FILES):
        test_name = Path(test_file).stem
        run(
            testscript=test_file,
            taskid=f"{safe_hostname}_{test_name}",
            hostname=HOSTNAME,
            max_runtime=21600,
            testbed=runtime.testbed
        )
```

### Root Cause

**The D2D job generator does not set `runtime.max_workers`**, causing PyATS to default to sequential execution:

**File:** `nac_test/pyats_core/execution/job_generator.py`

**API Job Generator** (lines 27-81):
```python
def generate_job_file_content(self, test_files: list[Path]) -> str:
    job_content = textwrap.dedent(f'''
    def main(runtime):
        """Main job file entry point"""
        # Set max workers
        runtime.max_workers = {self.max_workers}  # ✅ SETS MAX WORKERS
        
        # Run all test files
        for idx, test_file in enumerate(TEST_FILES):
            run(testscript=test_file, taskid=test_name, ...)
    ''')
    return job_content
```

**D2D Job Generator** (lines 83-157):
```python
def generate_device_centric_job(self, device: dict[str, Any], test_files: list[Path]) -> str:
    job_content = textwrap.dedent(f'''
    def main(runtime):
        """Main job file entry point for device-centric execution"""
        os.environ['DEVICE_INFO'] = json.dumps(DEVICE_INFO)
        runtime.connection_manager = DeviceConnectionManager(max_concurrent=1)
        
        # ❌ MISSING: No runtime.max_workers line
        
        # Run all test files for this device
        for idx, test_file in enumerate(TEST_FILES):
            run(testscript=test_file, taskid=..., ...)
    ''')
    return job_content
```

---

## Impact Analysis

### Current Behavior (Without `runtime.max_workers`)

**D2D Tests:** PyATS defaults to `max_workers = 1` (sequential)
```
Test 01 ────> [10s] ──┐
Test 02 ────────────> [10s] ──┐
Test 03 ──────────────────> [10s] ──┐
...
Test 11 ──────────────────────────────────────────> [10s]

Total: 11 × 10s = 110 seconds per device
```

**API Tests:** Explicitly sets `max_workers = 5` (parallel)
```
Test 01 ──> [10s] ──┐
Test 02 ──> [10s] ──┤
Test 03 ──> [10s] ──┤ Batch 1 (20s)
Test 04 ──> [10s] ──┤
Test 05 ──> [10s] ──┘
Test 06 ────────────> [10s] ──┐
Test 07 ────────────> [10s] ──┤
Test 08 ────────────> [10s] ──┤ Batch 2 (20s)
Test 09 ────────────> [10s] ──┤
Test 10 ────────────> [10s] ──┘
Test 11 ────────────────────────> [10s] ── Batch 3 (20s)

Total: 3 batches × 20s = 60 seconds (assuming 10s per test including overhead)
```

**Observed results:**
- API: 67 seconds (matches 3-batch model with some overhead)
- D2D: 114 seconds per device (matches sequential model)

---

## Solution

### Add `runtime.max_workers` to D2D Job Generator

**File:** `nac_test/pyats_core/execution/job_generator.py`  
**Method:** `generate_device_centric_job()` (lines 83-157)

**Change:**
```python
def generate_device_centric_job(self, device: dict[str, Any], test_files: list[Path]) -> str:
    # ... existing code ...
    
    job_content = textwrap.dedent(f'''
    def main(runtime):
        """Main job file entry point for device-centric execution"""
        # Set up environment variables that SSHTestBase expects
        os.environ['DEVICE_INFO'] = json.dumps(DEVICE_INFO)
        
        # Create and attach connection manager to runtime
        runtime.connection_manager = DeviceConnectionManager(max_concurrent=1)
        
        # ADD THIS LINE: Set max workers for parallel test execution
        runtime.max_workers = {self.max_workers}
        
        # Sanitize hostname for taskid
        safe_hostname = re.sub(r'[^a-zA-Z0-9_]', '_', HOSTNAME).lower()
        
        # Run all test files for this device
        for idx, test_file in enumerate(TEST_FILES):
            run(testscript=test_file, taskid=..., ...)
    ''')
    return job_content
```

### Expected Impact

**Before (sequential):**
```
D2D per device: 11 tests × 10s = 110 seconds
Total (4 devices in parallel): 110 seconds
```

**After (5 parallel workers):**
```
D2D per device: 11 tests ÷ 5 workers = 3 batches
                3 batches × 20s = 60 seconds
Total (4 devices in parallel): 60 seconds
```

**Performance Gain:**
- Per-device speedup: 110s → 60s (**1.8x faster**)
- Total test time: 2m 47s → ~1m 30s (**1.8x faster**)

This gets us much closer to the 30-second target. Additional optimizations may be needed to reach that goal.

---

## Considerations & Risks

### Risk 1: SSH Connection Limit

**Concern:** Running 5 tests per device in parallel may overwhelm SSH connections.

**Mitigation:**
- Connection broker already handles connection pooling
- Mock devices (local) have no connection limits
- Real devices: SSH typically supports 5-10 concurrent sessions
- If needed, reduce `max_workers` to 3 or 4

**Recommendation:** Start with `max_workers = 3` for D2D tests (conservative) and increase if stable.

### Risk 2: Test Independence

**Concern:** Tests may have shared state causing failures when run in parallel.

**Analysis:**
- Tests use connection broker for shared connections (thread-safe)
- Each test has its own task context in PyATS
- Command cache is thread-safe (Redis-backed or in-memory dict with locks)
- Mock server handles concurrent requests

**Recommendation:** Monitor first run for race conditions; add test isolation if needed.

### Risk 3: Connection Manager Conflict

**Concern:** `DeviceConnectionManager(max_concurrent=1)` may limit parallelization.

**Analysis:**
```python
runtime.connection_manager = DeviceConnectionManager(max_concurrent=1)
```

This limits concurrent SSH connections to 1 per device. If tests use the connection manager directly (bypassing broker), they'll serialize anyway.

**Resolution Options:**
1. Increase `max_concurrent` to match `max_workers`
2. Remove connection manager from D2D jobs (rely on broker)
3. Verify tests use broker, not connection manager

**Recommendation:** Investigate if connection manager is actually used by D2D tests. If broker handles all connections, connection manager may be unnecessary.

---

## Implementation Steps

### Step 1: Code Change

1. Edit `/nac_test/pyats_core/execution/job_generator.py`
2. In `generate_device_centric_job()` method (line ~133), add after line 140:
   ```python
   # Set max workers for parallel test execution
   runtime.max_workers = {self.max_workers}
   ```
3. Verify indentation matches surrounding code

### Step 2: Test with Conservative Settings

```bash
# Test with max_workers=3 for D2D tests (conservative)
export PYATS_MAX_WORKERS=3
cd /Users/oboehmer/Documents/DD/nac-test/workspace/scale
./run_with_timing.sh
```

**Expected results:**
- D2D per device: ~70-80 seconds (down from 114s)
- Total runtime: ~2m 0s (down from 2m 47s)

### Step 3: Gradually Increase Workers

If Step 2 is stable:
```bash
# Test with max_workers=5 (matches API tests)
export PYATS_MAX_WORKERS=5
./run_with_timing.sh
```

**Expected results:**
- D2D per device: ~60-70 seconds
- Total runtime: ~1m 30s

---

## Alternative Solutions (If Main Solution Fails)

### Option A: Combine All Tests into Single TestScript

Instead of 11 separate test files with `run()` calls, create one test file with 11 test methods.

**Pros:** No subprocess overhead (1 subprocess per device)  
**Cons:** Requires restructuring test files, loses modularity

**Expected Impact:** D2D per device: 11 tests × 6s = 66 seconds (1.7x faster)

### Option B: Batch Tests into Fewer Files

Group related tests into 3-4 files instead of 11.

**Pros:** Reduces subprocess count without losing all modularity  
**Cons:** Requires reorganizing test files

**Expected Impact:** D2D per device: 4 subprocesses × 30s = 120 seconds (no improvement, worse than parallel)

### Option C: Use PyATS `--testbed-file` with Multi-Device Testbed

Run all devices and tests in a single PyATS job with multi-device testbed.

**Pros:** Maximum parallelization, single subprocess  
**Cons:** Requires significant architecture changes, may complicate debugging

**Expected Impact:** Total runtime: ~30-60 seconds (3-5x faster)

---

## Success Criteria

After implementing the fix (`runtime.max_workers` in D2D job generator):

| Metric | Current | Target | Success |
|--------|---------|--------|---------|
| D2D per-device time | 1m 54s | <1m 10s | ✅ if <1m 10s |
| Total test time | 2m 47s | <1m 40s | ✅ if <1m 40s |
| Test pass rate | 100% | 100% | ✅ if no new failures |
| Connection broker hit rate | 91% | >85% | ✅ if maintained |

---

## Conclusion

The root cause of slow D2D test performance is **missing `runtime.max_workers` configuration in D2D job files**. API tests already use parallel execution (`max_workers=5`), which is why they're 1.7x faster despite identical workload.

**Fix:** Add one line to `generate_device_centric_job()` method:
```python
runtime.max_workers = {self.max_workers}
```

**Expected Impact:** 1.8x speedup, reducing total runtime from 2m 47s to ~1m 30s.

**Risk Level:** LOW - API tests already use this pattern successfully. Main concern is SSH connection limits on real devices (mitigated by starting with conservative `max_workers=3`).

---

**Next Step:** Implement the code change and validate with timing instrumentation.
