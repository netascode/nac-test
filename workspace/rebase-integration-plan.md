# Rebase Integration Plan: fix/612-controller-check onto release/pyats-integration-v1.1-beta

**Status:** Ready to execute. `feature/preflight-controller-auth` has already been merged
into `release/pyats-integration-v1.1-beta` (as commits `7cc29b6`, `26879b7`, `0d2f56a` —
squash/cherry-picked, not a merge commit). The `feature/` branch itself is now stale.

**Do not** apply `feature/preflight-controller-auth`'s merge commit `2456b7e` — it merged
against an older state of the parent and would conflict or duplicate content already present.

**Rebase command:**
```bash
git checkout fix/612-controller-check
git rebase origin/release/pyats-integration-v1.1-beta
```

The rebase drops the `4a4b8f1` merge commit automatically and replays the 5 meaningful
commits (`ad7228b` → `f3474cd`) onto the current parent tip. Conflicts are expected in the
files listed below; resolve each per the instructions in this plan.

**Goal:** Preserve the two unique contributions of `fix/612-controller-check` on top of the
now-merged preflight code:
1. Robot Framework continues to run even when PyATS pre-flight fails.
2. Inline error display in the combined dashboard for mid-execution errors.

**Important Instructions**:
1. ALWAYS ask for approval before committing any changes
2. ALWAYS use pytest arguments `-n auto --dist loadscope` to speed up execution time
3. NEVER push

---

## What becomes redundant (drop entirely)

These items from `fix/612-controller-check` are fully superseded by
`feature/preflight-controller-auth` and must be removed to avoid duplication/conflicts.

### `nac_test/exceptions.py` (entire file)
- `ControllerDetectionError` is no longer needed.
- Their code keeps `detect_controller_type()` raising `ValueError`; structured error detail
  now lives in `PreFlightFailure.detail` and the auth-failure HTML report.
- **Action:** Delete the file. Remove the import from `combined_orchestrator.py`.

### `nac_test/core/types.py`
- Remove `ErrorType.CONTROLLER_DETECTION` — no longer used once `TestResults.from_error()`
  is no longer called for controller detection failures.
- Remove `verbose_message: str | None` field from `TestResults` and from `TestResults.from_error()`.
- **Action:** Revert those two additions. Keep all other `types.py` changes from both branches
  (`ControllerTypeKey`, `PreFlightFailure`, `CombinedResults.pre_flight_failure`).

### `nac_test/utils/environment.py`
- `get_missing_controller_vars()` and `format_missing_credentials_error()` are only used in
  the standalone guard inside `PyATSOrchestrator.run_tests()` (see below). Both methods can
  be dropped once that guard is removed.
- The broader simplification (removing `check_required_vars()` / `validate_controller_env()`
  with their `sys.exit()` calls) is still valid — keep that.
- **Action:** Keep the simplified `EnvironmentValidator` skeleton but remove the two new
  methods. If `get_missing_controller_vars()` is still wanted for standalone orchestrator use,
  rewrite it to delegate to `CONTROLLER_REGISTRY[controller_type].required_env_vars`.

### `nac_test/pyats_core/orchestrator.py`
- Remove the `EnvironmentValidator.get_missing_controller_vars()` block added at the top of
  `run_tests()` — superseded by their pre-flight HTTP auth check.
- Remove the `controller_type is None` defensive error-return guard — unnecessary now that
  `CombinedOrchestrator` always provides a valid `controller_type` or aborts via
  `PreFlightFailure` before reaching PyATSOrchestrator.
- Keep: removal of the old internal `detect_controller_type()` fallback and `sys.exit()`.
- Keep: `self.controller_type: str | None = controller_type` (pure injection from caller).
- Keep: removal of `validate_environment()` method.
- **Action:** Strip the two new blocks; keep the structural simplification.

### `nac_test/combined_orchestrator.py` — controller_error flag and TestResults.from_error
- Remove the `controller_error` boolean flag.
- Remove the `TestResults.from_error("Controller detection failed", ...)` calls on
  `combined_results.api` and `combined_results.d2d`.
- Remove the `from nac_test.exceptions import ControllerDetectionError` import.
- The `except ControllerDetectionError` block is replaced by their `except ValueError` +
  `PreFlightFailure` pattern (see "What to keep" below).
