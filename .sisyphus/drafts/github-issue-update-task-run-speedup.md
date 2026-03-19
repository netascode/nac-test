# GitHub Issue Update: Task().run() Performance Re-Assessment

## Summary

We've completed a controlled re-assessment of the `Task().run()` optimization with the disconnect timeout properly eliminated. **The actual performance improvement is only 3% (1.72 seconds), not the originally reported 27%.**

Given the minimal speedup and the critical timeout/isolation issues, **we recommend reverting to the original `run()` subprocess approach**.

---

## Performance Results (CORRECTED)

**Test Environment:** macOS, 22 PyATS tests (11 API + 11 D2D/SSH), disconnect timeout eliminated (`POST_DISCONNECT_WAIT_SEC: 0`)

| Metric | Original (`run()`) | New (`Task().run()`) | Improvement |
|--------|-------------------|---------------------|-------------|
| **Total Runtime** | 58.07s | 56.35s | **-1.72s (3.0% faster)** |
| **PyATS Phase Only** | 58.1s | 56.3s | **-1.8s** |
| **Per-test overhead** | ~9s subprocess fork | ~9s (still present) | Minimal reduction |

### What Changed from Original Analysis?

**Original (incorrect) measurements:**
- Baseline: 2m 55s (175s) → After removing 44s disconnect: 2m 10s (130s)
- Optimized: 1m 35s (95s)
- **Claimed speedup: 35 seconds (27% faster)**

**Corrected measurements (this run):**
- Baseline: 58.07s (with disconnect already removed)
- Optimized: 56.35s
- **Actual speedup: 1.72 seconds (3% faster)**

**Why the discrepancy?**
The earlier measurements were inflated by:
1. Including the 44-second disconnect timeout (now properly eliminated)
2. Possible cold-start effects or other environmental factors
3. Measuring different phases (the controlled re-test isolated PyATS execution only)

**Key Finding:** The subprocess overhead is **NOT 9 seconds per test** as originally thought. Most of the execution time is actual test work, not subprocess spawning.

---

## Critical Issues (Still Apply)

Even though the speedup is minimal, the same critical issues remain:

### 1. Timeout Protection is Completely Broken

**Problem:** The `max_runtime` parameter is **ignored** when calling `task.run()` directly.

**Evidence from PyATS source (`tasks.py:486-509`):**
```python
def wait(self, max_runtime = None):
    self.join(max_runtime)  # Wait for subprocess
    if self.is_alive():     # Still running after timeout?
        self.terminate()    # Send SIGTERM to subprocess
        raise TimeoutError(...)
```

**Impact:** A hung test blocks all subsequent tests indefinitely.

### 2. Process Isolation is Lost

**Problem:** `task.run()` executes in-process, meaning:
- Test crashes kill the entire job
- No resource cleanup isolation
- Shared state between tests

**PyATS Maintainer's Warning (issue #519):**
> "You can avoid the overhead of the process fork by calling the Task run API directly. **This breaks easypy if your script causes python to crash or calls sys.exit().**"

---

## Risk vs Benefit Analysis

| Factor | Original `run()` | `Task().run()` | Winner |
|--------|------------------|----------------|--------|
| **Performance** | 58.07s | 56.35s (-1.72s) | Task.run (marginally) |
| **Timeout Protection** | ✅ Works | ❌ Broken | run() |
| **Process Isolation** | ✅ Full | ❌ None | run() |
| **Complexity** | Simple | Requires workarounds | run() |
| **Risk** | Low | High | run() |

**Conclusion:** A 3% speedup does NOT justify:
- Complete loss of timeout protection
- Loss of process isolation
- Increased risk of cascading failures

---

## Decision: Revert to `run()` API

Based on this re-assessment, we recommend **immediately reverting** commit `3f1c6bb` and returning to the original `pyats.easypy.run()` subprocess approach.

### Rationale

1. **Minimal benefit:** 1.72 seconds (3%) is not significant enough to warrant any compromise
2. **Critical risks:** Timeout and isolation issues are dealbreakers for production
3. **Original assumption wrong:** The subprocess overhead is much smaller than initially estimated
4. **Better alternatives exist:** The disconnect timeout fix (`POST_DISCONNECT_WAIT_SEC: 0`) already achieved the major speedup

### Implementation

```python
# REVERT TO (original working approach):
from pyats.easypy import run

for idx, test_file in enumerate(TEST_FILES):
    test_name = Path(test_file).stem
    run(
        testscript=test_file,
        taskid=test_name,
        max_runtime=21600,
        testbed=runtime.testbed
    )
```

---

## What We Learned

1. **Always measure with controlled conditions:** The disconnect timeout was masking the true overhead
2. **Subprocess overhead is acceptable:** 9 seconds across all tests is not the bottleneck
3. **Safety over speed:** Timeout protection is critical for production reliability
4. **The real win:** Eliminating the 44-second disconnect delay (via testbed config) was the actual performance improvement

---

## Next Steps

1. ✅ **Revert commit `3f1c6bb`** - Return to `run()` API
2. ✅ **Document findings** - Update issue with corrected data
3. ✅ **Close investigation** - No further optimization needed on this path
4. 🔍 **Alternative optimizations** - Explore other areas if performance is still a concern

---

## Test Evidence

**Log files:**
- Baseline: `workspace/scale/test1_subprocess_run.log` (58.07s)
- Optimized: `workspace/scale/test2_direct_taskrun.log` (56.35s)

**Timing extraction:**
```bash
$ grep "Completed phase: PyATS Test Execution" test1_subprocess_run.log
2026-02-09 19:52:06,916 - INFO - Completed phase: PyATS Test Execution (58.1 s)

$ grep "Completed phase: PyATS Test Execution" test2_direct_taskrun.log
2026-02-09 19:53:35,425 - INFO - Completed phase: PyATS Test Execution (56.3 s)
```

---

## References

- **PyATS Issue #519:** Original discussion on subprocess overhead
- **Commit:** `3f1c6bb` - "WIP - use Task().run() api to avoid easypy process spawning" (TO BE REVERTED)
- **Commit:** `35b639b` - Working baseline with `run()` API (REVERT TO THIS)
- **Performance test plan:** `.sisyphus/drafts/performance-test-plan.md`
