# pyATS Step Data Bug Reproduction

This directory contains a minimal reproduction case for a bug where the `data` parameter
passed to `step.failed()`, `step.passed()`, etc. is not persisted to `results.json`.

## Files

- `test_step_data_bug.py` - Test script demonstrating the bug
- `job.py` - Job file to run the test
- `empty_testbed.yaml` - Empty testbed (no devices needed)
- `results_actual.json` - Actual results.json output showing the bug (data field missing)

## How to Run

```bash
cd /path/to/pyats-bug

# Run via job file
uv run pyats run job job.py --testbed-file empty_testbed.yaml

# Or run testscript directly
uv run pyats run testscript test_step_data_bug.py --testbed-file empty_testbed.yaml
```

## Expected vs Actual

### Expected

In `results.json`, the step result should contain the `data` field:

```json
{
    "type": "Step",
    "name": "Step with data that should appear in results.json",
    "result": {
        "value": "failed",
        "reason": "Intentional failure to demonstrate bug",
        "data": {
            "verification_summary": {
                "total_checked": 10,
                "passed": 8,
                "failed": 2
            },
            "custom_field": "this should be in results.json"
        }
    }
}
```

### Actual

The `data` field is missing:

```json
{
    "type": "Step",
    "name": "Step with data that should appear in results.json",
    "result": {
        "value": "failed",
        "reason": "Intentional failure to demonstrate bug"
    }
}
```

## Root Cause

See the full bug report for details. The issue is a positional argument mismatch in
`pyats/aetest/steps/implementation.py` where `data` is passed as the second positional
argument to signal constructors, but `ResultSignal.__init__` expects `goto` as the
second positional parameter.
