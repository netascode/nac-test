## Summary

This PR implements a unified test execution framework that combines PyATS (API and D2D tests) with Robot Framework, providing a single combined dashboard at the output root.

Closes #470

## What's New

### Combined Dashboard (`combined_summary.html`)

- **Unified entry point** at the output root aggregating results from all test frameworks (pyats API, pyats D2D and robot)
- Shows overall statistics (total, passed, failed, skipped) across all frameworks
- Individual framework blocks (API, D2D, Robot) with links to summary reports
- Dashboard generated for ALL test runs, not just when multiple frameworks execute

### Robot Framework Output Alignment

- Robot output files now stored in `robot_results/` subdirectory
- Backward compatibility symlinks at root (`output.xml`, `log.html`, `report.html`, `xunit.xml`)
- Framework-specific `summary_report.html` generated in `robot_results/`

## Architecture Changes

### `TestResults` Data Model (`nac_test/core/types.py`)

- `TestResults` and `CombinedResults` dataclasses passed from orchestrators back to main() for proper exit code generation (to be finalized in #469)
- Added `TestResults.from_counts()` factory method for convenient object creation
- `success_rate` computed automatically by the dataclass (no manual calculation in generators)

### Streamlined Statistics Flow

- Orchestrators populate results directly with `TestResults`/`CombinedResults` objects
- `CombinedReportGenerator` receives `CombinedResults` for rendering
- Templates access statistics via object attributes (`stats.total`, `stats.passed`, etc.) rather than dictionary keys

### Template Variable Simplification

- Templates now receive `TestResults` objects directly instead of expanded dictionary keys
- Template syntax changed from `{{ total_tests }}`, `{{ passed_tests }}` to `{{ stats.total }}`, `{{ stats.passed }}`
- Combined report template uses `{{ overall_stats.total }}` and `{{ framework_data.stats.total }}`
- `RobotResultParser` now returns `TestResults` objects via a `stats` property


## Output Directory Structure

```
output/
├── combined_summary.html          # Unified dashboard (NEW)
├── merged_data.yaml
├── output.xml -> robot_results/output.xml    # Symlink for backward compat
├── log.html -> robot_results/log.html
├── report.html -> robot_results/report.html
├── xunit.xml -> robot_results/xunit.xml
├── robot_results/
│   ├── output.xml
│   ├── log.html
│   ├── report.html
│   ├── xunit.xml
│   └── summary_report.html        # Robot-specific summary
└── pyats_results/
    ├── api/
    │   └── html_reports/
    │       └── summary_report.html
    └── d2d/
        └── html_reports/
            └── summary_report.html
```

## Testing

### New E2E Test Framework

This PR introduces a comprehensive E2E test framework in `tests/e2e/` that replaces the previous scattered integration tests:

- **Multi-architecture support**: Tests can target SDWAN, ACI, or Catalyst Center with architecture-specific environment variable configuration
- **Scenario-based testing**: 7 test scenarios covering different combinations (success, failure, mixed, robot-only, pyats-api-only, pyats-d2d-only, pyats-cc)
- **Comprehensive validation**: Each scenario validates CLI behavior, directory structure, Robot/PyATS outputs, HTML report structure, statistics accuracy, and cross-report navigation
- **Mock infrastructure**: Flask-based mock API server and mock Unicon devices enable full E2E testing without real network devices
- **Parallel execution**: Uses `pytest-xdist` with OS-assigned ports for ~5x speedup; CI runs unit/integration tests sequentially and E2E tests in parallel
- **Consolidated fixtures**: Shared test fixtures moved to `tests/conftest.py`, reducing duplication across test modules

### Skipped Tests

3 integration tests for exit code 252 handling are skipped (deferred to #469):
- `test_robot_invalid_extra_args_returns_252`
- `test_robot_invalid_include_tag_returns_252`
- `test_robot_missing_tests_returns_252`

### New Unit Tests

This PR adds **74 new unit tests** across 7 new test files (+2,200 lines):

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `test_combined_orchestrator_flow.py` | 14 | Discovery-based routing, dev mode flags, render-only mode, dashboard generation |
| `test_orchestrator.py` (Robot) | 18 | Initialization, file operations, symlinks, statistics, error handling |
| `test_robot_output_parser.py` | 11 | XML parsing, stats extraction, timestamp handling, error recovery |
| `test_robot_generator.py` | 11 | Summary report generation, stats aggregation, template rendering |
| `test_combined_generator.py` | 10 | Combined dashboard generation, success rate calculation, error handling |
| `test_subprocess_runner.py` | 8 | Process crashes, file errors, malformed data, buffer handling |
| `test_pabot_error_handling.py` | 2 | Exception propagation, argument validation errors |

**Key test scenarios covered:**
- **CombinedOrchestrator flow**: Test discovery routing, dev mode (`--pyats`/`--robot`), render-only mode, dashboard generation with empty/partial results
- **Robot Framework**: Output file management, backward-compat symlinks (including edge cases like directory targets), XML parsing with corrupted data
- **Report generation**: Template rendering, exception handling, zero-test scenarios, `TestResults` object passing
- **SubprocessRunner**: PyATS process crashes, missing archives, spawn failures, malformed progress events

## Breaking Changes

`pyats_results/combined_summary.html` no longer exists, this one moved to the root 

## Related Issues

- Closes #470 - Combined Dashboard
- Closes #507 - E2E Tests with artifacts verification
- Exit code 252 handling deferred to #469

## Screenshots

### Combined Dashboard (new)

<img width="1687" height="1286" alt="image" src="https://github.com/user-attachments/assets/685f3984-36ee-45af-b3cd-23c762b33d05" />

### Robot Summary Page (new)

<img width="1702" height="1312" alt="image" src="https://github.com/user-attachments/assets/3582f4e8-35cd-4f1f-98dd-33748c6861be" />

The details link into the normal robot log.html

