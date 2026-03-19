# Enable machine-readable results.json for custom report generation

## Problem Statement

The current pyATS integration generates HTML reports that contain rich test execution data (command outputs, API payloads, verification summaries), but the `results.json` file lacks much of this information. This makes it difficult to:

1. Generate custom reports (e.g., PDF, CSV, Slack notifications) from test results
2. Integrate with external dashboards or CI/CD systems that need structured data
3. Build alternative report formats without re-running tests

## Current State

**Data in HTML reports but NOT in results.json:**
- Command/API execution details (endpoint, method, response code, payload)
- Verification summaries per device (passed/failed counts, specific failures)
- Test procedure/criteria documentation

**results.json currently contains:**
- Test/step names and pass/fail status
- Basic timing information
- `extra` field (can hold arbitrary data, but not populated by default)

## Objective

Enrich `results.json` with structured test execution data so that:
1. Custom report generators can consume `results.json` directly
2. No dependency on parsing HTML reports
3. All relevant test data is available in machine-readable format

## Available Mechanisms (pyATS)

| Mechanism | API | Storage Location | Status |
|-----------|-----|------------------|--------|
| `extra` field | `runtime.reporter.client.add_extra(data)` | `section.extra` | ✅ Works |
| `result.data` | `step.passed(data={...})` | `result.data` | ✅ Works (after pyATS PR #890) |
| `details` | `step.add_detail("message")` | `section.details[]` | ✅ Works (strings only) |

## Proposed Approach

1. **Capture command/API executions** - Store endpoint, method, response code, truncated payload in `extra.command_executions`
2. **Capture verification summaries** - Store per-device pass/fail counts in `result.data.verification_summary`
3. **Optionally capture test metadata** - Store procedure/criteria in `extra.test_metadata`

## Dependencies

- ✅ pyATS bug #889 fixed (PR #890 pending merge) - enables `result.data` persistence

## Example Target Structure

```json
{
  "type": "Step",
  "name": "Verify device sync status",
  "extra": {
    "command_executions": [
      {
        "device": "SDWAN Manager",
        "type": "API",
        "method": "GET",
        "endpoint": "/dataservice/system/device/vedges",
        "response_code": 200,
        "duration_seconds": 0.59
      }
    ]
  },
  "result": {
    "value": "passed",
    "data": {
      "verification_summary": {
        "total_devices": 10,
        "passed": 9,
        "failed": 1,
        "failures": [{"device": "edge-01", "reason": "config out of sync"}]
      }
    }
  }
}
```

## Related Work

- pyATS issue #889 / PR #890: Fix step result data parameter persistence
- Investigation docs: `docs/results-json-enrichment-summary.md`
