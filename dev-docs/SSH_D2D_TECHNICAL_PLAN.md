# Technical Implementation Plan: SSH/D2D Generic Architecture Refactoring

## Executive Overview

### What Are We Building?

We are refactoring the existing SSH/Direct-to-Device (D2D) testing infrastructure to decouple it from SD-WAN-specific implementation. The goal is to extract common patterns into reusable base classes and utilities, enabling rapid adoption of D2D testing across 15+ network architectures without code duplication.

**Key Deliverables:**

- Device validation and file discovery utilities in nac-test
- BaseDeviceResolver abstract class in nac-test-pyats-common
- Refactored SDWANDeviceResolver extending the base class
- Fixed credential environment variables for SD-WAN D2D

**Scope Boundaries:**

- **In Scope:** Refactoring existing code, creating abstractions, fixing env vars
- **Out of Scope:** Adding new features, logging frameworks, monitoring, cloud deployment

### Why Are We Building This?

**Problem Statement:** The current D2D infrastructure is tightly coupled to SD-WAN, making it difficult to add D2D support for other architectures. With 15+ architectures planned, this would result in massive code duplication.

**Business Justification:**

- Current state: 1 architecture with D2D support (SD-WAN)
- Near-term need: ACI and Catalyst Center D2D support
- Long-term: 15+ architectures requiring D2D testing
- Without refactoring: 15x code duplication, maintenance nightmare

### How Will We Build This?

**Technical Approach:** Extract common patterns from SDWANDeviceResolver into a BaseDeviceResolver abstract class using the Template Method pattern. Architecture-specific resolvers will only implement schema navigation methods.

**Key Technologies:**

- Python 3.11+
- Abstract base classes for Template Method pattern
- Existing PyATS/Unicon for SSH connections (no changes)

**Success Criteria:**

- Zero code duplication in resolver logic
- New architecture implementation < 100 lines of code
- All existing SD-WAN D2D tests pass without modification
- Validation catches errors before SSH connection attempts

## Strategic Goals and Outcomes

### Primary Goals

1. **Decouple D2D Infrastructure from SD-WAN**
   - **Success Metric:** BaseDeviceResolver contains all common logic
   - **Expected Outcome:** Any architecture can implement D2D with minimal code
   - **Trade-off:** Small initial refactoring effort for massive future savings
   - **Risk:** Breaking existing SD-WAN tests during refactoring

2. **Fix Credential Environment Variables**
   - **Success Metric:** SD-WAN D2D uses IOSXE_USERNAME/IOSXE_PASSWORD
   - **Expected Outcome:** Correct separation of controller vs device credentials
   - **Trade-off:** Breaking change requiring documentation update
   - **Risk:** Users with hardcoded SDWAN_* vars will need to update

3. **Enable Rapid Architecture Adoption**
   - **Success Metric:** New resolver implementation < 100 lines
   - **Expected Outcome:** ACI/Catalyst Center D2D in days, not weeks
   - **Trade-off:** Upfront abstraction design vs iterative discovery
   - **Risk:** Abstract design might not fit all future architectures

4. **Improve Error Detection**
   - **Success Metric:** Validation catches 100% of config errors before SSH
   - **Expected Outcome:** Clear error messages for missing fields/credentials
   - **Trade-off:** Additional validation overhead (negligible)
   - **Risk:** None - purely additive improvement

## Core Design Principles

### Technical Design Principles

1. **Template Method Pattern**
   - **Definition:** Base class implements algorithm, subclasses fill in details
   - **Implementation Guidelines:**
     - Common logic in BaseDeviceResolver (loading, validation, credential injection)
     - Abstract methods for schema navigation
     - Optional hooks for customization
   - **Measurement:** Subclasses only implement 6-8 abstract methods
   - **Anti-patterns:** Duplicating logic in subclasses

2. **Fail-Fast Validation**
   - **Definition:** Validate early, fail with clear messages
   - **Implementation Guidelines:**
     - Validate device dicts before SSH attempts
     - Check environment variables at resolver init
     - Provide actionable error messages
   - **Measurement:** Zero SSH failures due to missing config
   - **Anti-patterns:** Silent failures, cryptic error messages

3. **Zero Breaking Changes**
   - **Definition:** Existing tests must work unchanged (except env vars)
   - **Implementation Guidelines:**
     - Maintain existing SDWANTestBase interface
     - Keep same data model navigation
     - Only change is credential env var names
   - **Measurement:** All existing tests pass
   - **Anti-patterns:** Unnecessary API changes

