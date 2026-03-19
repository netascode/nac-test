# Results.json Enrichment Investigation - Work Summary

## Objective

Investigate how to enrich pyATS `results.json` with command/API execution data and test metadata, enabling the HTML report generator to access structured data directly from results.json.

## Constraints

- Do not modify the report generation system
- Do not change the JSONL mechanism
- Implement purely within pyATS test cases

---

## Phase 1: Gap Analysis

### Findings

**Data present in HTML report but NOT in results.json:**
- Command execution details (API payloads, responses, timing)
- Test procedure/criteria documentation
- Detailed verification summaries per device

**results.json structure supports:**
- `extra` field at section/step level for arbitrary data
- `result.data` field for data attached to pass/fail results
- `details` field for string messages

### pyATS Mechanisms Identified

| Mechanism | API | Storage Location | Status |
|-----------|-----|------------------|--------|
| `extra` field | `runtime.reporter.client.add_extra(data)` | `section.extra` | ✅ Works |
| `result.data` | `step.passed(data={...})` / `step.failed(reason, data={...})` | `result.data` | ❌ Bug (see below) |
| `details` | `step.add_detail("message")` | `section.details[]` | ✅ Works (strings only) |

---

## Phase 2: Implementation

### Files Created

#### 1. Enriched Test File
**Path:** `/Users/oboehmer/Documents/DD/nac-test/workspace/sdwan/api-tests/tests/verify_sdwan_sync_enriched.py`

This is a copy of `verify_sdwan_sync.py` with enrichment additions:

```python
# Added to test method:
def _add_test_metadata_to_extra(self) -> None:
    """Add test documentation to results.json extra field."""
    test_metadata = {
        "title": "...",
        "description_html": "...",
        "setup_html": "...",
        "procedure_html": "...",
        "criteria_html": "...",
    }
    runtime.reporter.client.add_extra({"test_metadata": test_metadata})

def _add_command_execution_to_extra(self, ...) -> None:
    """Add API execution details to results.json extra field."""
    execution_record = {
        "device_name": "SDWAN Manager",
        "command_type": "API",
        "method": "GET",
        "endpoint": "/dataservice/system/device/vedges",
        "response_code": 200,
        "response_data": {...},  # truncated
        "duration_seconds": 0.59,
    }
    runtime.reporter.client.add_extra({"command_executions": [execution_record]})
```

### Files Modified

#### 2. Base Test Class
**Path:** `/Users/oboehmer/Documents/DD/nac-test/nac_test/pyats_core/common/base_test.py`

**Modified method:** `set_step_status()` (lines 1813-1854)

```python
def set_step_status(self, step: Any, result: VerificationResult) -> None:
    """Set PyATS step status based on verification result.

    Optionally attaches structured data (e.g., verification_summary) to
    result.data in results.json when present in the result dict.
    """
    status = result.get("status", "UNKNOWN")
    reason = result.get("reason", "Unknown reason")

    result_as_dict: dict[str, Any] = dict(result)
    step_data: dict[str, Any] | None = None

    # Extract 'data' key if present
    if "data" in result_as_dict and isinstance(result_as_dict["data"], dict):
        step_data = result_as_dict["data"]

    # Extract 'verification_summary' and add to step_data
    if "verification_summary" in result_as_dict:
        if step_data is None:
            step_data = {}
        step_data["verification_summary"] = result_as_dict["verification_summary"]

    # Pass data to step result methods
    if status == "PASSED" or status == ResultStatus.PASSED:
        if step_data:
            step.passed(data=step_data)
        else:
            step.passed()
    elif status == "FAILED" or status == ResultStatus.FAILED:
        if step_data:
            step.failed(reason, data=step_data)
        else:
            step.failed(reason)
    # ... etc
```

---

## Phase 3: Testing

### Test Execution

```bash
cd /Users/oboehmer/Documents/DD/nac-test
source .venv/bin/activate

# Set environment variables
export SDWAN_URL=https://10.62.190.146
export SDWAN_USERNAME=admin
export SDWAN_PASSWORD=<password>

# Run the test
nac-test -d workspace/sdwan/api-tests/data \
         -t workspace/sdwan/api-tests/tests \
         -o /tmp/output6 --pyats
```

