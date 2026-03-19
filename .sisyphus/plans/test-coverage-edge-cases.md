# Test Coverage: Edge Cases and Error Scenarios

## TL;DR

> **Quick Summary**: Add comprehensive test coverage for edge cases and error scenarios in the `feat/470-combined-dashboard` branch, focusing on subprocess crash handling, malformed input recovery, and failure modes that could cause silent failures or unexpected behavior.
> 
> **Deliverables**:
> - New test file: `tests/unit/pyats_core/execution/test_subprocess_runner.py` (HIGH priority - zero existing coverage)
> - New test file: `tests/unit/robot/test_pabot_error_handling.py` (MEDIUM priority)
> - Extended tests in: `tests/unit/robot/test_orchestrator.py` (edge cases)
> - Extended tests in: `tests/unit/robot/test_robot_output_parser.py` (edge cases)
> - Extended tests in: `tests/unit/core/test_combined_generator.py` (partial failure scenarios)
> 
> **Estimated Effort**: Medium-Large (12-16 test functions across 5 files)
> **Parallel Execution**: YES - 2 waves (independent test files can be written in parallel)
> **Critical Path**: Task 0 (baseline) -> Task 1 (subprocess_runner) -> Task 7 (coverage comparison)
> 
> **Coverage Tracking**:
> - Task 0: Capture baseline coverage before adding tests
> - Task 7: Compare final coverage to baseline and report improvement

---

## Context

### Original Request
Increase test coverage for edge cases and error scenarios in the `feat/470-combined-dashboard` branch before merging into `release/pyats-integration-v1.1-beta`. Focus on subprocess crash handling, error paths, and scenarios that could lead to failures or unexpected behavior.

### Interview Summary
**Key Discussions**:
- Happy path tests are already covered (user confirmed)
- Need both unit tests and integration tests
- Special attention to subprocess handling (PyATS via `pyats run`, Robot via in-process pabot)
- Must use `uv run pytest ...` (never `python` or `pytest` directly)
- No commits without explicit user approval

**Research Findings**:
- `subprocess_runner.py` has ZERO existing test coverage - highest risk
- 11 specific error scenarios identified as untested
- Existing test patterns use pytest with pytest-mock, unittest.mock, and MonkeyPatch
- Async code testing: **Note** - `pytest-asyncio` is NOT currently installed in this repo. Async tests should use `asyncio.run()` wrappers in standard pytest tests, OR add `pytest-asyncio` to dev dependencies if preferred. All async tests in Task 1 can be written as sync tests using `asyncio.run(async_function())`.

### Metis Review
**Identified Gaps** (addressed in this plan):
- No tests for subprocess spawn failures (OSError, FileNotFoundError)
- No tests for archive file existence verification
- No tests for `LimitOverrunError` handling
- Missing acceptance criteria for expected return values and log messages
- No tests for symlink collision when target is a directory (not file)

**Guardrails Applied**:
- Tests MUST mock `asyncio.create_subprocess_exec` - no actual subprocess spawning
- Tests MUST use `pytest.raises(ExceptionType, match="...")` for exception assertions
- Tests MUST use `caplog` fixture to assert log messages for error paths
- No bug fixes in same PR - test existing behavior only

---

## Work Objectives

### Core Objective
Add unit tests for 11 identified error scenarios, prioritizing `subprocess_runner.py` which has zero coverage and highest production risk.

### Concrete Deliverables
- `tests/unit/pyats_core/execution/test_subprocess_runner.py` - NEW file with 8+ test functions
- `tests/unit/robot/test_pabot_error_handling.py` - NEW file with 2+ test functions
- Extended `tests/unit/robot/test_orchestrator.py` - 2+ additional test functions
- Extended `tests/unit/robot/test_robot_output_parser.py` - 1+ additional test function
- Extended `tests/unit/core/test_combined_generator.py` - 2+ additional test functions

