# E2E Tests for Combined Reporting

This directory contains end-to-end (E2E) tests that verify the complete nac-test workflow, including Robot Framework tests, PyATS API tests, PyATS D2D (device-to-device) tests, and the combined reporting dashboard.

> **Note:** E2E tests take approximately 1 minute per scenario to execute, as they run the full nac-test CLI pipeline. Use parallel execution (`-n auto`) to significantly reduce total runtime.

## Architecture

### Test Infrastructure

The E2E tests use mock infrastructure to simulate real endpoints without requiring actual network devices or controllers:

1. **Mock API Server** (`tests/e2e/mocks/mock_server.py`)
   - Flask-based HTTP server running on `localhost`
   - Uses OS-assigned ports (port 0) for parallel test execution compatibility
   - Simulates SD-WAN Manager, ACI, and Catalyst Center API endpoints
   - Configured via `tests/e2e/mocks/mock_api_config.yaml`
   - Handles authentication, token generation, and API responses

2. **Mock SSH Devices** (`tests/e2e/mocks/mock_unicon.py`)
   - Simulates IOS-XE devices for PyATS D2D tests
   - Referenced in a dynamically generated `testbed.yaml`
   - Supports common show commands with canned responses
   - Allows tests to verify device connectivity and command parsing

### Test Organization

Tests use a **base class inheritance pattern** to minimize code duplication:

```
E2ECombinedTestBase (ABC)          # ~35 common tests for all scenarios
    ├── TestE2ESuccess             # All tests pass scenario
    ├── TestE2EAllFail             # All tests fail scenario
    └── TestE2EMixed               # Mixed pass/fail scenario
```

Each scenario:
- Runs the full nac-test CLI once (class-scoped fixture)
- Executes Robot Framework + PyATS API + PyATS D2D tests
- Generates combined reporting dashboard
- Validates all outputs against expected results

### Directory Structure

```
tests/e2e/
├── README.md              # This file
├── __init__.py
├── config.py              # E2EScenario dataclass and scenario definitions
├── conftest.py            # Pytest fixtures (mock server, testbed, scenarios)
├── html_helpers.py        # HTML parsing utilities for report validation
├── test_e2e_scenarios.py   # Main test file with base class and scenarios
└── fixtures/              # Test fixture data per scenario
    ├── success/           # All tests pass
    │   ├── data.yaml
    │   └── templates/tests/
    ├── failure/           # All tests fail
    │   ├── data.yaml
    │   └── templates/tests/
    └── mixed/             # Mixed pass/fail results
        ├── data.yaml
        └── templates/tests/
```

## Running E2E Tests

```bash
# Run all E2E tests in parallel (recommended)
pytest tests/e2e/ -n auto --dist loadscope

# Run all E2E tests sequentially (slower)
pytest tests/e2e/ -v

# Run a specific scenario
pytest tests/e2e/test_e2e_scenarios.py::TestE2ESuccess -v

# Run a specific test
pytest tests/e2e/test_e2e_scenarios.py::TestE2ESuccess::test_robot_statistics_correct -v

# Run tests matching a keyword
pytest tests/e2e/ -v -k "links_resolve"
```

### Parallel Execution

E2E tests support parallel execution via `pytest-xdist`. Use `--dist loadscope` to ensure all tests within a class run on the same worker (required for class-scoped fixtures):

```bash
# Auto-detect CPU count
pytest tests/e2e/ -n auto --dist loadscope

# Use specific number of workers
pytest tests/e2e/ -n 4 --dist loadscope
```

**Important:** Each test class shares a single scenario execution via class-scoped fixtures. The `--dist loadscope` flag ensures tests from the same class are not distributed across workers.

## Adding a New Scenario

1. **Create fixture directory** under `tests/e2e/fixtures/<scenario_name>/`
   - Add `data.yaml` with test data
   - Add `templates/tests/` with Robot and/or PyATS test files

2. **Define scenario** in `tests/e2e/config.py`:
   ```python
   NEW_SCENARIO = E2EScenario(
       name="new_scenario",
       description="Description of what this tests",
       data_path=f"{_FIXTURE_BASE}/new_scenario/data.yaml",
       templates_path=f"{_FIXTURE_BASE}/new_scenario/templates",
       expected_exit_code=0,  # or 1 if failures expected
       expected_robot_passed=1,
       expected_robot_failed=0,
       # ... other expected values
   )
   ```

3. **Add fixture** in `tests/e2e/conftest.py`:
   ```python
   @pytest.fixture(scope="class")
   def e2e_new_scenario_results(...) -> E2EResults:
       from tests.e2e.config import NEW_SCENARIO
       return _run_e2e_scenario(NEW_SCENARIO, ...)
   ```

4. **Create test class** in `tests/e2e/test_e2e_scenarios.py`:
   ```python
   class TestE2ENewScenario(E2ECombinedTestBase):
       @pytest.fixture
       def results(self, e2e_new_scenario_results: E2EResults) -> E2EResults:
           return e2e_new_scenario_results
   ```

## Test Categories

The base class includes tests for:

- **CLI Behavior**: Exit code, exception handling
- **Directory Structure**: Output directories created correctly
- **Robot Framework**: output.xml, log.html, report.html, statistics
- **PyATS API**: Summary reports, statistics, breadcrumb navigation
- **PyATS D2D**: Summary reports, statistics, breadcrumb navigation
- **Combined Dashboard**: Aggregated statistics, links to sub-reports
- **Backward Compatibility**: Symlinks for legacy file locations
