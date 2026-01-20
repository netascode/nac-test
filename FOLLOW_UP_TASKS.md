# Follow-Up Tasks

Tasks identified during merge conflict resolution that should be addressed after the merge is complete.

---

## 1. Refactor DEBUG_MODE to Core Constants

**Priority:** Medium
**Context:** Identified during v1.2-beta → v1.1-beta merge

### Problem

The pattern `os.environ.get("NAC_TEST_DEBUG", "").lower() == "true"` is repeated in multiple files:

- `nac_test/cli/main.py:24`
- `nac_test/pyats_core/reporting/batching_reporter.py:645`
- `nac_test/pyats_core/reporting/batching_reporter.py:958`
- `nac_test/combined_orchestrator.py` (newly added)

### Solution

Add a single constant to `nac_test/core/constants.py`:

```python
# Debug mode - enables progressive disclosure of error details
# Set NAC_TEST_DEBUG=true for developer-level error context
DEBUG_MODE = os.environ.get("NAC_TEST_DEBUG", "").lower() == "true"
```

Then refactor all usages to:

```python
from nac_test.core.constants import DEBUG_MODE
```

### Benefits

- Single source of truth
- Evaluated once at import time
- Easy to find all debug-dependent behavior
- Self-documenting constant name

---
