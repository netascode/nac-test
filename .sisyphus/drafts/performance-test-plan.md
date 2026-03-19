# Performance Re-Assessment Test Plan

**Date:** February 9, 2026  
**Purpose:** Compare `run()` vs `Task().run()` with disconnect timeout removed

---

## Test Setup

### Environment
- **Platform:** macOS (same as original tests)
- **Test Suite:** workspace/scale D2D tests
- **Testbed:** workspace/scale/testbed.yaml (already has POST_DISCONNECT_WAIT_SEC: 0)
- **Branch:** profiling

### Code Versions

**Version A: subprocess approach (baseline)**
- Commit: `35b639b` (before WIP commit)
- Uses: `run(testscript=..., max_runtime=..., testbed=...)`
- Behavior: Each test spawns subprocess, has timeout protection

**Version B: direct approach (current)**
- Commit: `3f1c6bb` (WIP commit, currently checked out)
- Uses: `Task(...).run()`
- Behavior: Tests run in-process, no timeout protection

### Key Difference in job_generator.py

**Before (35b639b):**
```python
from pyats.easypy import run

for idx, test_file in enumerate(TEST_FILES):
    test_name = Path(test_file).stem
    run(
        testscript=test_file,
        taskid=test_name,
        max_runtime=DEFAULT_TEST_TIMEOUT,
        testbed=runtime.testbed
    )
```

**After (3f1c6bb):**
```python
from pyats.easypy import Task

for idx, test_file in enumerate(TEST_FILES):
    test_name = Path(test_file).stem
    task = Task(
        testscript=test_file,
        taskid=test_name,
        max_runtime=DEFAULT_TEST_TIMEOUT,
        testbed=runtime.testbed
    )
    task.run()
```

---

## Test Execution Plan

### Test 1: Baseline (run() subprocess)

1. **Checkout baseline code:**
   ```bash
   git stash  # Save current changes
   git checkout 35b639b -- nac_test/pyats_core/execution/job_generator.py
   ```

2. **Run test:**
   ```bash
   cd workspace/scale
   ./run_with_timing.sh > test1_subprocess_run.log 2>&1
   ```

3. **Extract timing:**
   ```bash
   grep "Total testing time:" test1_subprocess_run.log
   ```

4. **Save results**

### Test 2: Direct (Task().run())

1. **Restore WIP code:**
   ```bash
   git checkout 3f1c6bb -- nac_test/pyats_core/execution/job_generator.py
   ```

2. **Run test:**
   ```bash
   cd workspace/scale
   ./run_with_timing.sh > test2_direct_taskrun.log 2>&1
   ```

3. **Extract timing:**
   ```bash
   grep "Total testing time:" test2_direct_taskrun.log
   ```

4. **Save results**

---

## Data Collection

### Metrics to Capture

For each test run:
- Total testing time (end-to-end)
- Per-device timing (if available)
- Number of tests executed
- Pass/fail status

### Expected Results

**Hypothesis:** With disconnect timeout removed (POST_DISCONNECT_WAIT_SEC: 0):
- Version A (subprocess): ~130-140s (no 44s disconnect penalty)
- Version B (direct): ~95s (no subprocess overhead)
- **Net speedup: ~30-40 seconds (25-30%)**

Previous measurements showed:
- Original with disconnect delay: 2m 55s (175s)
- Current with Task().run(): 1m 35s (95s)
- Difference: 80s

If 44s was disconnect timeout:
- Adjusted baseline: 175s - 44s = 131s
- Current: 95s
- Real speedup: 131s - 95s = 36s (27.5% faster)

---

## Analysis

### Questions to Answer

1. What is the actual speedup with disconnect timeout removed?
2. Is the 27% improvement worth the timeout/crash risk?
3. How many seconds per test are we saving?
4. Does the speedup scale linearly with test count?

### Comparison Table (To Fill)

| Metric | run() Subprocess | Task().run() Direct | Difference |
|--------|-----------------|---------------------|------------|
| Total Time | ??? | ??? | ??? |
| Per-test Overhead | ~9s | ~0s | ~9s |
| Subprocess Spawns | N (one per test) | 1 (entire job) | N-1 saved |
| Timeout Protection | YES | NO | Lost |
| Crash Isolation | YES | NO | Lost |

---

## Validation Checklist

- [ ] Both tests use same testbed.yaml (POST_DISCONNECT_WAIT_SEC: 0)
- [ ] Both tests run same test suite (workspace/scale D2D tests)
- [ ] Environment is consistent (no other processes interfering)
- [ ] Timing measurements are from same source (run_with_timing.sh)
- [ ] Results are reproducible (run each test 2-3 times)

---

## Next Steps After Testing

1. Update GitHub issue draft with corrected figures
2. Re-assess trade-offs with accurate speedup data
3. Discuss with architects using real numbers
4. Decision: proceed with optimization or revert?