### Test Results (output6)

**Results file:** `/tmp/output6/pyats_results/api/results.json`

| Feature | Expected | Actual | Status |
|---------|----------|--------|--------|
| `extra.test_metadata` | Present | Present | ✅ Pass |
| `extra.command_executions` | Present | Present | ✅ Pass |
| `result.data.verification_summary` | Present | **Missing** | ❌ Fail |

### Verification Script Output

```
=== Task 2: verify_sdwan_sync_enriched ===
Testscript: .../verify_sdwan_sync_enriched.py
  TestSection: test_edge_config_sync
  Extra keys: ['test_metadata', 'command_executions']  ← SUCCESS
    Step: SDWAN Edge Configuration Sync Status Verification
    Result keys: ['value', 'reason']  ← MISSING 'data' key!
```

---

## Phase 4: Bug Discovery

### pyATS Bug: `step.failed(data=...)` Does Not Persist Data

**Root Cause:** Positional argument mismatch in pyATS source code.

**Location:** `pyats/aetest/steps/implementation.py`

```python
# Step.failed() passes data as 2nd positional argument:
@staticmethod
def failed(reason = None, data = None, from_exception = None):
    raise signals.AEtestStepFailedSignal(reason, data, from_exception=from_exception)
    #                                           ^^^^ 2nd positional

# But ResultSignal.__init__ expects 'goto' as 2nd positional:
def __init__(self, reason = None, goto = None, from_exception = None, data = None):
    self.result = self.result.clone(reason = reason, data = data)
    #                                        ^^^^ 4th param, receives None
```

**Result:** The `data` dict is assigned to `goto` parameter and discarded. The actual `data` parameter receives `None`.

**Bug report created:** `/Users/oboehmer/Documents/DD/nac-test/docs/pyats-result-data-bug.md`

---

## Recommendations

### Immediate Workaround

Since `result.data` doesn't work due to the pyATS bug, use the `extra` field for all enrichment data:

```python
# Instead of:
step.failed(reason, data={"verification_summary": summary})

# Use:
runtime.reporter.client.add_extra({"verification_summary": summary})
step.failed(reason)
```

### Implementation Options

1. **Option A: Use `extra` field exclusively**
   - Move `verification_summary` to `extra` field
   - Proven to work
   - No pyATS changes required

2. **Option B: Wait for pyATS fix**
   - Report bug to Cisco pyATS team
   - Wait for fix in future pyATS release
   - Then use `result.data` as intended

3. **Option C: Monkey-patch pyATS**
   - Override `Step.failed()` etc. at runtime
   - Risk: may break with pyATS updates

### Recommended Approach

**Use Option A** (extra field) for now, and **report the bug** to Cisco. When pyATS is fixed, consider migrating to `result.data` if the semantics are better for your use case.

---

## File References

### Created Files
- `/Users/oboehmer/Documents/DD/nac-test/workspace/sdwan/api-tests/tests/verify_sdwan_sync_enriched.py`
- `/Users/oboehmer/Documents/DD/nac-test/docs/pyats-result-data-bug.md`
- `/Users/oboehmer/Documents/DD/nac-test/docs/results-json-enrichment-summary.md` (this file)

### Modified Files
- `/Users/oboehmer/Documents/DD/nac-test/nac_test/pyats_core/common/base_test.py` (lines 1813-1854)

### Test Output
- `/tmp/output6/pyats_results/api/results.json`

### pyATS Source References (for bug investigation)
- `pyats/aetest/steps/implementation.py` - Step.passed(), Step.failed() methods
- `pyats/aetest/signals.py` - ResultSignal.__init__()
- `pyats/reporter/testsuite.py` - TestResult_representer (serialization)
- `pyats/results/result.py` - TestResult.clone()

---

## Next Steps

1. [ ] Report pyATS bug to Cisco (use `pyats-result-data-bug.md`)
2. [ ] Modify enriched test to use `extra` field for `verification_summary`
3. [ ] Test the workaround
4. [ ] Decide on final implementation approach
5. [ ] Update report generator to read from `extra` field (if needed)
