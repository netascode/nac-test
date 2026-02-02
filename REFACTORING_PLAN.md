# Subprocess Refactoring Plan

## Phase 1: Extract SubprocessHttpClient (nac-test) - REVISED

### Task 1.1: Create http package structure
- [x] Create `nac_test/pyats_core/http/` directory
- [x] Create `nac_test/pyats_core/http/__init__.py` with re-exports

### Task 1.2: Extract SubprocessResponse and SubprocessHttpClient (atomic operation)
- [x] Create `nac_test/pyats_core/http/subprocess_client.py` containing:
  - SubprocessResponse dataclass
  - SubprocessHttpClient class
  - HTTP status code constants (all in one file since they're tightly coupled)

### Task 1.3: Update connection_pool.py
- [x] Remove extracted SubprocessResponse dataclass, SubprocessHttpClient class, and HTTP status constants
- [x] Update imports to use new http package: `from nac_test.pyats_core.http import SubprocessResponse, SubprocessHttpClient`
- [x] Keep ConnectionPool and get_fork_safe_client()
- [x] NO backward compatibility re-exports - update all imports directly

### Task 1.4: Update test imports
- [x] Update `tests/pyats_core/common/test_subprocess_http_client.py` to import from `nac_test.pyats_core.http`

### Task 1.5: Verify Phase 1
- [x] Run all tests to ensure extraction didn't break anything

## Phase 2: Create SubprocessAuthExecutor (nac-test)

### Task 2.1: Create subprocess_auth.py
- [x] Create `nac_test/pyats_core/common/subprocess_auth.py`
- [x] Implement SubprocessAuthExecutor class with execute() method
- [x] Include temp file handling, os.system execution, cleanup

### Task 2.2: Add unit tests for SubprocessAuthExecutor
- [ ] Create tests for the new executor

## Phase 3: Refactor Auth Modules (nac-test-pyats-common)

### Task 3.1: Refactor ACI auth module
- [x] Update `aci/auth.py` to use SubprocessAuthExecutor
- [x] Keep only APIC-specific auth script template

### Task 3.2: Refactor SDWAN auth module
- [x] Update `sdwan/auth.py` to use SubprocessAuthExecutor
- [x] Keep only SDWAN-specific auth script template

### Task 3.3: Refactor Catalyst Center auth module
- [x] Update `catc/auth.py` to use SubprocessAuthExecutor
- [x] Keep only CatC-specific auth script template

### Task 3.4: Final Validation
- [x] Run all tests in both repositories
- [x] Verify no regressions
