# Technical Implementation Plan: Auto-detect CONTROLLER_TYPE from Environment Variables

## Overview

**Goal**: Eliminate the CONTROLLER_TYPE environment variable by auto-detecting architecture from controller credentials.

**Key deliverables**:

- Auto-detection function that determines architecture from credential environment variables
- Integration into PyATS and Combined orchestrators
- Comprehensive error messages for ambiguous/missing credentials
- Full test coverage for all detection scenarios

**Scope**:

- **In Scope**: Detection logic, orchestrator integration, error handling, all 6 architectures
- **Out of Scope**: Credential validation, mixed-architecture testing, data model detection

**Breaking Change**: This is a breaking change. NO backward compatibility or fallbacks.

---

## Table of Contents

1. [Overview](#overview)
2. [Controller Credentials for D2D Tests](#controller-credentials-for-d2d-tests)
3. [Directory Structure](#directory-structure)
4. [Implementation Phases](#implementation-phases)
5. [Testing Strategy](#testing-strategy)
6. [Documentation Requirements](#documentation-requirements)

---

## Controller Credentials for D2D Tests

### Dual Purpose of Controller Credentials

Controller credentials (URL, USERNAME, PASSWORD) serve **two distinct purposes**:

1. **Architecture Detection** (always required)
2. **Controller Connection** (API tests only)

### Why Controller Credentials Are Required for D2D Tests

**Problem**: Device credentials alone are ambiguous.

Example: `IOSXE_USERNAME` and `IOSXE_PASSWORD` could be used for:

- SD-WAN edge devices (cEdge routers)
- Catalyst Center-managed devices (switches, routers)

**Without controller credentials**, the framework cannot determine which DeviceResolver to use:

- SDWANDeviceResolver? (uses SD-WAN Manager API to get device list)
- CatalystCenterDeviceResolver? (uses Catalyst Center API to get device list)

**Solution**: Controller credentials provide architecture context, even when controller is not contacted during D2D test execution.

### D2D Test Workflow

```bash
# Controller credentials required for architecture detection
export SDWAN_URL='https://sdwan.example.com'
export SDWAN_USERNAME='admin'
export SDWAN_PASSWORD='password'

# Device credentials for SSH connections
export IOSXE_USERNAME='cisco'
export IOSXE_PASSWORD='cisco123'

# Run D2D tests (tests/d2d/ directory)
nac-test -d data/ -t tests/d2d/ -o output/ --pyats
```

**What happens**:

1. Framework detects CONTROLLER_TYPE=SDWAN from controller credentials
2. Framework loads SDWANDeviceResolver for device inventory resolution
3. Tests connect to devices via SSH using IOSXE credentials
4. Controller credentials are NOT used for connection (D2D tests)

### Users Without Controller Access

For D2D-only testing without controller access, use dummy credentials for detection:

```bash
# Dummy credentials for architecture detection (not validated)
export SDWAN_URL='https://dummy.local'
export SDWAN_USERNAME='dummy'
export SDWAN_PASSWORD='dummy'

# Real device credentials for SSH connections
export IOSXE_USERNAME='cisco'
export IOSXE_PASSWORD='cisco123'
```

**Important**: The controller credentials are used ONLY for architecture detection. The framework does not validate them for D2D-only test runs.

---

## Directory Structure

```bash
nac-test/
├── nac_test/
│   ├── utils/
│   │   ├── __init__.py              # Export detection function
│   │   ├── controller.py            # NEW: Detection implementation
│   │   └── environment.py           # MODIFIED: Remove CONTROLLER_TYPE
│   ├── pyats_core/
│   │   ├── orchestrator.py          # MODIFIED: Add detection
│   │   └── common/
│   │       └── base_test.py         # MODIFIED: Use detected type
│   └── combined_orchestrator.py     # MODIFIED: Add detection
└── tests/
    └── utils/
        └── test_controller.py        # NEW: Comprehensive test suite
```

---

## Implementation Phases

### Phase 1: Core Detection Implementation

**Goal**: Implement and test the core detection logic as a standalone module

#### 1.1 Create Detection Module

**File**: `nac_test/utils/controller.py`

```python
# -*- coding: utf-8 -*-
"""Controller type auto-detection from environment variables.

This module provides automatic detection of the controller architecture
based on environment variables, eliminating the need for CONTROLLER_TYPE.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# Credential patterns for each supported architecture
CREDENTIAL_PATTERNS: dict[str, list[str]] = {
    "ACI": ["ACI_URL", "ACI_USERNAME", "ACI_PASSWORD"],
    "SDWAN": ["SDWAN_URL", "SDWAN_USERNAME", "SDWAN_PASSWORD"],
    "CC": ["CC_URL", "CC_USERNAME", "CC_PASSWORD"],
    "MERAKI": ["MERAKI_URL", "MERAKI_USERNAME", "MERAKI_PASSWORD"],
    "FMC": ["FMC_URL", "FMC_USERNAME", "FMC_PASSWORD"],
    "ISE": ["ISE_URL", "ISE_USERNAME", "ISE_PASSWORD"],
}


def detect_controller_type() -> str:
    """Auto-detect controller type from environment variables.

    Scans environment variables for complete credential sets (URL + USERNAME + PASSWORD)
    and returns the detected controller type. Raises ValueError if detection is ambiguous
    or no complete sets are found.

    Controller credentials are required for ALL tests (API and D2D) because they
    determine which architecture-specific DeviceResolver to use. For D2D tests,
    controller credentials are used ONLY for detection, not for connection.

    Returns:
        str: Detected controller type (ACI, SDWAN, CC, MERAKI, FMC, or ISE)

    Raises:
        ValueError: If multiple credential sets found or no complete sets found

    Example:
        >>> os.environ.update({
        ...     "SDWAN_URL": "https://sdwan.example.com",
        ...     "SDWAN_USERNAME": "admin",
        ...     "SDWAN_PASSWORD": "password"
        ... })
        >>> controller_type = detect_controller_type()
        >>> print(controller_type)
        SDWAN
    """
    detected_types, partial_credentials = _find_credential_sets()

    # Single complete set found - success case
    if len(detected_types) == 1:
        controller_type = detected_types[0]
        vars_used = ", ".join(CREDENTIAL_PATTERNS[controller_type])
        logger.info(f"Detected controller type: {controller_type} ({vars_used})")
        return controller_type

    # Multiple complete sets - ambiguous
    if len(detected_types) > 1:
        raise ValueError(_format_multiple_credentials_error(detected_types))

    # No complete sets found
    raise ValueError(_format_no_credentials_error(partial_credentials))


def _find_credential_sets() -> tuple[list[str], dict[str, dict[str, list[str]]]]:
    """Find complete and partial credential sets in environment.

    Returns:
        Tuple of (complete_types, partial_credentials)
        - complete_types: List of controller types with all credentials present
        - partial_credentials: Dict mapping controller type to present/missing vars
    """
    detected_types: list[str] = []
    partial_credentials: dict[str, dict[str, list[str]]] = {}

    for controller_type, required_vars in CREDENTIAL_PATTERNS.items():
        # Check each variable - treat empty/whitespace-only as not set
        present_vars = [
            var for var in required_vars
            if os.environ.get(var, "").strip()
        ]

        if len(present_vars) == len(required_vars):
            # All credentials present
            detected_types.append(controller_type)
        elif present_vars:
            # Some credentials present (partial)
            missing_vars = [
                var for var in required_vars
                if not os.environ.get(var, "").strip()
            ]
            partial_credentials[controller_type] = {
                "present": present_vars,
                "missing": missing_vars,
            }

    return detected_types, partial_credentials


def _format_multiple_credentials_error(detected_types: list[str]) -> str:
    """Format error message for multiple credential sets detected."""
    lines = [
        "Multiple controller credential sets detected.",
        "Cannot determine which architecture to use.",
        "",
        "Detected credential sets:"
    ]

    for controller_type in detected_types:
        vars_list = ", ".join(CREDENTIAL_PATTERNS[controller_type])
        lines.append(f"  • {controller_type} ({vars_list})")

    lines.extend([
        "",
        "Please provide credentials for only ONE architecture at a time."
    ])

    return "\n".join(lines)


def _format_no_credentials_error(
    partial_credentials: dict[str, dict[str, list[str]]]
) -> str:
    """Format error message when no complete credential sets found."""
    lines = ["No complete controller credential sets detected."]

    if partial_credentials:
        lines.extend(["", "Partial credentials found:"])
        for controller_type, cred_info in partial_credentials.items():
            present = ", ".join(cred_info["present"])
            missing = ", ".join(cred_info["missing"])
            lines.append(f"  • {controller_type}: found {present}")
            lines.append(f"    Missing: {missing}")

    lines.extend([
        "",
        "To use a specific architecture, set all required credentials:",
        ""
    ])

    for controller_type, vars_list in CREDENTIAL_PATTERNS.items():
        lines.append(f"For {controller_type}:")
        for var in vars_list:
            lines.append(f"  export {var}='...'")
        lines.append("")

    return "\n".join(lines)
```

**Tasks**:

- [x] Create new file `nac_test/utils/controller.py`
- [x] Export `detect_controller_type` from `nac_test/utils/__init__.py`

#### 1.2 Create Test Suite

**File**: `tests/utils/test_controller.py`

```python
"""Tests for controller type auto-detection."""

import os
import pytest

from nac_test.utils.controller import (
    CREDENTIAL_PATTERNS,
    _find_credential_sets,
    _format_multiple_credentials_error,
    _format_no_credentials_error,
    detect_controller_type,
)


class TestControllerDetection:
    """Test controller type detection from environment variables."""

    @pytest.fixture(autouse=True)
    def clean_env(self):
        """Clean environment before each test."""
        original_env = dict(os.environ)

        # Clear all credential variables
        for pattern_vars in CREDENTIAL_PATTERNS.values():
            for var in pattern_vars:
                os.environ.pop(var, None)

        yield

        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)

    @pytest.mark.parametrize("controller_type,env_vars", [
        ("ACI", {"ACI_URL": "https://apic.local", "ACI_USERNAME": "admin", "ACI_PASSWORD": "pass"}),
        ("SDWAN", {"SDWAN_URL": "https://sdwan.local", "SDWAN_USERNAME": "admin", "SDWAN_PASSWORD": "pass"}),
        ("CC", {"CC_URL": "https://cc.local", "CC_USERNAME": "admin", "CC_PASSWORD": "pass"}),
        ("MERAKI", {"MERAKI_URL": "https://meraki.local", "MERAKI_USERNAME": "admin", "MERAKI_PASSWORD": "pass"}),
        ("FMC", {"FMC_URL": "https://fmc.local", "FMC_USERNAME": "admin", "FMC_PASSWORD": "pass"}),
        ("ISE", {"ISE_URL": "https://ise.local", "ISE_USERNAME": "admin", "ISE_PASSWORD": "pass"}),
    ])
    def test_single_credential_set_detection(self, controller_type: str, env_vars: dict[str, str]) -> None:
        """Test detection with single complete credential set."""
        os.environ.update(env_vars)

        result = detect_controller_type()

        assert result == controller_type

    def test_multiple_credential_sets_error(self) -> None:
        """Test error when multiple credential sets present."""
        os.environ.update({
            "ACI_URL": "https://apic.local",
            "ACI_USERNAME": "admin",
            "ACI_PASSWORD": "pass",
            "SDWAN_URL": "https://sdwan.local",
            "SDWAN_USERNAME": "admin",
            "SDWAN_PASSWORD": "pass",
        })

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "Multiple controller credential sets detected" in error_msg
        assert "ACI" in error_msg
        assert "SDWAN" in error_msg

    def test_partial_credentials_error(self) -> None:
        """Test error with partial credentials."""
        os.environ.update({
            "SDWAN_URL": "https://sdwan.local",
            "SDWAN_USERNAME": "admin",
        })

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "Partial credentials found" in error_msg
        assert "SDWAN" in error_msg
        assert "SDWAN_PASSWORD" in error_msg

    def test_no_credentials_error(self) -> None:
        """Test error when no credentials present."""
        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "No complete controller credential sets detected" in error_msg
        assert "For ACI:" in error_msg
        assert "For SDWAN:" in error_msg

    def test_empty_string_not_treated_as_present(self) -> None:
        """Test that empty strings are not treated as present credentials."""
        os.environ.update({
            "SDWAN_URL": "https://sdwan.local",
            "SDWAN_USERNAME": "",  # Empty string
            "SDWAN_PASSWORD": "pass",
        })

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "Partial credentials found" in error_msg
        assert "SDWAN_USERNAME" in error_msg

    def test_whitespace_only_not_treated_as_present(self) -> None:
        """Test that whitespace-only values are not treated as present credentials."""
        os.environ.update({
            "SDWAN_URL": "https://sdwan.local",
            "SDWAN_USERNAME": "   ",  # Whitespace only
            "SDWAN_PASSWORD": "pass",
        })

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "Partial credentials found" in error_msg

    def test_d2d_with_dummy_controller_credentials(self) -> None:
        """Test D2D scenario with dummy controller credentials for detection."""
        # Users without controller access can use dummy credentials
        os.environ.update({
            "SDWAN_URL": "https://dummy.local",
            "SDWAN_USERNAME": "dummy",
            "SDWAN_PASSWORD": "dummy",
        })

        # Detection should succeed - credentials are not validated
        result = detect_controller_type()

        assert result == "SDWAN"


class TestHelperFunctions:
    """Test helper functions in isolation."""

    @pytest.fixture(autouse=True)
    def clean_env(self):
        """Clean environment before each test."""
        original_env = dict(os.environ)

        for pattern_vars in CREDENTIAL_PATTERNS.values():
            for var in pattern_vars:
                os.environ.pop(var, None)

        yield

        os.environ.clear()
        os.environ.update(original_env)

    def test_find_credential_sets_complete(self) -> None:
        """Test finding complete credential sets."""
        os.environ.update({
            "ACI_URL": "https://apic.local",
            "ACI_USERNAME": "admin",
            "ACI_PASSWORD": "pass",
        })

        detected, partial = _find_credential_sets()

        assert detected == ["ACI"]
        assert partial == {}

    def test_find_credential_sets_partial(self) -> None:
        """Test finding partial credential sets."""
        os.environ.update({
            "ACI_URL": "https://apic.local",
            "ACI_USERNAME": "admin",
        })

        detected, partial = _find_credential_sets()

        assert detected == []
        assert "ACI" in partial
        assert "ACI_PASSWORD" in partial["ACI"]["missing"]

    def test_format_multiple_credentials_error(self) -> None:
        """Test error message formatting for multiple credentials."""
        error_msg = _format_multiple_credentials_error(["ACI", "SDWAN"])

        assert "Multiple controller credential sets detected" in error_msg
        assert "ACI" in error_msg
        assert "SDWAN" in error_msg
        assert "only ONE architecture" in error_msg

    def test_format_no_credentials_error_with_partial(self) -> None:
        """Test error message formatting with partial credentials."""
        partial = {
            "SDWAN": {
                "present": ["SDWAN_URL"],
                "missing": ["SDWAN_USERNAME", "SDWAN_PASSWORD"],
            }
        }

        error_msg = _format_no_credentials_error(partial)

        assert "No complete controller credential sets detected" in error_msg
        assert "Partial credentials found" in error_msg
        assert "SDWAN_URL" in error_msg
        assert "SDWAN_USERNAME" in error_msg
```

**Tasks**:

- [x] Create test file `tests/utils/test_controller.py`
- [x] Run tests to verify all pass

---

### Phase 2: Orchestrator Integration

**Goal**: Integrate detection into PyATS and Combined orchestrators

#### 2.1 PyATS Orchestrator Integration

**File**: `nac_test/pyats_core/orchestrator.py`

```python
# Add import at top
from nac_test.utils.controller import detect_controller_type

class PyATSOrchestrator:
    """Orchestrates PyATS test execution with dynamic resource management."""

    def __init__(
        self,
        data_paths: list[Path],
        test_dir: Path,
        output_dir: Path,
        merged_data_filename: str,
        minimal_reports: bool = False,
    ):
        """Initialize the PyATS orchestrator with auto-detected controller type."""
        # ... existing initialization ...

        # Auto-detect controller type - NO FALLBACK
        try:
            self.controller_type = detect_controller_type()
            logger.info(f"Auto-detected controller type: {self.controller_type}")
        except ValueError as e:
            logger.error(f"Controller detection failed:\n{e}")
            raise SystemExit(1) from e

        # ... rest of initialization ...
```

**Tasks**:

- [x] Complete PyATS Orchestrator integration with `detect_controller_type`: Add import, call detection in `__init__`, store result in `self.controller_type`, remove all `CONTROLLER_TYPE` environment variable references, and update `_validate_environment()` to use the detected controller type

#### 2.2 Combined Orchestrator Integration

**File**: `nac_test/combined_orchestrator.py`

```python
# Add import at top
from nac_test.utils.controller import detect_controller_type

class CombinedOrchestrator:
    """Lightweight coordinator for sequential PyATS and Robot Framework test execution."""

    def __init__(self, ...):
        """Initialize with auto-detected controller type."""
        # ... existing initialization ...

        # Auto-detect controller type - NO FALLBACK
        try:
            self.controller_type = detect_controller_type()
            logger.info(f"Auto-detected controller type: {self.controller_type}")
        except ValueError as e:
            typer.secho(f"ERROR:\n{e}", fg=typer.colors.RED)
            raise typer.Exit(1) from e

        # ... rest of initialization ...
```

**Tasks**:

- [x] Complete Combined Orchestrator integration with `detect_controller_type`: Add import, call detection in `__init__`, store result in `self.controller_type`, and remove all `CONTROLLER_TYPE` environment variable references

#### 2.3 Base Test Class Updates

**File**: `nac_test/pyats_core/common/base_test.py`

```python
from nac_test.utils.controller import detect_controller_type

class NACTestBase(aetest.Testcase):
    """Generic base class with auto-detected controller type."""

    @aetest.setup
    def setup(self) -> None:
        """Common setup with auto-detected controller type."""
        super().setup()

        # Get controller type via detection - NO FALLBACK
        # Detection runs once per orchestrator, but tests may run directly
        self.controller_type = detect_controller_type()

        # ... rest of setup using self.controller_type ...
```

**Tasks**:

- [x] Remove `CONTROLLER_TYPE` environment variable usage
- [x] Call `detect_controller_type()` directly (no fallback to "ACI")
- [x] Update all `controller_type` references

---

### Phase 3: Cleanup and Documentation

**Goal**: Remove legacy code and update documentation

#### 3.1 Remove Legacy CONTROLLER_TYPE References

**Tasks**:

- [x] Remove all legacy CONTROLLER_TYPE references: Remove from environment.py, update terminal.py error formatters, search entire codebase for remaining references, and remove from any test files

#### 3.2 Update Documentation

**README.md updates**:

```markdown
## Environment Variables

Set credentials for your architecture (nac-test will auto-detect the type):

### For ACI/APIC
```bash
export ACI_URL='https://apic.example.com'
export ACI_USERNAME='admin'
export ACI_PASSWORD='password'
```

### For SD-WAN

```bash
export SDWAN_URL='https://sdwan.example.com'
export SDWAN_USERNAME='admin'
export SDWAN_PASSWORD='password'
```

The framework automatically detects your architecture from the credentials provided.

**Note**: Provide credentials for only ONE architecture at a time.

### D2D (Direct-to-Device) Tests

For SSH-based D2D tests, you need BOTH controller credentials (for architecture detection) AND device credentials (for SSH connections):

```bash
# Controller credentials (for architecture detection)
export SDWAN_URL='https://sdwan.example.com'
export SDWAN_USERNAME='admin'
export SDWAN_PASSWORD='password'

# Device credentials (for SSH connections)
export IOSXE_USERNAME='cisco'
export IOSXE_PASSWORD='cisco123'

# Run D2D tests
nac-test -d data/ -t tests/d2d/ -o output/ --pyats
```

**D2D Testing Without Controller Access**: If you don't have controller access, use dummy credentials for detection:

```bash
export SDWAN_URL='https://dummy.local'
export SDWAN_USERNAME='dummy'
export SDWAN_PASSWORD='dummy'
export IOSXE_USERNAME='cisco'
export IOSXE_PASSWORD='cisco123'
```

```

**Tasks**:
- [ ] Update main README.md
- [ ] Update environment variable documentation
- [ ] Add D2D credential explanation
- [ ] Document dummy credentials workaround

---

### Phase 4: Integration Testing

**Goal**: Validate end-to-end functionality

**Tasks**:
- [ ] Test ACI with real credentials
- [ ] Test SD-WAN with real credentials
- [ ] Test Catalyst Center with real credentials
- [ ] Test D2D mode with detection
- [ ] Test error scenarios (multiple credentials, partial credentials, no credentials)
- [ ] Remove CONTROLLER_TYPE from CI workflows
- [ ] Validate all CI pipelines pass

---

## Testing Strategy

### Test Coverage Requirements

- **Unit testing**: 100% coverage of detection module
- **Integration testing**: All orchestrator integration points
- **End-to-end testing**: All 6 architectures with real credentials
- **Error path testing**: All error scenarios produce correct messages

### Test Cases from PRD

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| TC1 | Single credential set (SD-WAN) | Auto-detect CONTROLLER_TYPE=SDWAN |
| TC2 | Multiple complete sets (ACI + SD-WAN) | Error listing both detected sets |
| TC3 | Partial credentials (SDWAN_URL only) | Error listing missing variables |
| TC4 | No credentials | Error listing all supported architectures |
| TC5 | D2D-only tests | Detect from controller credentials, SSH via device credentials |

### Edge Cases

- Empty string credentials (`export SDWAN_URL=""`)
- Whitespace-only credentials (`export SDWAN_URL="   "`)
- Dummy credentials for D2D testing

---

## Documentation Requirements

### User Documentation

#### Migration Guide

```markdown
# Migrating from CONTROLLER_TYPE

## What's Changed

The `CONTROLLER_TYPE` environment variable is no longer needed or supported.
The framework now auto-detects your architecture from credentials.

## Migration Steps

1. Remove `CONTROLLER_TYPE` from your environment:
   ```bash
   unset CONTROLLER_TYPE
   ```

1. Ensure you have complete credentials for ONE architecture:

   ```bash
   # Example for SD-WAN
   export SDWAN_URL='https://sdwan.example.com'
   export SDWAN_USERNAME='admin'
   export SDWAN_PASSWORD='password'
   ```

2. Run tests as usual - detection happens automatically!

## CI/CD Updates

Remove CONTROLLER_TYPE from your CI configuration files:

```yaml
# Before
env:
  CONTROLLER_TYPE: SDWAN
  SDWAN_URL: ${{ secrets.SDWAN_URL }}

# After
env:
  SDWAN_URL: ${{ secrets.SDWAN_URL }}
  SDWAN_USERNAME: ${{ secrets.SDWAN_USERNAME }}
  SDWAN_PASSWORD: ${{ secrets.SDWAN_PASSWORD }}
```

```

---

## Summary

This implementation eliminates the CONTROLLER_TYPE environment variable through automatic detection from controller credentials. Key points:

- **Breaking Change**: NO backward compatibility - remove all fallback logic
- **ValueError**: Use standard `ValueError` instead of custom exceptions
- **D2D Support**: Controller credentials required for architecture detection even in D2D tests
- **Dummy Credentials**: Users without controller access can use dummy credentials for detection
- **Empty String Handling**: Empty/whitespace-only values are treated as "not set"