## System Architecture and Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Execution Layer                     │
│                  (Architecture Test Files)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              nac-test-pyats-common (Layer 2)                │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐  │
│  │                 BaseDeviceResolver                    │  │
│  │  (Template Method: loading, validation, credentials)  │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────▼────────────────────────────────┐ │
│  │  Architecture-Specific Resolvers (SD-WAN, ACI, etc)   │ │
│  │     (Implement: schema navigation, extraction)         │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   nac-test (Layer 1)                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Utility Functions                        │  │
│  │  - validate_device_inventory()                        │  │
│  │  - find_data_file()                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           SSHTestBase (existing, enhanced)           │  │
│  │              (calls validation utility)              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Architecture

**BaseDeviceResolver (nac-test-pyats-common)**

- **Purpose:** Template Method implementation for device resolution
- **Responsibilities:**
  - Load test inventory from YAML
  - Filter devices based on inventory
  - Inject credentials from environment
  - Build device dictionaries
- **Dependencies:** nac-test utilities, PyYAML
- **Interfaces:** get_resolved_inventory() -> list[dict]
- **Technology:** Python ABC with abstract methods

**SDWANDeviceResolver (nac-test-pyats-common)**

- **Purpose:** SD-WAN-specific schema navigation
- **Responsibilities:**
  - Navigate sites[].routers[] structure
  - Extract chassis_id, hostname, management IP
  - Return IOSXE credential env var names
- **Dependencies:** BaseDeviceResolver
- **Interfaces:** Implements 8 abstract methods
- **Technology:** Python class extending ABC

### Directory Structure