### Definition of Done
- [x] Baseline coverage report captured (Task 0)
- [x] `uv run pytest tests/unit/pyats_core/execution/test_subprocess_runner.py -v` passes with 8+ tests
- [x] `uv run pytest tests/unit/robot/test_pabot_error_handling.py -v` passes with 2+ tests
- [x] `uv run pytest tests/unit/robot/test_orchestrator.py -v` passes (including new edge case tests)
- [x] `uv run pytest tests/unit/ -v` passes with no regressions
- [x] All new tests follow existing project patterns (fixtures, mocking, naming)
- [x] Final coverage report shows improvement over baseline (Task 7)

### Must Have
- Tests for subprocess crash handling (return code > 1)
- Tests for archive file not created scenario
- Tests for `LimitOverrunError` handling
- Tests for malformed NAC_PROGRESS JSON
- Tests for buffer drain timeout
- Tests use `uv run pytest ...` (never `python` or `pytest` directly)

### Must NOT Have (Guardrails)
- **NO actual subprocess spawning** - mock `asyncio.create_subprocess_exec`
- **NO testing PyATS functionality** - only test `SubprocessRunner` behavior
- **NO bug fixes** in the same PR (separate fixes from tests)
- **NO tests for modules outside the 9-file scope**
- **NO commits without explicit user approval**
- **NO acceptance criteria requiring human verification** - all must be agent-executable

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.
> The executing agent will run `uv run pytest ...` commands and verify output.

### Test Decision
- **Infrastructure exists**: YES (pytest with pytest-mock, pytest-asyncio)
- **Automated tests**: YES (Tests-after approach)
- **Framework**: pytest with pytest-mock, unittest.mock, pytest-asyncio

### Agent-Executed QA Scenarios (MANDATORY - ALL tasks)

**Verification Tool**: Bash (`uv run pytest ...`)

