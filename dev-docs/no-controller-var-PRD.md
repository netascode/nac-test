# PRD: Auto-detect CONTROLLER_TYPE from Environment Variables

**Issue**: [#429](https://github.com/netascode/nac-test/issues/429)
**Status**: Draft
**Priority**: High
**Target Version**: 1.1.0 or 1.2.0

---

## Problem Statement

Users must explicitly set `CONTROLLER_TYPE` environment variable even when architecture-specific credentials are already provided. This creates unnecessary friction and confusion during framework adoption.

**Current Experience**:

```bash
# User provides SD-WAN credentials
export SDWAN_URL='https://sdwan.example.com'
export SDWAN_USERNAME='admin'
export SDWAN_PASSWORD='password'

# Run nac-test
nac-test -d data/ -t tests/ -o output/ --pyats

# ERROR: Missing required environment variables: ACI_URL, ACI_USERNAME, ACI_PASSWORD
# Framework defaults to ACI because CONTROLLER_TYPE wasn't set
```

**Expected Experience**:

```bash
# User provides SD-WAN credentials
export SDWAN_URL='https://sdwan.example.com'
export SDWAN_USERNAME='admin'
export SDWAN_PASSWORD='password'

# Run nac-test
nac-test -d data/ -t tests/ -o output/ --pyats

# SUCCESS: Auto-detected CONTROLLER_TYPE=SDWAN from environment variables
```

---

## Goals

1. **Eliminate CONTROLLER_TYPE entirely** - Remove the environment variable requirement
2. **Auto-detect from credentials** - Determine architecture from provided credential set
3. **Fail fast with clear errors** - Ambiguous situations produce helpful error messages
4. **Support all architectures** - ACI, SD-WAN, Catalyst Center, Meraki, FMC, ISE

---

## Non-Goals

- Auto-detect from data model files (too complex, error-prone)
- Support mixed-architecture testing in single run (out of scope)
- Credential validation beyond presence check (handled elsewhere)

---

## Functional Requirements

### FR1: Auto-detection Logic

**When CONTROLLER_TYPE is NOT set**, detect from environment variables:

| Architecture | Required Variables | Detected As |
|-------------|-------------------|-------------|
| ACI (APIC) | `ACI_URL` + `ACI_USERNAME` + `ACI_PASSWORD` | `CONTROLLER_TYPE=ACI` |
| SD-WAN | `SDWAN_URL` + `SDWAN_USERNAME` + `SDWAN_PASSWORD` | `CONTROLLER_TYPE=SDWAN` |
| Catalyst Center | `CC_URL` + `CC_USERNAME` + `CC_PASSWORD` | `CONTROLLER_TYPE=CC` |
| Meraki | `MERAKI_URL` + `MERAKI_USERNAME` + `MERAKI_PASSWORD` | `CONTROLLER_TYPE=MERAKI` |
| FMC | `FMC_URL` + `FMC_USERNAME` + `FMC_PASSWORD` | `CONTROLLER_TYPE=FMC` |
| ISE | `ISE_URL` + `ISE_USERNAME` + `ISE_PASSWORD` | `CONTROLLER_TYPE=ISE` |

**Detection requires ALL three variables** (URL + USERNAME + PASSWORD) for a given architecture.

### FR2: Detection Rules

1. **Single credential set** - Auto-detect from the one complete set found
2. **Multiple credential sets** - ERROR with clear message
3. **No credential sets** - ERROR with helpful message listing all supported architectures

### FR3: Error Messages

**Multiple credential sets detected**:

```
ERROR: Multiple controller credential sets detected.
Cannot determine which architecture to use.

Detected credential sets:
  • ACI (ACI_URL, ACI_USERNAME, ACI_PASSWORD)
  • SDWAN (SDWAN_URL, SDWAN_USERNAME, SDWAN_PASSWORD)

Please provide credentials for only ONE architecture at a time.
```

**No complete credential sets**:

```
ERROR: No complete controller credential sets detected.

Partial credentials found:
  • SDWAN_URL (missing: SDWAN_USERNAME, SDWAN_PASSWORD)

To use SD-WAN, set all required credentials:
  export SDWAN_URL='https://sdwan.example.com'
  export SDWAN_USERNAME='admin'
  export SDWAN_PASSWORD='password'
```

### FR4: Logging

When auto-detection succeeds:

```
[INFO] Detected controller type: SDWAN (SDWAN_URL, SDWAN_USERNAME, SDWAN_PASSWORD)
```

---

## Controller Credentials for D2D Tests

### Dual Purpose of Controller Credentials

Controller credentials (URL, USERNAME, PASSWORD) serve **two distinct purposes**:

1. **Architecture Detection** (always required)
2. **Controller Connection** (API tests only)

### D2D Test Workflow

For Direct-to-Device (D2D) tests that bypass the controller:

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

### Why Controller Credentials Are Required for D2D

**Problem**: Device credentials alone are ambiguous.

Example: `IOSXE_USERNAME` and `IOSXE_PASSWORD` could be used for:

- SD-WAN edge devices (cEdge routers)
- Catalyst Center-managed devices (switches, routers)

**Without controller credentials**, the framework cannot determine which DeviceResolver to use:

- SDWANDeviceResolver? (uses SD-WAN Manager API to get device list)
- CatalystCenterDeviceResolver? (uses Catalyst Center API to get device list)

**Solution**: Controller credentials provide architecture context, even when controller is not contacted during test execution.

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

## Technical Design

### Detection Function

```python
def detect_controller_type() -> str:
    """
    Auto-detect controller type from environment variables.

    Returns:
        str: Detected controller type (ACI, SDWAN, CC, etc.)

    Raises:
        ValueError: If multiple credential sets found or none found
    """
    # Define credential patterns
    credential_patterns = {
        "ACI": ["ACI_URL", "ACI_USERNAME", "ACI_PASSWORD"],
        "SDWAN": ["SDWAN_URL", "SDWAN_USERNAME", "SDWAN_PASSWORD"],
        "CC": ["CC_URL", "CC_USERNAME", "CC_PASSWORD"],
        "MERAKI": ["MERAKI_URL", "MERAKI_USERNAME", "MERAKI_PASSWORD"],
        "FMC": ["FMC_URL", "FMC_USERNAME", "FMC_PASSWORD"],
        "ISE": ["ISE_URL", "ISE_USERNAME", "ISE_PASSWORD"],
    }

    # Detect complete credential sets
    detected_types = []
    partial_credentials = {}

    for controller_type, required_vars in credential_patterns.items():
        present_vars = [var for var in required_vars if os.environ.get(var)]

        if len(present_vars) == len(required_vars):
            # All credentials present
            detected_types.append(controller_type)
        elif present_vars:
            # Some credentials present (partial)
            missing_vars = [var for var in required_vars if var not in present_vars]
            partial_credentials[controller_type] = {
                "present": present_vars,
                "missing": missing_vars,
            }

    # Evaluate results
    if len(detected_types) == 1:
        detected = detected_types[0]
        vars_used = credential_patterns[detected]
        logger.info(
            f"Detected controller type: {detected} ({', '.join(vars_used)})"
        )
        return detected

    if len(detected_types) > 1:
        raise ValueError(_format_multiple_credentials_error(detected_types, credential_patterns))

    # No complete sets found
    raise ValueError(_format_no_credentials_error(partial_credentials, credential_patterns))
```

### Integration Points

**File**: `nac_test/pyats_core/orchestrator.py`

- Add detection at orchestrator initialization
- Call before credential validation

**File**: `nac_test/combined_orchestrator.py`

- Add detection for combined runs
- Consistent behavior with PyATS-only mode

**File**: `nac_test/cli/main.py` (optional)

- Could add `--detect-controller` flag for verbose mode
- Show detection result without running tests

---

## Test Cases

### TC1: Single Credential Set (SD-WAN)

```bash
export SDWAN_URL='https://sdwan.example.com'
export SDWAN_USERNAME='admin'
export SDWAN_PASSWORD='password'
# No CONTROLLER_TYPE set
```

**Expected**: Auto-detect CONTROLLER_TYPE=SDWAN, run tests successfully

### TC2: Multiple Complete Sets

```bash
export ACI_URL='https://apic.example.com'
export ACI_USERNAME='admin'
export ACI_PASSWORD='password'
export SDWAN_URL='https://sdwan.example.com'
export SDWAN_USERNAME='admin'
export SDWAN_PASSWORD='password'
```

**Expected**: Error with message listing both detected sets

### TC3: Partial Credentials

```bash
export SDWAN_URL='https://sdwan.example.com'
# Missing SDWAN_USERNAME and SDWAN_PASSWORD
```

**Expected**: Error listing partial credentials and missing variables

### TC4: No Credentials

```bash
# No credentials set
```

**Expected**: Error listing all supported architectures and required variables

### TC5: D2D-Only Tests

```bash
# Controller credentials for architecture detection
export SDWAN_URL='https://sdwan.example.com'
export SDWAN_USERNAME='admin'
export SDWAN_PASSWORD='password'

# Device credentials for SSH connections
export IOSXE_USERNAME='cisco'
export IOSXE_PASSWORD='cisco123'

# Run D2D tests only
nac-test -d data/ -t tests/d2d/ -o output/ --pyats
```

**Expected**: Auto-detect CONTROLLER_TYPE=SDWAN, load SDWANDeviceResolver, connect to devices via SSH using IOSXE credentials. Controller credentials used only for detection, not connection.

---

## User Impact

### Breaking Change

**Existing users** (with CONTROLLER_TYPE set):

- ❌ CONTROLLER_TYPE environment variable no longer supported
- ✅ Simply remove CONTROLLER_TYPE from scripts/configs
- ✅ Credential-based detection works automatically

**All users**:

- ✅ One less environment variable to remember
- ✅ More intuitive setup experience
- ✅ Clear error messages guide configuration

### Documentation Updates

**README.md**:

```markdown
## Environment Variables

Set credentials for your architecture:

```bash
# For SD-WAN API Tests
export SDWAN_URL='https://sdwan.example.com'
export SDWAN_USERNAME='admin'
export SDWAN_PASSWORD='password'

# For ACI API Tests
export ACI_URL='https://apic.example.com'
export ACI_USERNAME='admin'
export ACI_PASSWORD='password'

# For Catalyst Center API Tests
export CC_URL='https://cc.example.com'
export CC_USERNAME='admin'
export CC_PASSWORD='password'
```

nac-test automatically detects the controller type from the credentials you provide.

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

The controller credentials are used ONLY for architecture detection. The framework determines which DeviceResolver to use (SDWANDeviceResolver, CatalystCenterDeviceResolver, etc.) based on the controller type. Tests connect directly to devices via SSH using the device credentials.

**D2D Testing Without Controller Access**: If you don't have controller access, use dummy credentials for detection:

```bash
export SDWAN_URL='https://dummy.local'
export SDWAN_USERNAME='dummy'
export SDWAN_PASSWORD='dummy'
export IOSXE_USERNAME='cisco'
export IOSXE_PASSWORD='cisco123'
```

```

---

## Implementation Phases

### Phase 1: Core Detection (MVP)
- Implement detection function
- Integrate into PyATS orchestrator
- Add unit tests for detection logic
- Update error messages

### Phase 2: Combined Mode Support
- Integrate into combined orchestrator
- Handle Robot Framework-only mode (no detection needed)
- End-to-end testing

### Phase 3: Polish
- Verbose logging improvements
- Documentation updates
- User-facing examples

---

## Success Metrics

- ✅ Zero support tickets asking "why do I need CONTROLLER_TYPE?"
- ✅ Reduced time-to-first-successful-run for new users
- ✅ Simpler CI/CD pipeline configurations
- ✅ Positive user feedback on adoption friction reduction

---

## Resolved Questions

1. **Should detection work for D2D-only tests?**
   - **Decision**: YES - Controller credentials are required for ALL tests (API and D2D)
   - Controller credentials serve dual purpose: architecture detection (always) and controller connection (API tests only)
   - For D2D tests, controller credentials determine which DeviceResolver to use (SDWANDeviceResolver vs CatalystCenterDeviceResolver)
   - Device credentials (IOSXE_USERNAME/PASSWORD) are ambiguous without architecture context
   - Users without controller access can use dummy credentials for detection

2. **Should partial credentials trigger a warning or error?**
   - **Decision**: Error with helpful message listing missing variables
   - Fail fast to prevent confusion

---

## References

- Issue: https://github.com/netascode/nac-test/issues/429
- Related: Issue #408 (test structure flexibility)
- Related: Issue #417 (api/d2d structure flexibility)