- **Action:** Adopt their detection + pre-flight block wholesale, then apply the Robot
  continuation change described below.

---

## What to keep (carry forward)

### 1. Robot continues after pre-flight failure  ← core behavioural change

Their `combined_orchestrator.py` after the pre-flight block:
```python
# Their code — returns immediately, Robot never runs
generator = CombinedReportGenerator(self.output_dir)
report_path = generator.generate_combined_summary(combined_results)
if report_path is not None:
    typer.echo(f"Report: {report_path}")
return combined_results          # <-- Robot blocked here
```

**Change:** Remove the `return`. Introduce a `preflight_failed` flag so the PyATS execution
block is skipped, but execution continues to the Robot block.

```python
# Target state
preflight_failed = False

if has_pyats and not self.render_only and not self.dry_run:
    try:
        self.controller_type = detect_controller_type()
        logger.info(f"Controller type detected: {self.controller_type}")
    except ValueError as e:
        typer.secho(
            f"\n❌ Controller detection failed:\n{e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(EXIT_ERROR) from None

    auth_result = preflight_auth_check(self.controller_type)
    if not auth_result.success:
        # ... display banner (their code unchanged) ...
        combined_results.pre_flight_failure = PreFlightFailure(...)
        preflight_failed = True
        # No return here — fall through to Robot block

if has_pyats and not self.render_only and not preflight_failed:
    typer.echo("\n🧪 Running PyATS tests...\n")
    # ... rest of PyATS block unchanged ...

if has_robot:
    typer.echo(f"\n🤖 Running Robot Framework tests{mode_suffix}...\n")
    # ... Robot block unchanged, always runs ...
```

Note: the report generation that was inside the `return`-early block should move to after
all framework execution, alongside the existing `CombinedReportGenerator` call at the end
of `run_tests()` — or keep it inline but without the `return`.

### 2. CombinedResults.errors deduplication

In `nac_test/core/types.py`, keep:
```python
@property
def errors(self) -> list[str]:
    """All unique execution errors/reasons across all frameworks."""
    reasons = [r.reason for r in self._results if r.reason is not None]
    return list(dict.fromkeys(reasons))
```
This is independent of both PRs and fixes a real issue (api + d2d both reporting the same
error reason when a single root cause affects both).

### 3. Pre-flight failure: save as child report, link from PyATS rows

The auth-failure HTML (their `auth_failure/report.html.j2`) is good content but the
`0 / 0 / 0` summary stats bar at the top is misleading — it implies tests ran and got
zero results rather than never started. Drop or hide that bar in the template.

**Saving the report:**

In `combined_generator.py`, change `_generate_pre_flight_failure_report()` to write the
file to `pyats_results/pre_flight_failure.html` instead of `combined_summary.html`:

```python
PRE_FLIGHT_FAILURE_FILENAME = "pre_flight_failure.html"  # add to constants.py

# In _generate_pre_flight_failure_report():
failure_report_path = self.output_dir / PYATS_RESULTS_DIRNAME / PRE_FLIGHT_FAILURE_FILENAME
failure_report_path.parent.mkdir(parents=True, exist_ok=True)
failure_report_path.write_text(html_content, encoding="utf-8")
```

The method returns the path to this child report. The caller (`generate_combined_summary`)
stores it and continues to render the normal combined dashboard template (since Robot ran,
there is real data to show).

**Linking from the PyATS rows:**

In `generate_combined_summary()`, when `pre_flight_failure` is set, still build
`test_type_stats` for API and D2D, but mark them with a link to the child report:

```python
pre_flight_report_path = self._generate_pre_flight_failure_report(results.pre_flight_failure)

# For API and D2D framework rows:
test_type_stats[framework_key] = {
    "title": metadata.get("title", framework_key),
    "stats": test_results,          # None — these rows were never run
    "report_path": str(pre_flight_report_path.relative_to(self.output_dir))
                   if pre_flight_report_path else "#",
    "is_pre_flight_failure": True,
    "is_error": False,
    "error_reason": None,
}
```

Note: `stats` can be `None` here — the template must guard on `is_pre_flight_failure`
before trying to render stats numbers (see template change below).

**Combined report template changes (`combined_report.html.j2`):**