**Each test scenario follows this format:**
```
Scenario: [Test function name]
  Tool: Bash (uv run pytest)
  Preconditions: Virtual environment activated via uv
  Steps:
    1. Run: uv run pytest [test_file]::[test_function] -v
    2. Assert: Exit code is 0
    3. Assert: Output contains "PASSED" for the test
  Expected Result: Test passes
  Evidence: pytest output captured
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 0 (FIRST - Baseline):
└── Task 0: Capture baseline coverage report

Wave 1 (After Wave 0 - Independent):
├── Task 1: subprocess_runner.py tests (HIGH priority, zero coverage)
├── Task 2: pabot.py error handling tests (MEDIUM priority)
└── Task 3: robot_output_parser.py edge cases (LOW priority)

Wave 2 (After Wave 1):
├── Task 4: robot_orchestrator.py edge cases (depends on understanding patterns from Wave 1)
└── Task 5: combined_generator.py partial failures (depends on Wave 1 patterns)

Wave 3 (After Wave 2):
└── Task 6: Integration verification - run full test suite

Wave 4 (FINAL - Coverage Comparison):
└── Task 7: Final coverage report and comparison to baseline

Critical Path: Task 0 → Task 1 → Task 4 → Task 6 → Task 7
Parallel Speedup: ~50% faster than sequential
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 0 | None | 1, 2, 3 | None (must run first) |
| 1 | 0 | 4, 6 | 2, 3 |
| 2 | 0 | 6 | 1, 3 |
| 3 | 0 | 6 | 1, 2 |
| 4 | 1 | 6 | 5 |
| 5 | 1 | 6 | 4 |
| 6 | 1, 2, 3, 4, 5 | 7 | None |
| 7 | 6 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Dispatch |
|------|-------|---------------------|
| 0 | 0 | `task(category="quick", load_skills=[], run_in_background=false)` |
| 1 | 1, 2, 3 | `task(category="ultrabrain", load_skills=[], run_in_background=false)` for Task 1; quick for 2, 3 |
| 2 | 4, 5 | `task(category="quick", load_skills=[], run_in_background=false)` |
| 3 | 6 | `task(category="quick", load_skills=[], run_in_background=false)` |
| 4 | 7 | `task(category="quick", load_skills=[], run_in_background=false)` |

---

## TODOs

- [x] 1. Create tests for SubprocessRunner error scenarios (HIGH PRIORITY)

  **What to do**:
  - Create new file: `tests/unit/pyats_core/execution/test_subprocess_runner.py`
  - Create directory if needed: `tests/unit/pyats_core/execution/`
  - Implement 8 test functions covering:
    1. `test_execute_job_subprocess_crashes` - return code > 1 returns None
    2. `test_execute_job_archive_not_created` - success but file missing
    3. `test_execute_job_spawn_failure_file_not_found` - pyats script missing
    4. `test_execute_job_spawn_failure_permission_error` - permission denied
    5. `test_parse_progress_event_malformed_json` - invalid JSON handling
    6. `test_parse_progress_event_missing_prefix` - non-NAC_PROGRESS lines
    7. `test_process_output_limit_overrun_error` - LimitOverrunError recovery
    8. `test_drain_remaining_buffer_timeout` - buffer drain timeout handling
  - Use pytest-asyncio for async test functions
  - Mock `asyncio.create_subprocess_exec` using `unittest.mock.AsyncMock`

  **Must NOT do**:
  - Do NOT spawn actual subprocesses
  - Do NOT test PyATS functionality itself
  - Do NOT fix bugs found during testing (separate PR)

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Complex async mocking patterns, highest priority task, requires careful design
  - **Skills**: `[]`
    - No special skills needed - standard Python/pytest work
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not browser-related
    - `git-master`: Not git operations during implementation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 4, 6
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `tests/unit/robot/test_orchestrator.py:21-56` - Fixture patterns for temp directories, mock data paths
  - `tests/pyats_core/common/test_subprocess_auth.py:1-50` - Subprocess-related test patterns (though different approach)
  - `tests/pyats_core/common/test_auth_cache.py:50-100` - File operation mocking and caplog usage

  **API/Type References** (contracts to implement against):
  - `nac_test/pyats_core/execution/subprocess_runner.py:48-166` - `execute_job()` method signature and return contract
  - `nac_test/pyats_core/execution/subprocess_runner.py:285-302` - `_parse_progress_event()` method
  - `nac_test/pyats_core/execution/subprocess_runner.py:378-462` - `_process_output_realtime()` with LimitOverrunError handling
  - `nac_test/pyats_core/execution/subprocess_runner.py:304-376` - `_drain_remaining_buffer_safe()` timeout handling

  **Test References** (testing patterns to follow):
  - `tests/unit/robot/test_orchestrator.py:213-279` - Testing methods that return TestResults.empty()
  - `tests/unit/robot/test_orchestrator.py:199-211` - Using caplog to assert log messages

  **External References** (libraries and frameworks):
  - pytest-asyncio docs: `https://pytest-asyncio.readthedocs.io/` - async test function patterns
  - unittest.mock.AsyncMock: `https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock`

  **WHY Each Reference Matters**:
  - `test_orchestrator.py` fixtures: Reuse same patterns for consistency
  - `subprocess_runner.py:48-166`: Understand return value contract (Path | None)
  - `_parse_progress_event`: Returns None for invalid JSON (no exception)
  - `_process_output_realtime`: Logs errors and continues processing

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios (MANDATORY):**

  ```
  Scenario: All subprocess_runner tests pass
    Tool: Bash (uv run pytest)
    Preconditions: Tests written and saved
    Steps:
      1. uv run pytest tests/unit/pyats_core/execution/test_subprocess_runner.py -v
      2. Assert: Exit code is 0
      3. Assert: Output shows 8 tests passed
      4. Assert: No test failures or errors
    Expected Result: All 8 tests pass
    Evidence: pytest output captured

  Scenario: test_execute_job_subprocess_crashes verifies None return
    Tool: Bash (uv run pytest)
    Preconditions: Test file created
    Steps:
      1. uv run pytest tests/unit/pyats_core/execution/test_subprocess_runner.py::test_execute_job_subprocess_crashes -v
      2. Assert: Exit code is 0
      3. Assert: Test verifies execute_job() returns None when return code > 1
    Expected Result: Test passes, verifies correct error handling
    Evidence: pytest output shows PASSED

  Scenario: test_parse_progress_event_malformed_json verifies graceful handling
    Tool: Bash (uv run pytest)
    Preconditions: Test file created
    Steps:
      1. uv run pytest tests/unit/pyats_core/execution/test_subprocess_runner.py::test_parse_progress_event_malformed_json -v
      2. Assert: Exit code is 0
      3. Assert: Test verifies method returns None (not raises exception)
    Expected Result: Test passes
    Evidence: pytest output shows PASSED

  Scenario: test_process_output_limit_overrun_error verifies recovery
    Tool: Bash (uv run pytest)
    Preconditions: Test file created
    Steps:
      1. uv run pytest tests/unit/pyats_core/execution/test_subprocess_runner.py::test_process_output_limit_overrun_error -v
      2. Assert: Exit code is 0
      3. Assert: Test verifies LimitOverrunError is caught and logged
      4. Assert: caplog contains "Output line exceeded buffer limit"
    Expected Result: Test passes, verifies error recovery
    Evidence: pytest output shows PASSED
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests passed
  - [ ] Test count matches expected (8 tests)

  **Commit**: NO (user approval required before any commits)

---

- [x] 2. Create tests for pabot error handling (MEDIUM PRIORITY)

  **What to do**:
  - Create new file: `tests/unit/robot/test_pabot_error_handling.py`
  - Implement 2+ test functions covering:
    1. `test_run_pabot_unexpected_exception` - pabot.main_program raises exception
    2. `test_parse_and_validate_extra_args_data_error` - DataError from robot.errors
  - Mock `pabot.pabot.main_program` to simulate exceptions

  **Must NOT do**:
  - Do NOT test pabot internals
  - Do NOT run actual Robot Framework tests

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple mocking task, well-understood patterns
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**:
    - None relevant

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `tests/unit/test_pabot_args.py` - Existing pabot argument tests (if present)
  - `tests/unit/robot/test_orchestrator.py:363-377` - Mocking run_pabot patterns

  **API/Type References**:
  - `nac_test/robot/pabot.py:78-133` - `run_pabot()` function signature
  - `nac_test/robot/pabot.py:14-75` - `parse_and_validate_extra_args()` function

  **WHY Each Reference Matters**:
  - `pabot.py:131`: `pabot.pabot.main_program(args)` is the call to mock
  - `test_orchestrator.py:363-377`: Shows how to mock `run_pabot` return values

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: All pabot error handling tests pass
    Tool: Bash (uv run pytest)
    Preconditions: Tests written
    Steps:
      1. uv run pytest tests/unit/robot/test_pabot_error_handling.py -v
      2. Assert: Exit code is 0
      3. Assert: 2+ tests passed
    Expected Result: All tests pass
    Evidence: pytest output captured

  Scenario: test_run_pabot_unexpected_exception handles crash
    Tool: Bash (uv run pytest)
    Preconditions: Test file created
    Steps:
      1. uv run pytest tests/unit/robot/test_pabot_error_handling.py::test_run_pabot_unexpected_exception -v
      2. Assert: Exit code is 0
    Expected Result: Test passes
    Evidence: pytest output shows PASSED
  ```

  **Commit**: NO (user approval required)

