# pyATS Bug Report: Step.failed()/passed() data parameter not persisted to results.json

## Summary

The `data` parameter passed to `step.failed()`, `step.passed()`, and other step result methods is not being persisted to `results.json`. The data is silently discarded due to a positional argument mismatch between `Step` methods and `ResultSignal.__init__`.

## Environment

- pyATS version: 25.11
- Python version: 3.12
- OS: macOS (also reproducible on Linux)

## Steps to Reproduce

```python
from pyats import aetest

class TestDataPersistence(aetest.Testcase):
    @aetest.test
    def test_step_data(self, steps):
        with steps.start("Test step with data") as step:
            step.failed(
                reason="Test failure",
                data={"key": "value", "verification_summary": {"passed": 5, "failed": 1}}
            )
```

## Expected Behavior

The `results.json` should contain the data in the step's result:

```json
{
    "type": "Step",
    "name": "Test step with data",
    "result": {
        "value": "failed",
        "reason": "Test failure",
        "data": {
            "key": "value",
            "verification_summary": {"passed": 5, "failed": 1}
        }
    }
}
```

## Actual Behavior

The `results.json` does NOT contain the `data` field:

```json
{
    "type": "Step",
    "name": "Test step with data",
    "result": {
        "value": "failed",
        "reason": "Test failure"
    }
}
```

## Root Cause Analysis

The bug is in `pyats/aetest/steps/implementation.py`. The `Step` class methods pass `data` as a **positional argument** to the signal constructors, but `ResultSignal.__init__` expects `goto` as the second positional parameter.

### Step.failed() implementation (steps/implementation.py, lines 712-724):

```python
@staticmethod
def failed(reason = None, data = None, from_exception = None):
    '''Step Failed
    ...
    '''
    raise signals.AEtestStepFailedSignal(reason, data, from_exception=from_exception)
    #                                           ^^^^ passed as 2nd positional arg
```

### ResultSignal.__init__ (signals.py, lines 35-37):

```python
def __init__(self, reason = None, goto = None, from_exception = None, data = None):
    self.result = self.result.clone(reason = reason, data = data)
    #                               ^^^^ 2nd positional = goto, NOT data
    #                               data is 4th parameter, receives None
```

### Call chain:

1. User calls: `step.failed(reason="msg", data={"key": "value"})`
2. `Step.failed()` receives: `reason="msg"`, `data={"key": "value"}`
3. `Step.failed()` raises: `AEtestStepFailedSignal("msg", {"key": "value"}, from_exception=None)`
4. `ResultSignal.__init__` receives: `reason="msg"`, `goto={"key": "value"}`, `from_exception=None`, `data=None`
5. Result is cloned with: `self.result.clone(reason="msg", data=None)` ← **data is lost!**

## Suggested Fix

In `pyats/aetest/steps/implementation.py`, change all step result methods to pass `data` as a **keyword argument**:

```python
@staticmethod
def failed(reason = None, data = None, from_exception = None):
    raise signals.AEtestStepFailedSignal(reason, data=data, from_exception=from_exception)
    #                                           ^^^^^^^^^ keyword argument

@staticmethod
def passed(reason = None, data = None, from_exception = None):
    raise signals.AEtestStepPassedSignal(reason, data=data, from_exception=from_exception)

# ... same for skipped, errored, blocked, aborted, passx
```

## Affected Methods

All step result methods in `Step` class have this issue:
- `Step.passed()`
- `Step.failed()`
- `Step.skipped()`
- `Step.errored()`
- `Step.blocked()`
- `Step.aborted()`
- `Step.passx()`

## Impact

- Users cannot attach structured data to step results
- The `data` parameter is documented but non-functional for steps
- Workaround requires using `runtime.reporter.client.add_extra()` instead, which attaches data to `extra` field rather than `result.data`

## Verification

The reporter serialization code correctly handles `result.data` when present. From `pyats/reporter/testsuite.py`:

```python
def TestResult_representer(dumper, data):
    mapping = {'value': data.value}
    if data.reason:
        mapping['reason'] = data.reason
    if data.data:
        mapping['data'] = data.data  # This works correctly
    return dumper.represent_mapping(YAML_MAP, mapping)
```

The bug is purely in how `Step` methods pass arguments to signals, not in the serialization layer.