```bash
nac-test/
├── nac_test/
│   ├── pyats_core/
│   │   └── common/
│   │       └── ssh_base_test.py       # Enhanced with validation
│   └── utils/
│       ├── __init__.py                # Export new utilities
│       ├── device_validation.py       # NEW: Validation utility
│       └── file_discovery.py          # NEW: File discovery utility

nac-test-pyats-common/
├── src/nac_test_pyats_common/
│   ├── common/                        # NEW: Common base classes
│   │   ├── __init__.py                # Export BaseDeviceResolver
│   │   └── base_device_resolver.py    # NEW: Abstract base class
│   └── sdwan/
│       ├── device_resolver.py         # REFACTORED: Extends base
│       └── ssh_test_base.py           # REFACTORED: Uses new resolver
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

#### Goal: Add foundational utilities to nac-test

#### [1.1] Add Device Validation Utility

**Task: Create device_validation.py with validation logic**

- [x] Create `nac_test/utils/device_validation.py`
- [x] Define REQUIRED_DEVICE_FIELDS constant
- [x] Implement DeviceValidationError exception class
- [x] Implement validate_device_inventory() function
- [x] Add unit tests for validation scenarios
- **Time Estimate:** 4 hours
- **Dependencies:** None
- **Risk:** Low - new utility, well-defined scope

#### [1.2] Add File Discovery Utility

**Task: Create file_discovery.py for generic file traversal**

- [x] Create `nac_test/utils/file_discovery.py`
- [x] Implement find_data_file() function
- [x] Support configurable search directories
- [x] Add logging for debugging
- [x] Add unit tests for various directory structures
- **Time Estimate:** 3 hours
- **Dependencies:** None
- **Risk:** Low - simple directory traversal

#### [1.3] Update SSHTestBase with Validation

**Task: Enhance SSHTestBase.setup() to validate devices**

- [x] Import validation utility in ssh_base_test.py
- [x] Add validation call after device_info parsing
- [x] Handle DeviceValidationError with clear message
- [x] Test with intentionally bad device info
- **Time Estimate:** 2 hours
- **Dependencies:** Task 1.1
- **Risk:** Medium - modifying existing critical class

#### [1.4] Update nac-test **init** Exports

**Task: Export new utilities from package**

- [x] Update `nac_test/utils/__init__.py` with new exports
- [x] Ensure proper import paths
- [x] Verify imports work from external packages
- **Time Estimate:** 1 hour
- **Dependencies:** Tasks 1.1, 1.2
- **Risk:** Low - import configuration only

### Phase 2: Base Resolver Implementation (Week 1-2)

#### Goal: Create BaseDeviceResolver abstract class in nac-test-pyats-common

#### [2.1] Create Common Package Structure

**Task: Set up common/ directory for shared code**

- [x] Create `src/nac_test_pyats_common/common/` directory
- [x] Create `src/nac_test_pyats_common/common/__init__.py`
- [x] Configure exports for BaseDeviceResolver
- **Time Estimate:** 1 hour
- **Dependencies:** Phase 1 complete
- **Risk:** Low - new directory structure

#### [2.2] Implement BaseDeviceResolver

**Task: Create base_device_resolver.py with Template Method**

- [x] Create `src/nac_test_pyats_common/common/base_device_resolver.py`
- [x] Implement **init** with data_model and test_inventory
- [x] Implement _load_inventory() using find_data_file utility
- [x] Implement get_resolved_inventory() template method
- [x] Implement _get_devices_to_test() filtering logic
- [x] Implement _inject_credentials() from env vars
- [x] Define all abstract methods with clear docstrings
- [x] Implement build_device_dict() with default behavior
- **Time Estimate:** 8 hours
- **Dependencies:** Phase 1 utilities
- **Risk:** Medium - core abstraction design

#### [2.3] Add Unit Tests for BaseDeviceResolver

**Task: Create comprehensive tests for base class**

- [x] Create test file for base_device_resolver
- [x] Mock abstract methods for testing
- [x] Test inventory loading scenarios
- [x] Test device filtering logic
- [x] Test credential injection
- [x] Test error handling paths
- **Time Estimate:** 6 hours
- **Dependencies:** Task 2.2
- **Risk:** Low - standard testing

### Phase 3: SD-WAN Refactoring (Week 2)

#### Goal: Refactor SD-WAN resolver to use base class and fix credentials

#### [3.1] Refactor SDWANDeviceResolver

**Task: Update device_resolver.py to extend BaseDeviceResolver**

- [ ] Import BaseDeviceResolver in sdwan/device_resolver.py
- [ ] Change class to extend BaseDeviceResolver
- [ ] Remove redundant code (now in base class)
- [ ] Implement get_architecture_name() returning "sdwan"
- [ ] Implement get_schema_root_key() returning "sdwan"
- [ ] Implement navigate_to_devices() for sites[].routers[]
- [ ] Implement extract_device_id() for chassis_id
- [ ] Implement extract_hostname() for system_hostname
- [ ] Implement extract_host_ip() with CIDR handling
- [ ] Implement extract_os_type() defaulting to "iosxe"
- [ ] **CRITICAL: Implement get_credential_env_vars() returning ("IOSXE_USERNAME", "IOSXE_PASSWORD")**
- **Time Estimate:** 4 hours
- **Dependencies:** Phase 2 complete
- **Risk:** High - refactoring existing critical code

#### [3.2] Update SDWANTestBase

**Task: Simplify ssh_test_base.py to use refactored resolver**

- [ ] Update imports to use refactored SDWANDeviceResolver
- [ ] Simplify get_ssh_device_inventory() to delegate to resolver
- [ ] Remove redundant code
- [ ] Update docstrings to document credential change
- **Time Estimate:** 2 hours
- **Dependencies:** Task 3.1
- **Risk:** Medium - changing test base class

#### [3.3] Test SD-WAN Refactoring

**Task: Verify all SD-WAN D2D tests still pass**

- [ ] Run existing SD-WAN D2D tests
- [ ] Update test environment variables from SDWAN_*to IOSXE_*
- [ ] Verify device discovery works
- [ ] Verify SSH connections succeed
- [ ] Test with missing credentials for error messages
- **Time Estimate:** 4 hours
- **Dependencies:** Tasks 3.1, 3.2
- **Risk:** High - validating breaking change

#### [3.4] Update Documentation

**Task: Document credential environment variable change**

- [ ] Update README with new env var names
- [ ] Add migration note for users
- [ ] Document in code comments
- [ ] Update any CI/CD configurations
- **Time Estimate:** 2 hours
- **Dependencies:** Task 3.3
- **Risk:** Low - documentation only

### Phase 4: Integration Testing (Week 2-3)

#### Goal: Comprehensive testing of refactored system

#### [4.1] Integration Test Suite

**Task: Create integration tests for full flow**

- [ ] Test BaseDeviceResolver with mock implementation
- [ ] Test SDWANDeviceResolver end-to-end
- [ ] Test error scenarios (missing files, bad credentials)
- [ ] Test with real SD-WAN data model
- **Time Estimate:** 6 hours
- **Dependencies:** Phase 3 complete
- **Risk:** Low - testing only

#### [4.2] Performance Validation

**Task: Ensure no performance regression**

- [ ] Measure device resolution time before/after
- [ ] Profile memory usage
- [ ] Verify no additional I/O overhead
- **Time Estimate:** 2 hours
- **Dependencies:** Task 4.1
- **Risk:** Low - measurement only

#### [4.3] Documentation Updates

**Task: Update architecture documentation**

- [ ] Update PRD_AND_ARCHITECTURE.md
- [ ] Create implementation guide for new architectures
- [ ] Document credential naming conventions
- [ ] Add example for implementing new resolver
- **Time Estimate:** 4 hours
- **Dependencies:** All implementation complete
- **Risk:** Low - documentation only

## Task Breakdown Summary

### Phase Dependencies

```
Phase 1 (Core Infrastructure)
    ↓
