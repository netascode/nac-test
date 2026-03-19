# Task().run() Timeout Handling Analysis

**Date:** February 9, 2026  
**Issue:** Investigating whether `max_runtime` parameter is effective when using `Task().run()` instead of subprocess-based `run()`

---

## Background

We switched from subprocess-based `run(testscript=...)` to direct `Task().run()` execution for 45.4% performance improvement. However, PyATS maintainer warned:

> You can avoid the overhead of the process fork by calling the Task run API directly. **This breaks easypy if your script causes python to crash or calls sys.exit().**

**Key concern:** Does `max_runtime` parameter still work to prevent test timeouts from blocking subsequent tests?

---

## Current Implementation

**File:** `nac_test/pyats_core/execution/job_generator.py`

```python
task = Task(
    testscript=test_file,
    taskid=test_name,
    max_runtime=21600,  # DEFAULT_TEST_TIMEOUT = 6 hours
    testbed=runtime.testbed
)
task.run()  # Direct execution, no subprocess
```

**Question:** If a test hangs/times out, will `max_runtime` terminate it, or will it block all subsequent tests on that device?

---

## What We Know

### With Subprocess (OLD approach)
- `run(testscript=..., max_runtime=...)` spawns a `multiprocessing.Process`
- Timeout enforced by parent process monitoring child
- Stuck test can be killed, subsequent tests continue
- Overhead: ~9 seconds per test

### With Task().run() (NEW approach)
- `Task().run()` executes in same process (no fork)
- Unknown: How is `max_runtime` enforced without subprocess isolation?
- Unknown: Can timeout still kill a stuck test?
- Benefit: No subprocess overhead (45.4% faster)

---

## Risk Scenario

**Worst case:**
1. Test 3 of 11 hangs (infinite loop, deadlock, etc.)
2. `max_runtime` doesn't work without subprocess isolation
3. Remaining 8 tests never execute
4. User must manually kill process

**Impact:**
- 4 devices × 11 tests = 44 test executions
- One hang could block 25% of tests for that device
- Production CI/CD pipelines would hang

---

## Investigation Goals

1. **Does `max_runtime` work with `Task().run()`?**
   - How is timeout enforced? (signal.alarm, threading.Timer, etc.)
   - Does it require subprocess isolation?

2. **What happens on timeout?**
   - Does Task raise exception?
   - Can we catch and continue?
   - Are subsequent tests affected?

3. **Alternative approaches if timeout doesn't work:**
   - Wrap each `task.run()` in threading.Timer
   - Use signal.alarm for UNIX timeout
   - Use multiprocessing.Pool with timeout
   - Revert to subprocess for critical tests only

---

## Background Agents Launched

- **Agent 1 (explore):** Search PyATS Task timeout implementation
- **Agent 2 (librarian):** Search PyATS documentation on Task.run() timeouts
- **Agent 3 (explore):** Find timeout handling patterns in PyATS source

**Status:** Running in parallel, awaiting results...

---

## References

- PyATS maintainer comment: https://github.com/netascode/nac-test/issues/519#issuecomment-3866905917
- Task().run() implementation: commit `3f1c6bb`
- Performance analysis: `workspace/scale/TASK_RUN_API_PERFORMANCE_ANALYSIS.md`