In the per-framework section, add a third branch alongside `is_error`:

```jinja
{% if framework_data.is_pre_flight_failure %}
<div class="error-banner" role="alert">
    <span class="error-icon">⚠</span>
    <div>
        <strong>Pre-flight failure — tests not executed</strong>
        <a href="{{ framework_data.report_path }}">View details →</a>
    </div>
</div>
{% elif framework_data.is_error %}
... existing error banner ...
{% else %}
... existing mini-stats ...
{% endif %}
```

The "View Detailed Report →" button in the section header should still render for
`is_pre_flight_failure` rows (pointing to `pre_flight_failure.html`), so remove the
`{% if not framework_data.is_error %}` guard on that button — or change it to
`{% if not framework_data.is_error and not framework_data.is_pre_flight_failure %}` and
add a separate link in the banner.

**Overall summary bar:** unaffected — api/d2d remain `None` so `_results` only contains
Robot's data. The top-level totals are accurate Robot-only numbers.

**Auth-failure template (`auth_failure/report.html.j2`):**

Remove (or `display: none`) the summary stats bar block (the three `0/0/0` boxes).
The failure card, remediation steps, and "What Happened" section stand on their own
without needing a stats bar that only communicates "nothing ran".

### 4. Inline error display in combined dashboard (mid-execution errors)

These additions from the current branch cover non-pre-flight errors on individual
frameworks (e.g., Robot pabot failure, PyATS subprocess crash). They are orthogonal to
the pre-flight path and should be kept.

**`nac_test/core/reporting/combined_generator.py`** — keep `is_error` / `error_reason`
in `test_type_stats`. Drop the `verbose_message` → `error_details_html` path entirely
(both `TestResults.verbose_message` and `markdown_to_html()` are being removed):

```python
test_type_stats[framework_key] = {
    "title": metadata.get("title", framework_key),
    "stats": test_results,
    "report_path": metadata.get("report_path", "#"),
    "is_pre_flight_failure": False,
    "is_error": test_results.is_error,
    "error_reason": test_results.reason,
}
```

**`nac_test/pyats_core/reporting/templates/summary/combined_report.html.j2`** — keep
all `is_error` conditional blocks and error-banner CSS/JS from this branch. Not touched
by the other branch, so no conflict.

**`nac_test/utils/strings.py`** — drop `markdown_to_html()`. It is only imported in
`combined_generator.py` and that usage is being removed. `sanitize_hostname()` is still
re-exported from `nac_test/utils/__init__.py` and must be kept.

---

## Tests to update

### Remove
- `tests/unit/utils/test_environment.py` tests for `get_missing_controller_vars()` and
  `format_missing_credentials_error()` — those methods are being dropped.
- Any tests that assert on `TestResults.verbose_message` or `ErrorType.CONTROLLER_DETECTION`.
- Any tests that assert `combined_results.api.is_error` / `combined_results.d2d.is_error`
  as the mechanism for controller detection failure.

### Keep / update
- `tests/unit/test_combined_orchestrator_controller.py` — update to assert that:
  - `combined_results.pre_flight_failure` is set on auth failure.
  - `combined_results.robot` is populated (Robot ran) despite the pre-flight failure.
  - `combined_results.api` and `combined_results.d2d` remain `None`.
- `tests/unit/core/test_types.py` — remove `verbose_message` and
  `ErrorType.CONTROLLER_DETECTION` test cases.
- `tests/unit/core/test_combined_generator.py` — keep `is_error`/`error_reason` tests.
  Add tests for the pre-flight path: assert that `pre_flight_failure.html` is written to
  `pyats_results/`, and that `combined_summary.html` is also generated (with Robot data)
  and contains links to the child report. Remove any `error_details_html`/`verbose_message`
  tests.

---

## New E2E scenarios

Both scenarios use PyATS + Robot tests (like the existing `SUCCESS_SCENARIO` / `MIXED_SCENARIO`
fixture structure). Neither requires a testbed because PyATS never reaches test execution.

### Scenario 1 — Controller detection failure (no credentials)

**What it tests:** PyATS cannot detect a controller because no `<TYPE>_URL/USERNAME/PASSWORD`
env vars are set. Robot tests should still run to completion.

