# Commit Message for #612

```
fix(cli): move controller detection to CombinedOrchestrator.run_tests() (#612)

Robot Framework tests were blocked by controller detection even when
only D2D credentials were provided. This change moves controller
detection to CombinedOrchestrator.run_tests(), enabling Robot tests
to run independently when detection fails.

PROBLEM:
Running `nac-test` with Robot-only tests required controller
credentials even though Robot tests might not use them. Detection happened
eagerly in CombinedOrchestrator.__init__(), blocking execution before
any test framework could run.

SOLUTION:
- Move controller detection to CombinedOrchestrator.run_tests()
- On detection failure: set error state for PyATS, continue to Robot
- PyATSOrchestrator receives controller_type from caller (no detection)
- Return error results instead of sys.exit() on failures

CHANGES:

CombinedOrchestrator:
- Move controller detection from __init__() to run_tests()
- Skip detection when dry_run=True or render_only=True
- On detection failure: set error on api/d2d results, allow Robot to run
- Pass controller_type to PyATSOrchestrator constructor

PyATSOrchestrator:
- Remove detect_controller_type import and internal detection logic
- Require controller_type from caller (None allowed only for dry_run)
- Return error result if controller_type is None during actual execution
- Credential validation still performed internally

EnvironmentValidator (nac_test/utils/environment.py):
- Add get_missing_controller_vars(controller_type) -> list[str]
- Add format_missing_credentials_error(controller_type, missing) -> str
- Change validate_controller_env() to return list[str] (no sys.exit)
- Remove generic check_required_vars() and format_missing_vars_error()
  (unused after refactor)
- Import CREDENTIAL_PATTERNS from controller.py (source of truth)

controller.py:
- Fix log message for incomplete credentials (human-readable, not dict)

CombinedResults (nac_test/core/types.py):
- errors property now returns deduplicated list

TEST CHANGES:

Deleted (tested detection in PyATSOrchestrator, now obsolete):
- tests/pyats_core/test_orchestrator_controller_detection.py
  - test_orchestrator_detects_controller_on_init
  - test_orchestrator_exits_on_detection_failure
  - test_orchestrator_handles_multiple_controllers_error
  - test_validate_environment_uses_detected_controller
  - test_orchestrator_no_longer_uses_controller_type_env_var

- tests/pyats_core/test_orchestrator_controller_param.py
  - test_orchestrator_uses_provided_controller_type
  - test_orchestrator_falls_back_to_detection_when_none
  - test_orchestrator_defaults_to_detection
  - test_validate_environment_uses_provided_controller

Added (new file - tests PyATS validation, detection now in CombinedOrchestrator):
- tests/pyats_core/test_orchestrator_controller.py
  - test_controller_type_preserved_from_init
  - test_dry_run_accepts_none_controller_type
  - test_missing_controller_type_for_execution_returns_error
  - test_provided_controller_type_missing_credentials_returns_error
  - test_error_results_only_for_discovered_categories_api_only
  - test_error_results_only_for_discovered_categories_d2d_only

Replaced (tests detection in CombinedOrchestrator.run_tests()):
- tests/unit/test_combined_orchestrator_controller.py
  OLD (tested eager detection in __init__, sys.exit on failure):
    - test_combined_orchestrator_detects_controller_on_init
    - test_combined_orchestrator_exits_on_detection_failure
    - test_combined_orchestrator_passes_controller_to_pyats
    - test_render_only_mode_does_not_instantiate_pyats_orchestrator
    - test_combined_orchestrator_production_mode_passes_controller
  NEW (tests detection in run_tests() with graceful degradation):
    - test_combined_orchestrator_delegates_to_pyats_with_controller_type
    - test_robot_only_does_not_invoke_pyats
    - test_render_only_does_not_invoke_pyats
    - test_detection_failure_sets_error_and_allows_robot_to_run
    - test_dry_run_skips_controller_detection
    - test_multiple_controllers_sets_error_and_allows_robot_to_run

Added (new file):
- tests/unit/utils/test_environment.py
  - test_unknown_controller_type_raises_error
  - test_returns_all_vars_when_none_set
  - test_returns_empty_when_all_vars_set
  - test_returns_partial_missing_vars
  - test_delegates_to_get_missing_controller_vars
  - test_unknown_controller_type_raises_error (validate_controller_env)

Reorganized (fixtures consolidated):
- tests/unit/conftest.py
  - Added: clean_controller_env, aci_controller_env fixtures
  - Added: pyats_test_env fixture (PyATSTestEnv namedtuple)
  - Added: PYATS_TEST_FILE_CONTENT, PYATS_D2D_TEST_FILE_CONTENT,
           PYATS_API_TEST_FILE_CONTENT, ROBOT_TEST_FILE_CONTENT constants

- tests/pyats_core/conftest.py
  - Added: PYATS_TEST_FILE_CONTENT, PYATS_D2D_TEST_FILE_CONTENT,
           PYATS_API_TEST_FILE_CONTENT constants

- tests/integration/test_cli_basic.py
- tests/integration/test_cli_extra_args.py
- tests/integration/test_cli_ordering.py
  - Removed duplicate clean_controller_env fixture (use shared from conftest)
  - No longer set up controller environment (Robot-only tests don't need it)

- tests/e2e/config.py
  - E2EScenario.architecture changed from str to str | None
  - ROBOT_ONLY_SCENARIO: architecture=None (no controller credentials needed)

- tests/e2e/conftest.py
  - Conditionally set controller env vars only when scenario.architecture is set
  - Robot-only scenarios now run without any controller credentials

Closes #612
```
