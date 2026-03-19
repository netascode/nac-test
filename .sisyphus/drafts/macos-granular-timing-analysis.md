# macOS D2D Granular Timing Analysis

**Date:** February 8, 2026  
**Platform:** macOS (darwin), Python 3.12  
**Test Configuration:** 4 devices, 22 test files (11 API + 11 D2D)

---

## Executive Summary

**Total Runtime:** 2m 54.9s (174.9s)  
**D2D Execution (Broker Startup):** 2m 50s (170s)  
**Per-Device Average:** 42.5s (170s ÷ 4 devices)

**Key Finding:** First test takes **16.6s** (includes SSH setup), subsequent tests take **5.8s** (2.86× speedup from connection reuse).

---

## Phase Timing Breakdown

| Phase | Duration | Percentage | Notes |
|-------|----------|------------|-------|
| **Test Discovery** | 2.9 ms | <0.1% | File discovery |
| **Device Inventory Discovery** | 3.4 s | 1.9% | Import test, resolve devices |
| **API Test Execution** | 0.0 ms | <0.1% | Orchestration only |
| **D2D Test Execution** | 0.2 ms | <0.1% | Orchestration only |
| **Broker Startup** | 2m 50s (170s) | 97.2% | **Main execution** |
| **Report Generation** | 6.6 ms | <0.1% | HTML report creation |
| **TOTAL** | 2m 54.9s (174.9s) | 100% | End-to-end |

**Critical Insight:** 97.2% of time is in "Broker Startup" which includes all device test execution.

---

## D2D Test Execution Timing

### First Test (verify_iosxe_control) - Includes SSH Connection Setup

| Device | Duration | Notes |
|--------|----------|-------|
| Device 1 | 16.2s | Includes SSH handshake, auth, first command |
| Device 2 | 16.5s | |
| Device 3 | 16.2s | |
| Device 4 | 17.6s | |
| **Average** | **16.6s** | ~30s SSH setup + ~1.5s test logic (estimated) |

**Breakdown (estimated):**
- SSH connection establishment: ~14-15s
- Test logic execution: ~1.5-2s

### Second Test (verify_iosxe_control_01) - Connection Reuse

| Device | Duration | Notes |
|--------|----------|-------|
| Device 1 | 6.1s | Connection reused from first test |
| Device 2 | 5.9s | |
| Device 3 | 5.2s | |
| Device 4 | 6.0s | |
| **Average** | **5.8s** | Pure test execution (no SSH setup) |

**Speedup from Connection Reuse:** **2.86×** (16.6s → 5.8s)

**Breakdown (estimated):**
- PyATS framework overhead: ~4s
- Test logic execution: ~1.5-2s

---

## API Test Execution Timing (for comparison)

**Test:** verify_sdwan_sync (REST API calls to SD-WAN Manager)

| Metric | Value |
|--------|-------|
| **Count** | 11 tests |
| **Min** | 0.8s |
| **Max** | 2.6s |
| **Average** | 1.9s |
| **Total** | 20.7s |

**Observation:** API tests are **3× faster** than D2D tests (1.9s vs 5.8s) because:
- No SSH connection overhead
- Faster HTTP requests vs SSH commands
- Less PyATS framework overhead

---

## Connection Broker Performance

| Metric | Value | Hit Rate |
|--------|-------|----------|
| **Connection Reuse** | 44/48 | **91.6%** |
| **Command Cache** | 40/44 | **90.9%** |

**Analysis:**
- 44 connection hits = 40 tests reused existing connections + 4 new connections
- 4 connection misses = 4 initial connections (one per device)
- 40 command hits = Cached command outputs reused
- 4 command misses = 4 unique commands executed

**Savings from Connection Reuse:**
```
Without reuse: 44 tests × 16.6s = 730.4s
With reuse: (4 × 16.6s) + (40 × 5.8s) = 66.4s + 232s = 298.4s
Actual: 170s (broker startup time)

Difference: 298.4s - 170s = 128.4s
This 128s is device parallelization savings (4 devices run in parallel)
```

---

## Per-Test Component Breakdown

### First Test (16.6s total)

| Component | Estimated Time | Percentage |
|-----------|---------------|------------|
| **PyATS Process Spawn** | ~8-9s | 48-54% |
| **SSH Connection Setup** | ~5-6s | 30-36% |
| **Test Logic Execution** | ~1.5-2s | 9-12% |
| **Result Collection** | ~0.5-1s | 3-6% |

**Critical Finding:** PyATS process spawning is the PRIMARY bottleneck (8-9s per test).

### Subsequent Tests (5.8s total)

| Component | Estimated Time | Percentage |
|-----------|---------------|------------|
| **PyATS Process Spawn** | ~8-9s | **Still present!** |
| **Connection Acquisition** | ~0.5s | 9% |
| **Test Logic Execution** | ~1.5-2s | 26-34% |
| **Result Collection** | ~0.5-1s | 9-17% |
| **??? (Overlap/Parallelism)** | -4-5s | Negative? |

