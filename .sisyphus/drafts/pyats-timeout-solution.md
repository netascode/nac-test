# Draft: PyATS Task Execution - Timeout Solution

**Date:** February 9, 2026  
**Status:** Interview Phase

---

## Problem Statement

We achieved a **45.4% performance improvement** by switching from `pyats.easypy.run()` to `Task().run()`, but discovered this **completely breaks timeout protection**.

| Approach | Runtime | Timeout Protection | Process Isolation |
|----------|---------|-------------------|-------------------|
| `run()` (subprocess) | 2m 55s | YES | YES |
| `task.run()` (direct) | 1m 35s | **NO** | NO |
| **Goal** | ~1m 35s | **YES** | Negotiable |

---

## Requirements (confirmed)

### Must Have
- [x] Performance improvement retained (~45% speedup vs original)
- [x] Timeout protection for stuck tests (prevent blocking subsequent tests)
- [x] Works on Linux (CI/CD primary platform)

### Nice to Have
- [ ] macOS support (development convenience, not critical)
- [ ] Process isolation (crash protection) - "very very rare" per user

### Constraints (from PyATS maintainer)
- PyATS subprocess design is intentional for crashes, timeouts, sys.exit() handling
- Calling `task.run()` directly "breaks easypy" if script crashes or calls sys.exit()

### User Answers (Feb 9, 2026)
- **Timeout frequency:** Very rare (< 1% of runs) → Can optimize for speed
- **Primary platform:** Linux CI only → SIGALRM is viable (UNIX-only OK)
- **Crash handling:** Tests are in subprocess already; crashes very rare
- **Hybrid approach:** Needs trade-off explanation before deciding

---

## Technical Decisions

1. **Platform:** Linux CI is primary → UNIX-only solutions (signal.SIGALRM) are acceptable
2. **Risk tolerance:** Timeouts < 1% → Can accept "best effort" timeout with some edge cases
3. **Process isolation:** Very rare crashes → Can relax isolation requirements
4. **Timeout location:** Job-level in orchestrator (subprocess_runner) — NOT inside job file
5. **Granularity:** Batch grouping for API tests; D2D stays per-device
6. **Blast radius:** API tests need smaller batches; D2D per-device is acceptable

### Chosen Approach: Job-Level Timeout with Batch Grouping

```
API Tests:
  Batch 1 (tests 1-10) → Job subprocess → timeout at orchestrator level
  Batch 2 (tests 11-20) → Job subprocess → timeout at orchestrator level
  ...

D2D Tests:
  Device A (all tests) → Job subprocess → timeout at orchestrator level
  Device B (all tests) → Job subprocess → timeout at orchestrator level
  ...
```

**Implementation Location:** `subprocess_runner.py` using `asyncio.wait_for()`

---

## Research Findings

### Execution Hierarchy (CRITICAL)

```
nac-test orchestrator (Python async)
    ↓
subprocess_runner.execute_job()
    ↓
asyncio.create_subprocess_exec("pyats run job ...")   ← SUBPROCESS #1 (easypy)
    ↓
Inside easypy job file main():
    Task(...).run()   ← Currently: in-process (was subprocess fork before)
```

**Key Insight (from user):** The job file itself is ALREADY running in a subprocess!
- `subprocess_runner.py` spawns `pyats run job ...` via `asyncio.create_subprocess_exec()`
- The generated job file's `main()` function runs INSIDE that subprocess
- When we call `task.run()` directly, it runs in-process within that subprocess

**Implications for SIGALRM:**
- If SIGALRM kills the job (e.g., via `raise TimeoutError`), it terminates the ENTIRE easypy subprocess
- All subsequent tests in that job file would be killed too
- This is NOT equivalent to killing just one test

### SSH Connection Architecture

**From user:** "SSH connections are actually handled by the connection broker outside the pyATS job execution"

```
orchestrator (parent process)
    └── Connection Broker (in parent)
            ↓ Unix socket
    └── pyats subprocess (job file)
            └── Test → BrokerClient → socket → Broker → actual SSH
```

**Implication:** Killing the easypy subprocess doesn't necessarily close SSH connections.
The broker keeps them alive. This is good for cleanup concerns.

### Constants Usage

`DEFAULT_TEST_TIMEOUT = 21600` (6 hours) used in:
- `job_generator.py:76` - API tests `max_runtime={DEFAULT_TEST_TIMEOUT}`
- `job_generator.py:154` - D2D tests `max_runtime={DEFAULT_TEST_TIMEOUT}`
- PRD docs as reference

---

## Open Questions

### Resolved
1. ~~**Risk Tolerance:** What happens if a test hangs forever?~~ → Kill job, lose batch (acceptable at <1% timeout rate)
2. ~~**Platform Priority:** macOS development vs Linux CI~~ → Linux CI primary
3. ~~**Crash Handling:** How critical is process isolation?~~ → Not critical; crashes very rare
4. ~~**Timeout Location:** Signal in job vs orchestrator?~~ → Orchestrator (subprocess_runner)

### Needs Team Input
5. **Batch Size for API Tests:** How many tests per batch? 
   - Smaller batch = more subprocess overhead but less blast radius
   - Larger batch = faster but more tests lost on timeout
   - Suggested default: 10 tests per batch (tunable via env var?)

6. **Timeout Duration:** Currently 6 hours (`DEFAULT_TEST_TIMEOUT = 21600`).
   - Should batch timeout = `batch_size × per_test_timeout`?
   - Or a fixed job timeout (e.g., 1 hour per batch)?

---

## Candidate Solutions (To Evaluate)

1. **Signal-based timeout (SIGALRM)** — UNIX only, wrap task.run()
2. **Threading + timeout detection** — Can't kill threads, resource leak risk
3. **Hybrid approach** — Direct for API, subprocess for D2D
4. **Pre-warmed process pool** — Reduce fork overhead while keeping isolation
5. **Custom Task subclass** — Override with in-process timeout
6. **Unicon-level timeout** — Rely on SSH connection timeouts

---

## Scope Boundaries

### IN Scope
- Timeout mechanism implementation
- Performance optimization retention
- macOS + Linux support

### OUT of Scope (Explicit)
- Windows support (unless trivial)
- Changes to PyATS upstream
- Robot Framework execution changes