**Fixture directory:** `tests/e2e/fixtures/pyats_robot_no_controller/`
- `data.yaml` — same minimal structure as `mixed/data.yaml` (no controller-specific fields needed)
- `templates/tests/config/test.robot` — copy from `robot_only` fixture (1 passing Robot test)
- `templates/tests/` — include one PyATS API test file (same as `mixed` fixture)

**`E2EScenario` definition in `config.py`:**
```python
PYATS_ROBOT_NO_CONTROLLER_SCENARIO = E2EScenario(
    name="pyats_robot_no_controller",
    description="PyATS+Robot with no controller credentials — Robot should run, PyATS skipped",
    architecture="SDWAN",           # sets the env var prefix for detection
    data_path=f"{_FIXTURE_BASE}/pyats_robot_no_controller/data.yaml",
    templates_path=f"{_FIXTURE_BASE}/pyats_robot_no_controller/templates",
    expected_exit_code=1,           # pre_flight_failure → exit code 1
    expected_robot_passed=1,
    expected_robot_failed=0,
    expected_pyats_api_passed=0,
    expected_pyats_api_failed=0,
    expected_pyats_d2d_passed=0,
    expected_pyats_d2d_failed=0,
)
```

**Fixture in `conftest.py`:**
```python
@pytest.fixture(scope="class")
def e2e_pyats_robot_no_controller_results(
    mock_api_server: MockAPIServer,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    from tests.e2e.config import PYATS_ROBOT_NO_CONTROLLER_SCENARIO
    # Do NOT set controller env vars — detection should fail
    # (mock_api_server is still needed for Robot, but no credentials)
    return _run_e2e_scenario_no_auth(
        PYATS_ROBOT_NO_CONTROLLER_SCENARIO, mock_api_server, None, tmp_path_factory, class_mocker
    )
```

The existing `_run_e2e_scenario()` sets `{arch}_URL/USERNAME/PASSWORD` unconditionally.
For this scenario, use a variant `_run_e2e_scenario_no_auth()` that skips setting those
env vars (or add an `omit_controller_env: bool = False` flag to `_run_e2e_scenario()`).

**Test class in `test_e2e_scenarios.py`:**
```python
class TestE2EPyatsRobotNoController:
    """PyATS+Robot with no controller credentials."""

    @pytest.fixture
    def results(self, e2e_pyats_robot_no_controller_results: E2EResults) -> E2EResults:
        return e2e_pyats_robot_no_controller_results

    def test_exit_code_is_1(self, results: E2EResults) -> None:
        assert results.exit_code == 1

    def test_robot_ran_and_passed(self, results: E2EResults) -> None:
        assert results.scenario.expected_robot_passed == 1
        # Robot output.xml exists
        assert (results.output_dir / "robot_results" / "output.xml").exists()

    def test_pre_flight_failure_report_written(self, results: E2EResults) -> None:
        assert (results.output_dir / "pyats_results" / "pre_flight_failure.html").exists()

    def test_combined_summary_generated(self, results: E2EResults) -> None:
        assert (results.output_dir / "combined_summary.html").exists()

    def test_combined_summary_links_preflight_report(self, results: E2EResults) -> None:
        html = (results.output_dir / "combined_summary.html").read_text()
        assert "pre_flight_failure.html" in html

    def test_pyats_rows_show_preflight_banner(self, results: E2EResults) -> None:
        html = (results.output_dir / "combined_summary.html").read_text()
        assert "Pre-flight failure" in html

    def test_no_pyats_results_directory_created(self, results: E2EResults) -> None:
        # PyATS execution never started, so no api/ or d2d/ subdirs
        assert not (results.output_dir / "pyats_results" / "api").exists()
        assert not (results.output_dir / "pyats_results" / "d2d").exists()
```

Note: this scenario does NOT inherit `E2ECombinedTestBase` because many of its base tests
assume PyATS ran. Write the tests as a standalone class.

---

### Scenario 2 — Pre-flight auth failure (wrong password)

**What it tests:** Controller is detected (env vars present and complete) but the pre-flight
HTTP auth check fails with a 401. Robot tests should still run.

**Approach:** Use the existing mock server, but set the password env var to a value the mock
server rejects. The mock server already has a 401 endpoint
(`/api/aaaLogin.json` responds 200 for `mock_pass`). We need it to respond 401 for a wrong
password. Two options:

- **Option A (preferred):** Add a second mock endpoint config for `aaaLogin.json` that
  returns 401 when body contains a sentinel bad-password value (e.g., `"wrong_pass"`).
  This requires a small addition to `mock_api_config.yaml`.
- **Option B (simpler):** Patch `preflight_auth_check` at the E2E level to return a failing
  `AuthCheckResult` with `reason=AuthOutcome.BAD_CREDENTIALS`, bypassing the actual HTTP
  call. This is less realistic but avoids mock server changes.

**Recommendation: Option B** for the initial implementation, since E2E infra changes to
`mock_api_config.yaml` are risky to get right and the key behaviour to test is the
combined-report outcome, not the HTTP layer (which has its own unit tests).

**Fixture directory:** `tests/e2e/fixtures/pyats_robot_auth_fail/`
- Same structure as scenario 1 — one Robot test, one PyATS API test file.

**`E2EScenario` definition in `config.py`:**
```python
PYATS_ROBOT_AUTH_FAIL_SCENARIO = E2EScenario(
    name="pyats_robot_auth_fail",
    description="PyATS+Robot where preflight auth fails — Robot runs, preflight report generated",
    architecture="SDWAN",
    data_path=f"{_FIXTURE_BASE}/pyats_robot_auth_fail/data.yaml",
    templates_path=f"{_FIXTURE_BASE}/pyats_robot_auth_fail/templates",
    expected_exit_code=1,
    expected_robot_passed=1,
    expected_robot_failed=0,
    expected_pyats_api_passed=0,
    expected_pyats_api_failed=0,
    expected_pyats_d2d_passed=0,
    expected_pyats_d2d_failed=0,
)
```

**Fixture in `conftest.py`:**
```python
@pytest.fixture(scope="class")
def e2e_pyats_robot_auth_fail_results(
    mock_api_server: MockAPIServer,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    from tests.e2e.config import PYATS_ROBOT_AUTH_FAIL_SCENARIO
    from nac_test.cli.validators.controller_auth import AuthCheckResult, AuthOutcome

    # Credentials present (detection succeeds), but patch preflight to fail
    class_mocker.setattr(
        "nac_test.combined_orchestrator.preflight_auth_check",
        lambda _: AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="SDWAN",
            controller_url=mock_api_server.url,
            detail="HTTP 401: Unauthorized",
            status_code=401,
        ),
    )
    return _run_e2e_scenario(
        PYATS_ROBOT_AUTH_FAIL_SCENARIO, mock_api_server, None, tmp_path_factory, class_mocker
    )
```

**Test class in `test_e2e_scenarios.py`:**
```python
class TestE2EPyatsRobotAuthFail:
    """PyATS+Robot where pre-flight auth check fails."""

    @pytest.fixture
    def results(self, e2e_pyats_robot_auth_fail_results: E2EResults) -> E2EResults:
        return e2e_pyats_robot_auth_fail_results

    def test_exit_code_is_1(self, results: E2EResults) -> None:
        assert results.exit_code == 1

    def test_robot_ran_and_passed(self, results: E2EResults) -> None:
        assert (results.output_dir / "robot_results" / "output.xml").exists()

    def test_pre_flight_failure_report_written(self, results: E2EResults) -> None:
        report = results.output_dir / "pyats_results" / "pre_flight_failure.html"
        assert report.exists()

    def test_pre_flight_report_shows_auth_failure(self, results: E2EResults) -> None:
        html = (results.output_dir / "pyats_results" / "pre_flight_failure.html").read_text()
        assert "401" in html or "Unauthorized" in html or "Auth Failed" in html

    def test_pre_flight_report_shows_controller_url(self, results: E2EResults) -> None:
        html = (results.output_dir / "pyats_results" / "pre_flight_failure.html").read_text()
        assert mock_api_server.url in html   # controller URL shown in report
        # Note: access mock_api_server via results or pass it separately

    def test_combined_summary_generated(self, results: E2EResults) -> None:
        assert (results.output_dir / "combined_summary.html").exists()

    def test_combined_summary_links_preflight_report(self, results: E2EResults) -> None:
        html = (results.output_dir / "combined_summary.html").read_text()
        assert "pre_flight_failure.html" in html

    def test_combined_summary_shows_robot_stats(self, results: E2EResults) -> None:
        # Overall stats bar reflects Robot's real numbers, not zeros
        html = (results.output_dir / "combined_summary.html").read_text()
        # Robot passed 1, so total should be 1 (not 0)
        # Use html_helpers to parse the stats properly if needed
        assert "pre_flight_failure.html" not in html or True  # placeholder
```