Phase 2 (Base Resolver)
    ↓
Phase 3 (SD-WAN Refactoring)
    ↓
Phase 4 (Integration Testing)
```

### Critical Path

1. Device validation utility → SSHTestBase enhancement
2. File discovery utility → BaseDeviceResolver inventory loading
3. BaseDeviceResolver → SDWANDeviceResolver refactoring

### Effort Estimates

| Phase | Tasks | Estimated Hours | Calendar Time |
|-------|-------|----------------|---------------|
| Phase 1 | 4 | 10 hours | 2 days |
| Phase 2 | 3 | 15 hours | 2-3 days |
| Phase 3 | 4 | 12 hours | 2 days |
| Phase 4 | 3 | 12 hours | 2 days |
| **Total** | **14** | **49 hours** | **~1.5 weeks** |

## Risk Analysis and Mitigation

### Technical Risks

| Risk | Probability | Impact | Mitigation Strategy |
|------|------------|--------|-------------------|
| Breaking existing SD-WAN tests | Medium | High | Comprehensive test suite before changes, gradual refactoring |
| Abstract design doesn't fit future architectures | Low | Medium | Based on known requirements for 15+ architectures |
| Environment variable change breaks user workflows | High | Medium | Clear documentation, migration guide, deprecation period |

### Implementation Risks

| Risk | Probability | Impact | Mitigation Strategy |
|------|------------|--------|-------------------|
| Merge conflicts during refactoring | Low | Low | Work on feature branch, regular rebasing |
| Missing edge cases in validation | Medium | Low | Comprehensive unit tests, real data testing |

## Dependencies and Prerequisites

### Technical Dependencies

- Python 3.11+
- PyYAML (existing dependency)
- PyATS/Unicon (existing, no version change)

### Team Dependencies

- One developer familiar with existing SD-WAN code
- Code review from architecture team lead
- Testing support for SD-WAN D2D validation

### Organizational Dependencies

- Approval for breaking change (env var rename)
- Documentation update in user guides
- CI/CD pipeline update for new env vars

## Testing Strategy

### Test Coverage Requirements

- BaseDeviceResolver: > 90% coverage
- Validation utility: 100% coverage
- File discovery: > 95% coverage
- SDWANDeviceResolver: Maintain existing coverage

### Test Implementation Plan

- Unit tests for each new utility
- Integration tests for full resolver flow
- Mock implementations for abstract class testing
- Real SD-WAN data for end-to-end validation

## Timeline Summary

**Week 1:**

- Days 1-2: Phase 1 (Core Infrastructure)
- Days 3-5: Phase 2 (Base Resolver)

**Week 2:**

- Days 1-2: Phase 3 (SD-WAN Refactoring)
- Days 3-4: Phase 4 (Integration Testing)
- Day 5: Documentation and cleanup

**Total Duration:** 10 working days (~2 weeks)

## Implementation Readiness Checklist

- [ ] PRD reviewed and approved
- [ ] Development environment ready
- [ ] Access to SD-WAN test data
- [ ] Test environment with IOSXE credentials
- [ ] CI/CD pipeline access for env var updates
- [ ] Documentation templates prepared
- [ ] Code review process established

## Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Code duplication eliminated | 100% | Code analysis |
| New resolver implementation size | < 100 lines | Line count |
| SD-WAN test pass rate | 100% | CI pipeline |
| Validation error detection | 100% | Unit tests |
| Performance impact | < 5% overhead | Profiling |

## Notes

This is a focused refactoring effort, not a redesign. The goal is to extract existing patterns into reusable components while maintaining full backward compatibility (except for the necessary credential env var fix). No new features, monitoring, or architectural changes beyond what's specified in the PRD.

---

*Document Version: 1.0*
*Date: December 2024*
*Status: Ready for Implementation*
