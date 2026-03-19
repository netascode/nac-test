# PR #612 Clean Implementation Plan

**Issue:** #612 - Continue Robot tests when PyATS pre-flight fails  
**Base branch:** `release/pyats-integration-v1.1-beta`  
**New branch:** `fix/612-preflight-continue-robot`

## Goal

When PyATS pre-flight fails (controller detection or auth), **continue running Robot tests** instead of exiting early. Generate a pre-flight failure report and link it from the combined summary.

### Current Behavior (on parent branch)
- Controller detection fails → `typer.Exit(EXIT_ERROR)` — nothing runs
- Pre-flight auth fails → generates report, `return combined_results` — Robot blocked

### Target Behavior
- Controller detection fails → set `PreFlightFailure`, skip PyATS, **run Robot**
- Pre-flight auth fails → set `PreFlightFailure`, skip PyATS, **run Robot**
- Generate `pyats_results/pre_flight_failure.html` as child report
- Generate `combined_summary.html` with Robot stats + links to pre-flight report
- Exit code = 1 (failure due to pre-flight issue)

---

## Implementation Steps

### Phase 1: Extend Types for Detection Failures

**File:** `nac_test/core/types.py`

Add an Enum for failure types and update `PreFlightFailure`:

```python
class PreFlightFailureType(Enum):
    """Type of pre-flight failure that prevented PyATS execution."""
    AUTH = "auth"
    UNREACHABLE = "unreachable"
    DETECTION = "detection"


@dataclass
class PreFlightFailure:
    """Details of a pre-flight failure that prevented PyATS execution.
    
    Attributes:
        failure_type: Category of failure.
        controller_type: Controller identifier, or None for detection failures.
        controller_url: URL that was tested, or None for detection failures.
        detail: Human-readable error description.
        status_code: HTTP status code, or None for non-HTTP failures.
    """
    failure_type: PreFlightFailureType  # Use Enum instead of Literal
    controller_type: ControllerTypeKey | None  # Allow None for detection failures
    controller_url: str | None  # Allow None for detection failures
    detail: str
    status_code: int | None = None
```

**File:** `nac_test/core/constants.py`

Add constant for the pre-flight failure report filename:

```python
PRE_FLIGHT_FAILURE_FILENAME = "pre_flight_failure.html"
```

---

### Phase 2: Update CombinedOrchestrator

**File:** `nac_test/combined_orchestrator.py`

Change the pre-flight block to **not exit** on detection failure and **not return** on auth failure:

```python
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
        # Instead of Exit, record failure and continue to Robot
        combined_results.pre_flight_failure = PreFlightFailure(
            failure_type="detection",
            controller_type=None,
            controller_url=None,
            detail=str(e),
        )
        preflight_failed = True

    if not preflight_failed and self.controller_type is not None:
        auth_result = preflight_auth_check(self.controller_type)
        if not auth_result.success:
            # ... display banner (unchanged) ...
            combined_results.pre_flight_failure = PreFlightFailure(...)
            preflight_failed = True
            # REMOVE: the return statement and inline report generation

# Run PyATS only if pre-flight passed
if has_pyats and not self.render_only and not preflight_failed:
    # ... PyATS execution (unchanged) ...

# Robot always runs (unchanged)
if has_robot:
    # ... Robot execution (unchanged) ...
```

**Key changes:**
1. Replace `raise typer.Exit(EXIT_ERROR)` with `PreFlightFailure` + `preflight_failed = True`
2. Remove the `return combined_results` after auth failure banner
3. Add `not preflight_failed` condition to PyATS execution block
4. Remove `EXIT_ERROR` import if no longer used

---

### Phase 3: Update Report Generator

**File:** `nac_test/core/reporting/combined_generator.py`

#### 3a. Change `_generate_pre_flight_failure_report()` to write child report

