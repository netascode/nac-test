# nac-test Cold Start Performance Issue

**Issue:** https://github.com/netascode/nac-test/issues/432  
**Date:** February 8, 2026  
**Status:** 🔬 INITIAL OBSERVATION

---

## Summary

Initial nac-test execution (cold start) shows **~22 second overhead** compared to subsequent executions (warm start) due to Python import caching and dependency loading.

---

## Observed Behavior

### Linux Python 3.12 Container

| Run Type | Total Runtime | Difference |
|----------|---------------|------------|
| **Cold Start** (first run) | 5m 14.96s (314.96s) | +22.3s |
| **Warm Start** (second run) | 4m 52.7s (292.7s) | Baseline |

**Cold Start Penalty:** ~22 seconds (~7.6% overhead)

### Test Configuration
- **Platform:** Linux Python 3.12 container
- **Test Suite:** 22 PyATS tests (11 API + 11 D2D)
- **Devices:** 4 IOS-XE devices
- **Environment:** Docker container with fresh `/tmp/venv`

---

## Hypothesis: Import Caching

The cold start penalty is likely due to:

1. **Python Bytecode Compilation**
   - First run: Python compiles `.py` → `.pyc` files
   - Subsequent runs: Python loads pre-compiled `.pyc` files
   - PyATS/Genie have many dependencies (hundreds of modules)

2. **System Page Cache**
   - First run: File system reads from disk
   - Subsequent runs: Files cached in memory (page cache)

3. **Dependency Loading**
   - PyATS imports many libraries on first execution
   - Subsequent runs benefit from import caching

4. **Container Overlay Filesystem**
   - Docker overlay2 filesystem adds latency
   - First access slower than cached access

---

## Evidence

### Cold Start Log
```
File: timing_output_debug_linux312.log
Total runtime: 5 minutes 14.96 seconds (314.96s)
```

### Warm Start Log
```
File: timing_output_linux312_warm.log
Total runtime: 4 minutes 52.68 seconds (292.68s)
```

### Difference
```
314.96s - 292.68s = 22.28 seconds
```

---

## Impact

### Severity: **LOW-MEDIUM**

- **CI/CD Pipelines:** Every pipeline run experiences cold start penalty
- **Development:** Developers experience penalty after container restart
- **Production:** One-time cost per environment initialization

### Affected Users

- Users running nac-test in containers
- CI/CD environments (every build)
- Ephemeral testing environments

### Not Affected

- Long-running containers (warm cache persists)
- Native Python installations (lower overhead)
- Repeated test executions in same environment

---

## Comparison with D2D Performance Issue (#519)

This is **SEPARATE** from the D2D performance analysis:

| Issue | Problem | Overhead | Scope |
|-------|---------|----------|-------|
| **#432 (this)** | Cold start penalty | ~22s one-time | All nac-test executions |
| **#519** | Process spawning in containers | ~118s continuous | D2D tests only |

**Key Difference:**
- Cold start (#432): One-time penalty at nac-test startup
- D2D performance (#519): Continuous overhead throughout test execution

---

## Potential Solutions

### Short-Term

1. **Pre-compile Python Modules**
   ```bash
   python -m compileall /path/to/nac-test
   python -m compileall /path/to/nac-test-pyats-common
   ```
   Creates `.pyc` files before first run

2. **Persistent Container Volumes**
   - Mount Python site-packages as volume
   - Preserve `.pyc` files across container restarts

3. **Docker Image Pre-caching**
   - Build Docker image with pre-compiled bytecode
   - Run dummy nac-test execution during image build

### Long-Term

1. **Lazy Import Optimization**
   - Defer heavy imports until needed
   - Reduce initial import overhead

2. **Module Load Profiling**
   - Identify slowest imports
   - Optimize or eliminate unnecessary dependencies

3. **Alternative Package Management**
   - Use `uv` for faster package installation
   - Compiled wheels instead of source distributions

---

## Recommended Next Steps

1. **Profile Import Time**
   ```bash
   python -X importtime -c "import nac_test" 2>&1 | tee import_profile.log
   ```

2. **Measure Bytecode Compilation**
   ```bash
   # Clear cache
   find /tmp/venv -name "*.pyc" -delete
   find /tmp/venv -name "__pycache__" -type d -delete
   
   # Time first run
   time nac-test --version
   
   # Time second run
   time nac-test --version
   ```

3. **Test Pre-compilation**
   ```bash
   # Pre-compile
   python -m compileall /tmp/venv/lib/python3.12/site-packages
   
   # Measure impact
   time nac-test -d data -t templates -o results --pyats
   ```

4. **Update Issue #432**
   - Add findings from this analysis
   - Propose solutions for investigation
   - Request feedback from maintainers

---

## Files Referenced

```
/Users/oboehmer/Documents/DD/nac-test/workspace/scale/
├── timing_output_debug_linux312.log       # Cold start (5m 14.96s)
└── timing_output_linux312_warm.log        # Warm start (4m 52.7s)
```

---

## References

- **GitHub Issue:** https://github.com/netascode/nac-test/issues/432
- **Related Issue:** https://github.com/netascode/nac-test/issues/519 (D2D performance)
- **Python Import System:** https://docs.python.org/3/reference/import.html
- **Docker Overlay2 Filesystem:** https://docs.docker.com/storage/storagedriver/overlayfs-driver/

---

## Status

- **Priority:** Medium (CI/CD impact, but one-time overhead)
- **Next Action:** Profile import time to identify bottlenecks
- **Owner:** To be assigned

---

**Report Generated:** February 8, 2026  
**Analyst:** Atlas (OhMyOpenCode)