---

- [x] 3. Add edge case tests for RobotResultParser (LOW PRIORITY)

  **What to do**:
  - Extend existing file: `tests/unit/robot/test_robot_output_parser.py`
  - Add 1+ test function:
    1. `test_parse_corrupted_xml_structure` - XML that parses but has wrong structure

  **Must NOT do**:
  - Do NOT duplicate existing tests for missing file (already covered)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single test addition to existing file
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `tests/unit/robot/test_robot_output_parser.py` - Existing test patterns (read first!)

  **API/Type References**:
  - `nac_test/robot/reporting/robot_output_parser.py:162-202` - `RobotResultParser.parse()` method

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Robot output parser tests pass including new edge case
    Tool: Bash (uv run pytest)
    Preconditions: Test added
    Steps:
      1. uv run pytest tests/unit/robot/test_robot_output_parser.py -v
      2. Assert: Exit code is 0
      3. Assert: All tests pass including new edge case
    Expected Result: Tests pass
    Evidence: pytest output captured
  ```

  **Commit**: NO (user approval required)

---

- [x] 4. Add edge case tests for RobotOrchestrator symlink handling (MEDIUM PRIORITY)

  **What to do**:
  - Extend existing file: `tests/unit/robot/test_orchestrator.py`
  - Add 2 test functions:
    1. `test_create_backward_compat_symlinks_target_is_directory` - target exists as directory
    2. `test_get_test_statistics_partially_corrupted_xml` - XML parses but missing expected elements

  **Must NOT do**:
  - Do NOT change existing tests
  - Do NOT test unrelated functionality

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding tests to well-understood existing file
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 5)
  - **Blocks**: Task 6
  - **Blocked By**: Task 1 (for pattern consistency)

  **References**:

  **Pattern References**:
  - `tests/unit/robot/test_orchestrator.py:157-211` - Existing symlink tests
  - `tests/unit/robot/test_orchestrator.py:263-279` - Invalid XML handling test

  **API/Type References**:
  - `nac_test/robot/orchestrator.py:271-300` - `_create_backward_compat_symlinks()` method
  - `nac_test/robot/orchestrator.py:302-326` - `_get_test_statistics()` method

  **WHY Each Reference Matters**:
  - Lines 294-296: Current code uses `target.unlink()` - but what if target is directory?
  - Lines 314-326: Exception handling returns `TestResults.empty()` - need to verify

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Robot orchestrator tests pass including new edge cases
    Tool: Bash (uv run pytest)
    Preconditions: Tests added
    Steps:
      1. uv run pytest tests/unit/robot/test_orchestrator.py -v
      2. Assert: Exit code is 0
      3. Assert: All tests pass
    Expected Result: Tests pass
    Evidence: pytest output captured

  Scenario: test_create_backward_compat_symlinks_target_is_directory
    Tool: Bash (uv run pytest)
    Preconditions: Test added
    Steps:
      1. uv run pytest tests/unit/robot/test_orchestrator.py::TestRobotOrchestrator::test_create_backward_compat_symlinks_target_is_directory -v
      2. Assert: Exit code is 0
    Expected Result: Test passes, verifies behavior when target is directory
    Evidence: pytest output shows PASSED
  ```

  **Commit**: NO (user approval required)