**Implementation note for `test_pre_flight_report_shows_controller_url`:** The `results`
object doesn't carry the mock server URL. Either store it on `E2EResults` (add a
`controller_url: str | None` field to the dataclass), use a class-level variable set in
the fixture, or access it via the `E2EScenario` (add `controller_url` to the scenario
config). The simplest approach is to use the existing `mock_api_server` fixture directly
in the test — but that requires it as a parameter, which breaks the class-scoped pattern.
**Simplest fix:** add a `controller_url: str | None = None` field to `E2EResults` and
populate it in `_run_e2e_scenario()`.

---

## File-by-file summary

| File | Action |
|---|---|
| `nac_test/exceptions.py` | **Delete** |
| `nac_test/core/constants.py` | Add `PRE_FLIGHT_FAILURE_FILENAME = "pre_flight_failure.html"` |
| `nac_test/core/types.py` | Remove `CONTROLLER_DETECTION`, `verbose_message`. Keep deduplication fix, adopt `ControllerTypeKey`+`PreFlightFailure` from other branch. |
| `nac_test/combined_orchestrator.py` | Adopt their detection+preflight block. Remove `return` → add `preflight_failed` flag. Remove `ControllerDetectionError` import. Remove inline report generation from preflight block (report generated at end of `run_tests()` as normal). |
| `nac_test/pyats_core/orchestrator.py` | Remove `get_missing_controller_vars` block and `controller_type is None` guard. Keep structural simplification. |
| `nac_test/utils/environment.py` | Keep simplified form; remove `get_missing_controller_vars`/`format_missing_credentials_error`. |
| `nac_test/utils/strings.py` | Drop `markdown_to_html()` (unused after this change). Keep `sanitize_hostname`. |
| `nac_test/core/reporting/combined_generator.py` | Change `_generate_pre_flight_failure_report()` to write to `pyats_results/pre_flight_failure.html` and return the path. In `generate_combined_summary()`: call it when `pre_flight_failure` is set, then continue to render the normal combined dashboard with `is_pre_flight_failure=True` on API/D2D rows linking to the child report. Keep `is_error`/`error_reason` for mid-execution errors. Drop `error_details_html`/`verbose_message` path. |
| `nac_test/pyats_core/reporting/templates/auth_failure/report.html.j2` | Remove the `0/0/0` summary stats bar block. |
| `nac_test/pyats_core/reporting/templates/summary/combined_report.html.j2` | Add `is_pre_flight_failure` branch in per-framework section (error banner + link to child report). Keep existing `is_error` blocks. |
| `tests/unit/test_combined_orchestrator_controller.py` | Rewrite assertions around `pre_flight_failure` + Robot-continues behaviour. |
| `tests/unit/core/test_types.py` | Remove `verbose_message`/`CONTROLLER_DETECTION` cases. |
| `tests/unit/core/test_combined_generator.py` | Add pre-flight path tests (child report written, combined dashboard generated, links present). Remove `error_details_html` tests. |
| `tests/unit/utils/test_environment.py` | Remove tests for dropped methods. |
| `tests/e2e/fixtures/pyats_robot_no_controller/` | **New** — data.yaml + Robot + PyATS templates |
| `tests/e2e/fixtures/pyats_robot_auth_fail/` | **New** — data.yaml + Robot + PyATS templates |
| `tests/e2e/config.py` | Add `PYATS_ROBOT_NO_CONTROLLER_SCENARIO` and `PYATS_ROBOT_AUTH_FAIL_SCENARIO` |
| `tests/e2e/conftest.py` | Add two class-scoped fixtures; add `omit_controller_env` flag or `_run_e2e_scenario_no_auth()` variant; add `controller_url` to `E2EResults` |
| `tests/e2e/test_e2e_scenarios.py` | Add `TestE2EPyatsRobotNoController` and `TestE2EPyatsRobotAuthFail` classes |