**Wait, this doesn't add up!** Let me recalculate...

**Revised Understanding:**

The 5.8s average for subsequent tests suggests:
- PyATS process spawning is NOT 8-9s per test for subsequent tests
- OR there's significant parallelization happening
- OR the 8-9s overhead is amortized across multiple tests

**New Hypothesis:** PyATS spawns ONE subprocess per device, then runs all 11 tests sequentially within that subprocess.

**Testing this hypothesis:**
```
Per device total time: 170s ÷ 4 devices = 42.5s
First test: 16.6s
Remaining 10 tests: 42.5s - 16.6s = 25.9s
Average per subsequent test: 25.9s ÷ 10 = 2.6s

Wait, that's only 2.6s, not 5.8s...
```

**Confusion:** The individual test timings (5.8s) don't match the calculated per-device time (42.5s).

Let me recalculate from actual data...

---

## Recalculation: What's Actually Happening?

**Broker Startup Time:** 170s (2m 50s)  
**Number of Devices:** 4  
**Tests per Device:** 11

**If devices run in parallel:**
```
Per-device time = 170s (all devices complete within this window)
Per-test average = 170s ÷ 11 tests = 15.5s per test
```

**If devices run sequentially:**
```
Per-device time = 170s ÷ 4 = 42.5s
Per-test average = 42.5s ÷ 11 tests = 3.9s per test
```

**Actual measured test times:**
- First test: 16.6s average
- Second test: 5.8s average
- Estimated subsequent tests: likely 5-6s each

**Calculation:**
```
Per device: (1 × 16.6s) + (10 × 5.8s) = 16.6s + 58s = 74.6s
But actual per-device time: 42.5s

Discrepancy: 74.6s - 42.5s = 32.1s
```

**Aha!** The devices are running **IN PARALLEL**, so individual test times appear longer, but total wall-clock time is shorter.

---

## Corrected Understanding: Parallel Execution

**Architecture:**
```
4 devices run in PARALLEL (5 workers available)
Within each device: 11 tests run SEQUENTIALLY
Broker Startup time (170s) = max(device1_time, device2_time, device3_time, device4_time)
```

**Expected per-device time:**
```
Device time = (1 × 16.6s) + (10 × 5.8s) = 74.6s
```

**But actual Broker Startup time is only 170s for ALL 4 devices.**

**This means:**
```
Slowest device: 170s (possibly more tests or slower tests)
Fastest device: ~60-70s (likely completed earlier)
```

**OR:**

The test times include ALL PyATS overhead (process spawning, framework, etc.) and devices complete faster than individual test times suggest due to overlapping operations.

---

## The 8-9 Second Mystery

**From previous analysis:** We estimated 8-9s PyATS overhead per test based on 87% overhead.

**But current data shows:**
- First test: 16.6s
- Subsequent tests: 5.8s

**If there's 8-9s overhead per test:**
```
First test: 8-9s overhead + 1.5s logic + 6s SSH = 15.5-16.5s ✅ Matches!
Subsequent: 8-9s overhead + 1.5s logic = 9.5-10.5s ❌ Should be 10s, not 5.8s!
```

**Conclusion:** The 8-9s overhead is NOT per test. It's per SUBPROCESS (per device job).

**Revised Model:**
```
Per device job:
  - PyATS subprocess spawn: 8-9s (ONE TIME)
  - First test (includes SSH setup): 16.6s
  - Subsequent 10 tests: 10 × 5.8s = 58s
  - Total: 8-9s + 16.6s + 58s = 82.6-83.6s per device

But actual: 170s ÷ 4 = 42.5s per device (if sequential)
OR: 170s per slowest device (if parallel)
```

**Still doesn't match!** Let me check if tests run in parallel per device...

---

## Final Analysis: Need More Data

**What we know for certain:**
1. Total execution time: 170s (Broker Startup)
2. First test average: 16.6s
3. Second test average: 5.8s
4. Connection reuse works: 91.6% hit rate

**What we DON'T know:**
1. Are tests running in parallel within a device? (Unlikely, but possible)
2. What's the actual PyATS subprocess spawn overhead?
3. Why doesn't per-test timing add up to per-device timing?

**Next Steps:**
1. Extract per-device total execution time from logs
2. Count exact number of tests per device
3. Calculate actual per-device time budget
4. Compare to sum of individual test times

---

## Summary for Comparison with Linux

**macOS Performance (confirmed):**
- Total runtime: 174.9s
- D2D execution: 170s
- First test: 16.6s (includes SSH setup)
- Subsequent tests: 5.8s (connection reuse)
- Connection reuse: 91.6% hit rate
- API tests: 1.9s average

**Ready for Linux Python 3.12 comparison.**

---

**Document Version:** 1.0 (needs revision after understanding parallel execution model)  
**Created:** February 8, 2026  
**Status:** Awaiting Linux Python 3.12 results for comparison