---

- [x] 5. Add partial failure tests for CombinedOrchestrator (MEDIUM PRIORITY)

  **What to do**:
  - Extend existing file: `tests/unit/core/test_combined_generator.py` OR create `tests/unit/test_combined_orchestrator_errors.py`
  - Add 2 test functions:
    1. `test_combined_results_with_robot_error` - Robot fails but PyATS succeeds
    2. `test_combined_results_with_partial_failures` - Mixed results aggregation

  **Must NOT do**:
  - Do NOT test full orchestration (that's integration level)
  - Do NOT change CombinedResults dataclass behavior

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Testing dataclass computed properties
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 4)
  - **Blocks**: Task 6
  - **Blocked By**: Task 1 (for pattern consistency)

  **References**:

  **Pattern References**:
  - `tests/unit/core/test_combined_generator.py` - Existing CombinedResults tests
  - `tests/unit/test_combined_orchestrator_flow.py` - Orchestrator flow tests

  **API/Type References**:
  - `nac_test/core/types.py:119-218` - `CombinedResults` dataclass with computed properties
  - `nac_test/core/types.py:36-46` - `TestResults.from_error()` class method

  **WHY Each Reference Matters**:
  - `CombinedResults._iter_results()`: Filters None values - need to test with errors
  - `TestResults.from_error()`: Creates error result - verify aggregation includes it

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Combined results error tests pass
    Tool: Bash (uv run pytest)
    Preconditions: Tests added
    Steps:
      1. uv run pytest tests/unit/core/test_combined_generator.py -v
      2. Assert: Exit code is 0
      3. Assert: All tests pass
    Expected Result: Tests pass
    Evidence: pytest output captured

  Scenario: test_combined_results_with_robot_error verifies error handling
    Tool: Bash (uv run pytest)
    Preconditions: Test added
    Steps:
      1. uv run pytest tests/unit/core/test_combined_generator.py::test_combined_results_with_robot_error -v
      2. Assert: Exit code is 0
      3. Assert: Test verifies CombinedResults.has_errors is True when robot has error
    Expected Result: Test passes
    Evidence: pytest output shows PASSED
  ```

  **Commit**: NO (user approval required)

---

- [x] 6. Integration verification - run full test suite (FINAL)

  **What to do**:
  - Run full unit test suite to verify no regressions
  - Run linting to verify code quality
  - Summarize test coverage improvements

  **Must NOT do**:
  - Do NOT commit without user approval

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple verification task
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential, final verification)
  - **Parallel Group**: Wave 3 (final)
  - **Blocks**: None (end of plan)
  - **Blocked By**: Tasks 1, 2, 3, 4, 5

  **References**:

  **Test References**:
  - `pyproject.toml` - pytest configuration
  - `.github/workflows/test.yml` - CI test commands

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Full unit test suite passes
    Tool: Bash (uv run pytest)
    Preconditions: All previous tasks completed
    Steps:
      1. uv run pytest tests/unit/ -v
      2. Assert: Exit code is 0
      3. Assert: No test failures
    Expected Result: All unit tests pass
    Evidence: pytest output captured

  Scenario: Full integration test suite passes
    Tool: Bash (uv run pytest)
    Preconditions: Unit tests pass
    Steps:
      1. uv run pytest tests/integration/ -v
      2. Assert: Exit code is 0 OR expected failures only
    Expected Result: Integration tests pass
    Evidence: pytest output captured

  Scenario: Linting passes
    Tool: Bash (uv run ruff)
    Preconditions: Tests written
    Steps:
      1. uv run ruff check tests/unit/pyats_core/execution/test_subprocess_runner.py
      2. uv run ruff check tests/unit/robot/test_pabot_error_handling.py
      3. Assert: No linting errors
    Expected Result: Code quality verified
    Evidence: ruff output captured
  ```

  **Commit**: NO (user approval required - will ask user if they want to commit)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| ALL (6) | `test: add edge case and error scenario coverage for subprocess handling` | All new/modified test files | `uv run pytest tests/unit/ -v` |

**Note**: Single commit after all tasks complete and user approval received.

---

## Success Criteria

### Verification Commands
```bash
# Run all new subprocess_runner tests
uv run pytest tests/unit/pyats_core/execution/test_subprocess_runner.py -v
# Expected: 8 tests passed

# Run all unit tests (regression check)
uv run pytest tests/unit/ -v
# Expected: All tests pass, no regressions

# Run linting on new files
uv run ruff check tests/unit/pyats_core/execution/
# Expected: No errors
```

### Final Checklist
- [x] All "Must Have" scenarios have tests
- [x] All "Must NOT Have" guardrails respected
- [x] All tests use `uv run pytest ...` (never `python` or `pytest`)
- [x] No commits made without user approval
- [x] All tests follow existing project patterns
- [x] `subprocess_runner.py` has 8+ new tests (from zero)
- [x] No actual subprocesses spawned in tests