```python
def _generate_pre_flight_failure_report(self, failure: PreFlightFailure) -> Path | None:
    """Generate pre-flight failure report as a child report.
    
    Writes to pyats_results/pre_flight_failure.html (not combined_summary.html).
    """
    failure_report_path = (
        self.output_dir / PYATS_RESULTS_DIRNAME / PRE_FLIGHT_FAILURE_FILENAME
    )
    failure_report_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Handle None controller_type/url for detection failures
    display_name = get_display_name(failure.controller_type) if failure.controller_type else None
    env_var_prefix = get_env_var_prefix(failure.controller_type) if failure.controller_type else None
    host = extract_host(failure.controller_url) if failure.controller_url else None
    curl_example = (
        _get_curl_example(failure.controller_type, failure.controller_url)
        if failure.controller_type and failure.controller_url
        else None
    )
    
    # ... render template with these potentially-None values ...
    
    failure_report_path.write_text(html_content, encoding="utf-8")
    return failure_report_path
```

#### 3b. Update `generate_combined_summary()` to handle pre-flight + Robot results

```python
def generate_combined_summary(self, results: CombinedResults | None = None) -> Path | None:
    pre_flight_report_path: Path | None = None
    
    if results is not None and results.pre_flight_failure is not None:
        pre_flight_report_path = self._generate_pre_flight_failure_report(
            results.pre_flight_failure
        )
        
        # If only pre-flight failed (no Robot), hard-link report to combined_summary
        if results.robot is None:
            if pre_flight_report_path:
                combined_path = self.output_dir / COMBINED_SUMMARY_FILENAME
                combined_path.hardlink_to(pre_flight_report_path)
                return combined_path
            return None
    
    # Build test_type_stats for template
    test_type_stats = {}
    
    if results is not None:
        # If pre-flight failed, mark API/D2D rows with link to pre-flight report
        if results.pre_flight_failure is not None and pre_flight_report_path:
            relative_path = str(pre_flight_report_path.relative_to(self.output_dir))
            for framework_key in ("API", "D2D"):
                metadata = FRAMEWORK_METADATA.get(framework_key, {})
                test_type_stats[framework_key] = {
                    "title": metadata.get("title", framework_key),
                    "stats": None,
                    "report_path": relative_path,
                    "is_pre_flight_failure": True,
                    "is_error": False,
                    "error_reason": None,
                }
        
        # Process actual results (Robot, or API/D2D if they ran)
        for framework_key, test_results in [("API", results.api), ("D2D", results.d2d), ("Robot", results.robot)]:
            if framework_key in test_type_stats:
                continue  # Already handled by pre-flight
            if test_results is None:
                continue
            
            metadata = FRAMEWORK_METADATA.get(framework_key, {})
            test_type_stats[framework_key] = {
                "title": metadata.get("title", framework_key),
                "stats": test_results,
                "report_path": metadata.get("report_path", "#"),
                "is_pre_flight_failure": False,
                "is_error": test_results.is_error,
                "error_reason": test_results.reason,
            }
    
    # ... render combined_report.html.j2 template ...
```

---

### Phase 4: Update Templates

**File:** `nac_test/pyats_core/reporting/templates/auth_failure/report.html.j2`

Handle `None` values for detection failures:

```jinja
{% if failure.failure_type == "detection" %}
    <h2>Controller Detection Failed</h2>
    <p>{{ failure.detail }}</p>
    {# No controller URL or curl example available #}
{% else %}
    <h2>Authentication Failed</h2>
    <p>Controller: {{ display_name }} at {{ host }}</p>
    {# ... existing auth failure content ... #}
{% endif %}
```

**File:** `nac_test/pyats_core/reporting/templates/summary/combined_report.html.j2`

Add `is_pre_flight_failure` branch in per-framework section:

