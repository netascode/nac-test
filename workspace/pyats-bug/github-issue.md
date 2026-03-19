# `step.failed(data=...)` / `step.passed(data=...)` does not persist data to results.json

## Summary

The `data` parameter passed to step result methods (`step.failed()`, `step.passed()`, etc.) is silently discarded and not persisted to `results.json`.

## Environment

- pyATS version: 25.11
- Python: 3.12

## Reproduction

```python
from pyats import aetest

class TestStepDataBug(aetest.Testcase):
    @aetest.test
    def test_step_data(self, steps):
        with steps.start("Step with data") as step:
            step.failed(
                reason="Test failure",
                data={"key": "value", "metrics": {"passed": 5, "failed": 1}}
            )
```

Run with: `pyats run testscript test.py --testbed-file empty_testbed.yaml`

## Expected

```json
"result": {
    "value": "failed",
    "reason": "Test failure",
    "data": {"key": "value", "metrics": {"passed": 5, "failed": 1}}
}
```

## Actual

```json
"result": {
    "value": "failed",
    "reason": "Test failure"
}
```

The `data` field is missing.

## Root Cause

In `pyats/aetest/steps/implementation.py`, the step methods pass `data` as a positional argument:

```python
@staticmethod
def failed(reason = None, data = None, from_exception = None):
    raise signals.AEtestStepFailedSignal(reason, data, from_exception=from_exception)
    #                                           ^^^^ 2nd positional arg
```

But `ResultSignal.__init__` in `signals.py` expects `goto` as the 2nd positional parameter:

```python
def __init__(self, reason = None, goto = None, from_exception = None, data = None):
    self.result = self.result.clone(reason = reason, data = data)
    #             ^^^^ data is 4th param, receives None; 2nd positional goes to goto
```

## Suggested Fix

Change step methods to pass `data` as a keyword argument:

```python
@staticmethod
def failed(reason = None, data = None, from_exception = None):
    raise signals.AEtestStepFailedSignal(reason, data=data, from_exception=from_exception)
    #                                           ^^^^^^^^^^ keyword argument
```

Same fix needed for: `passed()`, `skipped()`, `errored()`, `blocked()`, `aborted()`, `passx()`
