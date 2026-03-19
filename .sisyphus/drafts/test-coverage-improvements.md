# Draft: Test Coverage Improvements for Branch Merge

## Requirements (confirmed)
- Increase test coverage for changes in current branch (`feat/470-combined-dashboard`) vs `release/pyats-integration-v1.1-beta`
- Focus on edge cases and error scenarios (happy path already covered per user)
- Include both unit tests and integration tests
- Special attention to subprocess handling (pyats run, robot/pabot crashes)
- Test commands must use `uv run ..` (never `python` or `pytest` directly)
- No commits without explicit approval

## Branch Context
- **Current branch**: `feat/470-combined-dashboard`
- **Target merge branch**: `release/pyats-integration-v1.1-beta`
- **Key commits (30+)**: Typed results model, combined dashboard, orchestrator refactor, Robot reporting

## Technical Decisions
- Test framework: pytest with pytest-mock, pytest-xdist, pytest-cov
- Test structure: tests/unit/, tests/integration/, tests/e2e/
- Mocking: unittest.mock + pytest-mock (mocker fixture) + MonkeyPatch
- Run command: `uv run pytest ...`

## Research Findings

### Key New/Changed Source Files
1. `nac_test/core/types.py` - NEW: TestResults, PyATSResults, CombinedResults dataclasses
2. `nac_test/core/reporting/combined_generator.py` - NEW: CombinedReportGenerator
3. `nac_test/robot/reporting/robot_output_parser.py` - NEW: RobotResultParser
4. `nac_test/robot/reporting/robot_generator.py` - NEW: RobotReportGenerator
5. `nac_test/robot/orchestrator.py` - CHANGED: Returns TestResults, symlink creation
6. `nac_test/combined_orchestrator.py` - CHANGED: Returns CombinedResults
7. `nac_test/pyats_core/orchestrator.py` - CHANGED: Returns PyATSResults
8. `nac_test/pyats_core/execution/subprocess_runner.py` - Subprocess execution (pyats run)
9. `nac_test/robot/pabot.py` - In-process pabot execution

### Subprocess Handling Analysis (CRITICAL)

#### PyATS Subprocess (subprocess_runner.py)
- Uses `asyncio.create_subprocess_exec` with stdout=PIPE, stderr=STDOUT
- **GAPS IDENTIFIED**:
  1. No overall process timeout (only buffer-drain has timeout)
  2. Returns expected archive path WITHOUT verifying file exists
  3. No explicit signal handling (SIGTERM/SIGKILL)
  4. LimitOverrunError stops output processing but process continues
  5. macOS pipe EOF race condition (mitigated but not fully tested)

#### Robot/Pabot (pabot.py)
- Uses in-process `pabot.pabot.main_program()` (NOT subprocess)
- **GAPS IDENTIFIED**:
  1. Unhandled exceptions in pabot could crash nac-test process
  2. Exit code 252 handled, but other exceptions propagate

#### HTTP/Auth Subprocess (subprocess_client.py, subprocess_auth.py)
- Uses `os.system()` with temp files (fork-safe design)
- **GAPS IDENTIFIED**:
  1. No timeout enforcement
  2. Signal handling maps to -1 exit code

### Error Scenarios NOT Currently Tested
1. PyATS subprocess crashes mid-execution
2. Archive file not created despite return code 0/1
3. Malformed NAC_PROGRESS JSON events
4. Large output lines causing LimitOverrunError
5. Buffer drain timeout on macOS
6. In-process pabot throwing unexpected exception
7. output.xml missing after Robot execution
8. Corrupted/invalid output.xml parsing
9. Symlink creation when target already exists as file
10. Empty test discovery (no tests found)
11. Mixed framework results with partial failures

### Existing Test Coverage (What's Already Tested)
- TestResults/CombinedResults computed properties (partial)
- RobotResultParser basic parsing
- RobotOrchestrator symlink creation
- CombinedOrchestrator dev mode flows
- Auth subprocess success/error paths
- Auth cache with file locking

## Test Strategy Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (Tests-after approach - identify gaps, write tests)
- **Framework**: pytest with pytest-mock

## Scope Boundaries
- INCLUDE: Edge cases, error scenarios, subprocess crash handling
- INCLUDE: Both unit tests and integration tests
- INCLUDE: Mocking to simulate crashes without actual process failures
- EXCLUDE: Happy path tests (user says these are covered)
- EXCLUDE: Any changes without explicit approval
- EXCLUDE: E2E browser tests (out of scope for this task)