```jinja
{% for framework_key, framework_data in test_type_stats.items() %}
<div class="framework-section">
    <h3>{{ framework_data.title }}</h3>
    
    {% if framework_data.is_pre_flight_failure %}
    <div class="error-banner preflight-failure">
        <span class="error-icon">⚠️</span>
        <div>
            <strong>Pre-flight failure — tests not executed</strong>
            <a href="{{ framework_data.report_path }}">View details →</a>
        </div>
    </div>
    {% elif framework_data.is_error %}
    <div class="error-banner">
        <span class="error-icon">❌</span>
        <span>{{ framework_data.error_reason }}</span>
    </div>
    {% else %}
    {# Normal stats display #}
    {% endif %}
</div>
{% endfor %}
```

---

### Phase 5: Cleanup Redundant Code

**Files to delete:**
- `nac_test/exceptions.py` — `ControllerDetectionError` no longer used
- `nac_test/utils/environment.py` — `EnvironmentValidator` no longer used

**Files to update:**
- `nac_test/utils/__init__.py` — remove `EnvironmentValidator` export
- `nac_test/_env.py` — remove reference to deleted module in docstring
- `nac_test/pyats_core/orchestrator.py` — remove `EnvironmentValidator` import and usage

---

### Phase 6: Update Unit Tests

**Remove:**
- `tests/unit/utils/test_environment.py` — tests for deleted module

**Update:**
- `tests/unit/test_combined_orchestrator_controller.py` — test pre-flight failure + Robot continues
- `tests/unit/core/test_combined_generator.py` — test child report generation, None handling
- `tests/pyats_core/common/test_base_test_controller_detection.py` — update for ValueError (not ControllerDetectionError)

---

### Phase 7: Add E2E Tests

#### Scenario 1: No Controller Credentials

**Fixture:** `tests/e2e/fixtures/pyats_robot_no_controller/`
- Minimal Robot test + PyATS test file
- No controller env vars set

**Expected behavior:**
- Detection fails → pre-flight failure recorded
- Robot runs and passes
- `pyats_results/pre_flight_failure.html` generated
- `combined_summary.html` links to pre-flight report
- Exit code = 1

#### Scenario 2: Auth Failure (401)

**Fixture:** `tests/e2e/fixtures/pyats_robot_auth_fail/`
- Minimal Robot test + PyATS test file
- Controller env vars set, but auth patched to fail

**Expected behavior:**
- Detection succeeds, auth fails → pre-flight failure recorded  
- Robot runs and passes
- `pyats_results/pre_flight_failure.html` generated
- `combined_summary.html` links to pre-flight report
- Exit code = 1

**Config changes (`tests/e2e/config.py`):**
- Add `skip_controller_setup: bool = False` to `E2EScenario`
- Add scenario definitions

**Fixture changes (`tests/e2e/conftest.py`):**
- Use `scenario.skip_controller_setup` to skip env var setup
- Patch `preflight_auth_check` for auth failure scenario

---

## Verification Checklist

- [ ] All existing tests pass: `uv run pytest -n auto --dist loadscope tests`
- [ ] E2E scenario 1 (no controller) passes
- [ ] E2E scenario 2 (auth failure) passes
- [ ] `combined_summary.html` shows Robot stats when pre-flight fails
- [ ] `pyats_results/pre_flight_failure.html` is generated
- [ ] Exit code is 1 when pre-flight fails
- [ ] No unrelated changes (check diff against parent)

---

## Commit Strategy

Single focused commit:
```
feat(e2e): continue Robot tests on PyATS pre-flight failure (#612)

When controller detection fails (no credentials) or pre-flight auth
fails (401), the orchestrator now continues to run Robot tests and
generates a pre-flight failure report instead of exiting early.

Changes:
- Extend PreFlightFailure type to support detection failures (no URL)
- Update CombinedReportGenerator to handle None controller_type/url
- Update auth_failure template to support detection failure rendering
- Add E2E test scenarios for pre-flight failures
- Remove unused EnvironmentValidator and exceptions.py

Closes #612
```
