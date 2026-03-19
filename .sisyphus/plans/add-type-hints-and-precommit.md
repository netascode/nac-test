# Add Type Hints and Run Pre-commit Hooks

## TL;DR

> **Quick Summary**: Add type hints and docstrings to `test_subprocess_runner.py`, then stage all changed files and verify with pre-commit hooks.
> 
> **Deliverables**:
> - Updated `tests/unit/pyats_core/execution/test_subprocess_runner.py` with type hints and docstrings
> - All changed test files staged in git
> - Pre-commit hooks verified passing
> 
> **Estimated Effort**: Quick (5-10 minutes)
> **Parallel Execution**: NO - sequential

---

## Context

### Original Request
User requested two things:
1. Add type hints and comments to `tests/unit/pyats_core/execution/test_subprocess_runner.py`
2. Stage all changed files and verify them using all pre-commit hooks

### Files Changed in This Session (to be staged)
- `tests/unit/pyats_core/execution/test_subprocess_runner.py` (NEW - 8 tests)
- `tests/unit/robot/test_pabot_error_handling.py` (NEW - 2 tests)
- `tests/unit/robot/test_robot_output_parser.py` (MODIFIED - 1 test added)
- `tests/unit/robot/test_orchestrator.py` (MODIFIED - 2 tests added)
- `tests/unit/core/test_combined_generator.py` (MODIFIED - 2 tests added)

---

## TODOs

- [ ] 1. Add type hints and docstrings to test_subprocess_runner.py

  **What to do**:
  - Add module-level docstring explaining the test file's purpose
  - Add type hints to all fixtures and helper functions
  - Add docstrings to all test functions explaining what they test
  - Add type hint `pytest.LogCaptureFixture` for `caplog` parameter
  - Add type hint `dict[str, Any] | None` for `_parse_progress_event` results
  - Organize tests into sections with comment headers

  **Must NOT do**:
  - Do NOT change test logic
  - Do NOT rename functions

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 2
  - **Blocked By**: None

  **References**:

  **File to modify**:
  - `tests/unit/pyats_core/execution/test_subprocess_runner.py`

  **Type hints to add**:
  ```python
  # Module docstring at top:
  """Unit tests for SubprocessRunner error handling and edge cases.
  
  This module tests error scenarios in the SubprocessRunner class, focusing on:
  - Subprocess crash handling (non-zero return codes)
  - File operation failures (missing archives, spawn failures)
  - Malformed data recovery (invalid JSON progress events)
  - Resource limit handling (LimitOverrunError, buffer timeouts)
  
  Note:
      All tests mock asyncio.create_subprocess_exec to avoid spawning actual
      subprocesses. Async methods are tested using asyncio.run() since
      pytest-asyncio is not installed in this project.
  """
  
  # Add import:
  from typing import Any
  
  # For caplog parameters, change:
  caplog  # to:
  caplog: pytest.LogCaptureFixture
  
  # For _parse_progress_event result variables:
  result: dict[str, Any] | None = runner._parse_progress_event(...)
  
  # For stdout mock:
  stdout: AsyncMock = AsyncMock()
  ```

  **Docstring pattern for test functions**:
  ```python
  def test_execute_job_subprocess_crashes(...) -> None:
      """Test that execute_job returns None when subprocess exits with code > 1.
      
      When the PyATS subprocess crashes or fails (return code > 1), the runner
      should log an error and return None instead of a path to indicate failure.
      
      This covers the error path at subprocess_runner.py:135-140 where non-zero
      return codes are handled.
      """
  ```

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Tests still pass after adding type hints
    Tool: Bash (uv run pytest)
    Steps:
      1. uv run pytest tests/unit/pyats_core/execution/test_subprocess_runner.py -v
      2. Assert: Exit code is 0
      3. Assert: 8 tests passed
    Expected Result: All tests pass
    Evidence: pytest output

  Scenario: Ruff check passes
    Tool: Bash (uv run ruff)
    Steps:
      1. uv run ruff check tests/unit/pyats_core/execution/test_subprocess_runner.py
      2. Assert: No errors
    Expected Result: Linting passes
    Evidence: ruff output
  ```

  **Commit**: NO (part of larger commit)

---

- [ ] 2. Stage all changed files and run pre-commit hooks

  **What to do**:
  - Stage all test files changed in this session
  - Run pre-commit hooks on staged files
  - Fix any issues found by hooks
  - Verify all hooks pass

  **Must NOT do**:
  - Do NOT commit (user will review first)
  - Do NOT stage files outside the test directories

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[git-master]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None (final task)
  - **Blocked By**: Task 1

  **References**:

  **Files to stage**:
  ```
  tests/unit/pyats_core/execution/test_subprocess_runner.py
  tests/unit/robot/test_pabot_error_handling.py
  tests/unit/robot/test_robot_output_parser.py
  tests/unit/robot/test_orchestrator.py
  tests/unit/core/test_combined_generator.py
  ```

  **Commands**:
  ```bash
  # Stage all changed test files
  git add tests/unit/pyats_core/execution/test_subprocess_runner.py
  git add tests/unit/robot/test_pabot_error_handling.py
  git add tests/unit/robot/test_robot_output_parser.py
  git add tests/unit/robot/test_orchestrator.py
  git add tests/unit/core/test_combined_generator.py
  
  # Run pre-commit hooks on staged files
  uv run pre-commit run --files tests/unit/pyats_core/execution/test_subprocess_runner.py tests/unit/robot/test_pabot_error_handling.py tests/unit/robot/test_robot_output_parser.py tests/unit/robot/test_orchestrator.py tests/unit/core/test_combined_generator.py
  
  # Or run all hooks:
  uv run pre-commit run
  ```

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: All files staged
    Tool: Bash (git)
    Steps:
      1. git status --short
      2. Assert: All 5 test files show as staged (A or M in first column)
    Expected Result: Files staged
    Evidence: git status output

  Scenario: Pre-commit hooks pass
    Tool: Bash (uv run pre-commit)
    Steps:
      1. uv run pre-commit run
      2. Assert: Exit code is 0 OR all hooks show "Passed" or "Skipped"
    Expected Result: All hooks pass
    Evidence: pre-commit output
  ```

  **Commit**: NO (awaiting user approval per constraint)

---

## Success Criteria

### Verification Commands
```bash
# Verify tests still pass
uv run pytest tests/unit/pyats_core/execution/test_subprocess_runner.py -v

# Verify linting passes
uv run ruff check tests/unit/pyats_core/execution/

# Verify pre-commit passes
uv run pre-commit run

# Show staged files
git status
```

### Final Checklist
- [ ] Type hints added to all function signatures
- [ ] Docstrings added to all test functions
- [ ] All 5 test files staged
- [ ] Pre-commit hooks pass on all staged files
- [ ] No commits made (awaiting user approval)
