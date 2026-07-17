# Controller Resolution Refactor — Architecture Plan

## Problem Statement

Controller credentials are validated and controller/auth pre-flight checks are performed across multiple layers. Responsibility boundaries are unclear. PR #847 (credential sets + multi-method support for SD-WAN JWT tokens) increases complexity and makes drift between layers more likely.

### Current Flow (Before Refactor)

```
CLI main()
  ├─ validate_aci_defaults(data)
  ├─ DataMerger.merge_data_files()
  └─ CombinedOrchestrator.run_tests()
       ├─ _discover_test_types() → has_pyats, has_robot
       ├─ IF has_pyats AND NOT render_only AND NOT dry_run:
       │    └─ _run_pre_flight_checks()                      ← DETECTION #1
       │         ├─ detect_controller_type()                  (utils/controller.py)
       │         │    └─ _find_credential_sets()
       │         └─ preflight_auth_check()                    (cli/validators/controller_auth.py)
       ├─ IF has_pyats AND NOT preflight_failed:
       │    └─ PyATSOrchestrator(controller_type=...).run_tests()
       │         ├─ validate_environment()                    ← REDUNDANT CHECK
       │         │    └─ EnvironmentValidator.validate_controller_env()
       │         │         └─ re-checks same credential sets  (utils/environment.py)
       │         ├─ discover_pyats_tests()
       │         ├─ IF dry_run: return not_run
       │         └─ ELSE: launch subprocess(es)
       │              └─ base_test.setup()                    ← DETECTION #3
       │                   ├─ detect_controller_type()        (re-derives in every worker)
       │                   └─ reads {TYPE}_USERNAME/_PASSWORD  (hardcoded env var names)
       │                        └─ auth adapter (e.g. SDWANManagerAuth)
       │                             └─ get_matched_credential_set()  ← DETECTION #4
       └─ IF has_robot:
            └─ RobotOrchestrator.run_tests()  (no controller checks)
```

Problems:
- **4 detection/validation points** in a single PyATS run
- `validate_controller_env()` calls `sys.exit()` directly from utility code
- `EnvironmentValidator.validate_controller_env()` has delayed import from `controller.py` (circular dependency smell)
- Subprocess re-derives controller type independently — no context passed from parent
- `get_matched_credential_set()` called again inside subprocess auth adapter
- Rich per-variable UX feedback (present/missing env vars) was lost in PR #847 because CredentialSetStatus complexity grew too much with multi-credential-set support

### New Flow (After Refactor)

```
CLI main()
  ├─ validate_aci_defaults(data)
  ├─ DataMerger.merge_data_files()
  └─ CombinedOrchestrator.run_tests()
       ├─ _discover_test_types() → has_pyats, has_robot
       ├─ IF (has_pyats OR has_robot) AND NOT render_only AND NOT dry_run:
       │    └─ _run_pre_flight_checks()
       │         ├─ ctx = resolve_controller()               ← SINGLE RESOLUTION
       │         │    (core/controller.py — raises typed exceptions on failure)
       │         ├─ except ResolutionError:
       │         │    format_resolution_error(e, REGISTRY)
       │         │    → record PreFlightFailure, return
       │         ├─ result = preflight_auth_check(ctx)       ← AUTH REACHABILITY
       │         │    (core/controller_auth.py — HTTP auth, populates AuthCache)
       │         └─ self.controller_context = ctx             ← SAVED FOR LATER USE
       ├─ IF has_pyats AND NOT preflight_failed:
       │    └─ PyATSOrchestrator(controller_context=ctx).run_tests()
       │         │                                   ← RECEIVES ControllerContext
       │         ├─ discover_pyats_tests()            ← NO validate_environment()
       │         ├─ IF dry_run: return not_run
       │         └─ ELSE: launch subprocess(es)
       │              │  env = os.environ.copy()
       │              │  env["NAC_TEST_CONTROLLER_CONTEXT"] = ctx.to_json()
       │              │                              ← SERIALIZED HERE (owns transport)
       │              └─ base_test.setup()
       │                   ├─ ctx = get_controller_context()         ← ACCESSOR
       │                   │    (from nac_test.core.controller)
       │                   └─ auth adapter (e.g. SDWANManagerAuth)
       │                        └─ uses ctx.auth_method              ← NO RE-DETECTION
       │                             → "token" → reads SDWAN_API_TOKEN
       │                             → "session" → reads SDWAN_USERNAME/PASSWORD
       │                             → checks AuthCache (populated by parent)
       └─ IF has_robot AND NOT preflight_failed:
            └─ RobotOrchestrator.run_tests()  (benefits from resolved context + AuthCache)
```

## Design Decisions

### 1. Single Source of Truth

`resolve_controller()` in `core/controller.py` is the only place that scans environment variables and determines which controller type + credential set is active. All other components consume its output — they never re-derive.

### 2. Check ≠ Enforce

Resolution returns a `ControllerContext` on success or raises typed exceptions on failure. It never calls `sys.exit()`. The orchestrator (caller) decides whether to abort, warn, or continue. This enables:
- PyATS real run: resolve → enforce → pass to PyATSOrchestrator → serialize → subprocess
- Robot real run: resolve → enforce → run (benefits from AuthCache populated during pre-flight)
- Dry-run: skip resolution entirely (no pre-flight checks, no subprocess launched)
- Render-only: skip resolution entirely
- Future: any caller can handle resolution errors differently

**Dry-run semantics:** Pre-flight checks (resolution + auth reachability) are gated by `NOT dry_run`. In dry-run mode, `controller_context` stays `None`, and no subprocess is launched — so the absence of context is never observed by workers.

### 3. Subprocess Receives, Never Re-derives

`PyATSOrchestrator` serializes the resolved `ControllerContext` as inline JSON in `NAC_TEST_CONTROLLER_CONTEXT` before launching subprocesses (following the existing `DEVICE_INFO` pattern). The subprocess accesses it via the `get_controller_context()` accessor function — never by parsing the env var directly.

**Transitional fallback:** To avoid coupling the release of `nac-test` and `nac-test-pyats-common`, the subprocess retains a fallback to current `main()` behavior (`detect_controller_type()` / `get_matched_credential_set()`) when `NAC_TEST_CONTROLLER_CONTEXT` is absent. This allows shipping interim bug-fix releases of either package independently. The fallback is explicitly temporary — once both packages are released with the new API, the fallback path is removed (Phase 3).

`get_matched_credential_set()` has one in-repo consumer (`sdwan/auth.py`) that migrates in lockstep. The fallback exists solely to decouple *release timing*, not to support a permanent dual-path.

**Important:** Only controller type *detection/derivation* moves to the parent. Actual secret values (passwords, tokens, URLs) remain env var reads in the subprocess — they are never serialized into `ControllerContext`.

### 3a. Subprocess API: `get_controller_context()`

`nac-test-pyats-common` already tightly couples to `nac-test` (inherits `BaseTest`, `SSHTestBase`; uses `AuthCache`, `execute_auth_subprocess`). Adding one more function import is consistent with existing patterns.

The accessor function lives in `nac-test` and encapsulates the transport mechanism:

```python
# nac_test/core/controller.py

_cached_context: ControllerContext | None = None

def get_controller_context() -> ControllerContext:
    """Get the resolved controller context.

    Works in both parent and subprocess:
    - Parent: returns cached result from resolve_controller()
    - Subprocess: deserializes from NAC_TEST_CONTROLLER_CONTEXT env var
    - Fallback (transitional): re-derives via detect_controller_type() if env var absent
    """
    global _cached_context
    if _cached_context is not None:
        return _cached_context
    raw = os.environ.get("NAC_TEST_CONTROLLER_CONTEXT")
    if raw:
        _cached_context = ControllerContext.from_json(raw)
        return _cached_context
    # Transitional fallback: supports running with older nac-test that doesn't
    # serialize context. Remove once both packages ship with the new API.
    import warnings
    warnings.warn(
        "NAC_TEST_CONTROLLER_CONTEXT not set — falling back to detect_controller_type(). "
        "This fallback will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2,
    )
    controller_type = _detect_controller_type()
    if controller_type:
        _cached_context = ControllerContext(
            controller_type=controller_type,
            auth_method=_infer_auth_method(controller_type),
        )
        return _cached_context
    raise RuntimeError(
        "No controller context available. "
        "Was resolve_controller() called or NAC_TEST_CONTROLLER_CONTEXT set?"
    )
```

Usage in `nac-test-pyats-common`:
```python
from nac_test.core.controller import get_controller_context

ctx = get_controller_context()
auth_method = ctx.auth_method     # "token" or "session"
controller_type = ctx.controller_type  # "SDWAN", "ACI", etc.
```

This follows the same pattern as the existing `get_matched_credential_set()` call — a simple function import from `nac_test`, no knowledge of env var names or JSON format.

### 4. Auth Reachability in Parent Only

`preflight_auth_check()` runs in the parent after successful resolution. It populates `AuthCache` (file-based, cross-process). The subprocess never performs auth reachability — it trusts the parent's pre-flight and benefits from the cached auth tokens.

### 5. EnvironmentValidator Dissolved

The `EnvironmentValidator` class is removed. `get_bool()`, `get_int()`, and `get_with_default()` have zero callers and duplicate existing functions in `_env.py` — they are deleted outright. `check_required_vars()` and `format_missing_vars_error()` remain as module-level functions in `utils/environment.py` if needed. Controller-specific validation (`validate_controller_env`) is deleted — its job is fully absorbed by `resolve_controller()` + orchestrator enforcement.

### 6. Controller Domain Moves to `core/`

`controller.py` and `controller_auth.py` move from `utils/` to `core/`. The controller detection/resolution is core domain logic, not a generic utility. `CredentialSet`, `ControllerConfig`, `CONTROLLER_REGISTRY`, and `resolve_controller()` are central to nac-test's purpose.

## Component Ownership

| Component | Location | Owns | Consumes |
|-----------|----------|------|----------|
| `ControllerContext` | `core/types.py` | Serializable resolution result: `controller_type`, `auth_method`, `to_json()`, `from_json()` | — |
| `controller.py` | `core/controller.py` | `CONTROLLER_REGISTRY`, `CredentialSet`, `ControllerConfig`, `resolve_controller()`, `get_controller_context()`, typed exceptions, `format_resolution_error()` helper | `ControllerContext` from `core/types.py` |
| `controller_auth.py` | `core/controller_auth.py` | `preflight_auth_check(ctx: ControllerContext) → AuthCheckResult` (HTTP auth, AuthCache population) | `ControllerContext`, auth adapters from `nac-test-pyats-common` |
| `environment.py` | `utils/environment.py` | Generic env var helpers as module functions (no class) | — |
| `CombinedOrchestrator` | `combined_orchestrator.py` | Calls `resolve_controller()` + `preflight_auth_check()`, formats error messages, records `PreFlightFailure`, keeps `self.controller_context`, passes it to `PyATSOrchestrator` | `ControllerContext`, `ResolutionError` subtypes |
| `PyATSOrchestrator` | `pyats_core/orchestrator.py` | Test execution. Receives `ControllerContext`, serializes to `NAC_TEST_CONTROLLER_CONTEXT` before subprocess launch. No `validate_environment()`. | `ControllerContext` (typed parameter) |
| Subprocess (`base_test.py`) | `nac-test-pyats-common` | Calls `get_controller_context()` accessor | `ControllerContext` via `nac_test.core.controller` |
| Auth adapters | `nac-test-pyats-common` | Use `get_controller_context().auth_method` to branch (token vs session). Read actual credential values from hardcoded env var names. Check AuthCache. | `get_controller_context()` from `nac_test.core.controller` |

## Typed Exceptions

```python
class ResolutionError(Exception):
    """Base for controller resolution failures."""

class NoCredentialsFound(ResolutionError):
    """No controller env vars detected at all."""

class MultipleControllersFound(ResolutionError):
    def __init__(self, controllers: list[str]):
        self.controllers = controllers

class IncompleteCredentials(ResolutionError):
    def __init__(self, partial_controllers: list[str]):
        self.partial_controllers = partial_controllers
```

## ControllerContext

```python
@dataclass(frozen=True)
class ControllerContext:
    """Resolved controller identity passed from orchestrator to subprocess."""
    controller_type: ControllerTypeKey
    auth_method: str  # from CredentialSet.auth_method (e.g., "token", "session")

    def to_json(self) -> str:
        """Serialize for NAC_TEST_CONTROLLER_CONTEXT env var."""
        return json.dumps({"controller_type": self.controller_type, "auth_method": self.auth_method})

    @classmethod
    def from_json(cls, raw: str) -> "ControllerContext":
        """Deserialize from NAC_TEST_CONTROLLER_CONTEXT env var."""
        data = json.loads(raw)
        return cls(controller_type=data["controller_type"], auth_method=data["auth_method"])
```

Minimal, extensible. New fields can be added later without breaking existing consumers (JSON deserialization ignores unknown keys).

## Env Var Contract

`NAC_TEST_CONTROLLER_CONTEXT` — inline JSON, set by `CombinedOrchestrator` after successful resolution, inherited by subprocess via `os.environ.copy()`. Follows the existing `DEVICE_INFO` pattern.

Example values:
```json
{"controller_type": "SDWAN", "auth_method": "token"}
{"controller_type": "ACI", "auth_method": "session"}
```

## Changes by File

### nac-test

| File | Action | Details |
|------|--------|---------|
| `core/types.py` | ADD | `ControllerContext` dataclass with `to_json()`/`from_json()` |
| `core/controller.py` | MOVE + REFACTOR | Move from `utils/controller.py`. Rename `detect_controller_type()` to internal `_detect_controller_type()`. Add `resolve_controller() → ControllerContext`. Add typed exception classes. Add `format_resolution_error()` helper. |
| `core/controller_auth.py` | MOVE | Move `preflight_auth_check()` from `cli/validators/controller_auth.py`. Update signature to accept `ControllerContext`. |
| `utils/environment.py` | REFACTOR | Delete `EnvironmentValidator` class. Delete `validate_controller_env()`. Delete `get_bool()`, `get_int()`, `get_with_default()` (zero callers, duplicate `_env.py`). Keep `check_required_vars()`, `format_missing_vars_error()` as module functions if needed. |
| `combined_orchestrator.py` | REFACTOR | Update `_run_pre_flight_checks()`: call `resolve_controller()`, catch `ResolutionError`, call `format_resolution_error()`, call `preflight_auth_check(ctx)`. Save `self.controller_context`. Pass context to `PyATSOrchestrator`. Update pre-flight gate to cover both PyATS and Robot test types. |
| `pyats_core/orchestrator.py` | SIMPLIFY | Remove `controller_type` parameter. Add `controller_context: ControllerContext | None = None` parameter. Remove `self.controller_type`. Remove `validate_environment()` method. Serialize `controller_context.to_json()` into subprocess env before launch. Remove import of `detect_controller_type` and `EnvironmentValidator`. |
| `cli/validators/controller_auth.py` | DELETE or REDUCE | Move `preflight_auth_check` to `core/controller_auth.py`. If nothing remains, delete the file. |
| `cli/validators/__init__.py` | UPDATE | Update re-exports to point to new location. |

### nac-test-pyats-common

| File | Action | Details |
|------|--------|---------|
| `sdwan/auth.py` | REFACTOR | Replace `get_matched_credential_set("SDWAN")` import + `ImportError` fallback with `from nac_test.core.controller import get_controller_context`. Use `get_controller_context().auth_method` to determine token vs session. |
| `iosxe/test_base.py` | REFACTOR | Replace `from nac_test.utils.controller import detect_controller_type` with `from nac_test.core.controller import get_controller_context`. Use `get_controller_context().controller_type` where needed. |
| Tests referencing old imports | REFACTOR | Update mocks/patches to target `nac_test.core.controller.get_controller_context` instead of `nac_test.utils.controller.detect_controller_type` / `get_matched_credential_set`. |

#### CI Pipeline Strategy for nac-test-pyats-common

The two packages have a circular runtime dependency (`nac-test ↔ nac-test-pyats-common`). The transitional fallback in `get_controller_context()` handles version skew at runtime — if the parent (older `nac-test`) doesn't serialize context, the subprocess falls back to current detection behavior with a deprecation warning.

**Approach: Runtime fallback + test skips for new-API-only tests**

Production code uses the fallback path — no `try/except ImportError` shims needed. Tests that specifically validate the *new* integration (context passed from parent) use `pytest.importorskip` for the transition window:

```python
# tests/sdwan/test_auth.py
import pytest

nac_controller = pytest.importorskip(
    "nac_test.core.controller",
    reason="Requires nac-test with controller resolution refactor"
)
```

**Rationale:**
- Production code works with both old and new `nac-test` (via fallback) — no conditional imports in hot paths
- Tests that exercise the new integration skip cleanly in CI when `nac-test` hasn't been updated yet
- Full integration is validated locally where both packages are installed from source
- Once both packages are released together, the fallback + skip conditions become dead code (removed in Phase 3)

#### nac-test-pyats-common Detailed Changes

**`sdwan/auth.py`** (the only file currently using `get_matched_credential_set`):

Before:
```python
try:
    from nac_test.utils.controller import get_matched_credential_set
except ImportError:
    get_matched_credential_set = None  # type: ignore[assignment]

# Later in get_auth():
if get_matched_credential_set is not None:
    cred_set = get_matched_credential_set("SDWAN")
    if cred_set:
        auth_method = cred_set.auth_method
```

After:
```python
from nac_test.core.controller import get_controller_context

# Later in get_auth():
ctx = get_controller_context()
auth_method = ctx.auth_method
```

**`iosxe/test_base.py`** (uses `detect_controller_type` for device inventory routing):

Before:
```python
from nac_test.utils.controller import detect_controller_type
controller_type = detect_controller_type()
```

After:
```python
from nac_test.core.controller import get_controller_context
controller_type = get_controller_context().controller_type
```

## Implementation Order

### Phase 1: nac-test core refactor

1. **`core/types.py`** — Add `ControllerContext` dataclass (no dependencies, safe first step)
2. **`core/controller.py`** — Move from `utils/`, refactor to `resolve_controller()`, add `get_controller_context()` accessor, add typed exceptions, add `format_resolution_error()`
3. **`core/controller_auth.py`** — Move `preflight_auth_check()`, update signature
4. **`utils/environment.py`** — Dissolve `EnvironmentValidator` class. Delete `validate_controller_env()`. Delete `get_bool()`, `get_int()`, `get_with_default()` (zero callers — duplicate `_env.py` functions). Keep only `check_required_vars()` and `format_missing_vars_error()` as module functions if needed.
5. **`combined_orchestrator.py`** — Update pre-flight to use new API, pass context to `PyATSOrchestrator`. Update pre-flight gate to cover both PyATS and Robot.
6. **`pyats_core/orchestrator.py`** — Remove `controller_type`, add `controller_context: ControllerContext | None` parameter, serialize to env before subprocess launch, remove `validate_environment()`
7. **Update all nac-test internal imports** — ensure nothing references old `utils/controller` paths
8. **Update nac-test tests** — adjust unit tests in `tests/utils/test_controller.py` (move to `tests/core/`), delete tests for `EnvironmentValidator.validate_controller_env()`, add contract tests for `ControllerContext` serialization round-trip
9. **Delete `cli/validators/controller_auth.py`** if empty after move

### Phase 2: nac-test-pyats-common update

10. **`sdwan/auth.py`** — Replace `get_matched_credential_set` import + ImportError fallback with `get_controller_context()` call
11. **`iosxe/test_base.py`** — Replace `detect_controller_type()` with `get_controller_context().controller_type`
12. **Update tests** — Patch/mock `nac_test.core.controller.get_controller_context` instead of old functions. Add `pytest.importorskip` guards for tests requiring the new API (CI pipeline may still have old nac-test).
13. **Remove dead code** — Delete any remaining references to `detect_controller_type`, `get_matched_credential_set`, `CredentialSet` imports

### Phase 3: Cleanup (after both packages are released)

14. **Verify CI** — Both repos pass with shared venv (local) and individual pipelines (CI)
15. **Remove transitional fallback** — Delete the `detect_controller_type()` fallback path in `get_controller_context()` and the associated `DeprecationWarning`. Missing env var becomes a hard `RuntimeError` (clean cut).
16. **Remove skip guards** — Remove `pytest.importorskip` conditions from nac-test-pyats-common tests
17. **Remove dead code** — Delete `_detect_controller_type()`, `_infer_auth_method()` if no longer needed internally
18. **Update `dev-docs/PRD_AND_ARCHITECTURE.md`** — Reflect new controller resolution architecture

## Testing Strategy

### nac-test

- **Contract tests**: `ControllerContext.to_json()` → `from_json()` round-trip; schema stability; unknown fields ignored gracefully
- **Unit tests**: `resolve_controller()` returns correct `ControllerContext` for each controller type; raises correct typed exceptions for each failure mode
- **Unit tests**: `get_controller_context()` reads from env var in subprocess context, from cache in parent context, falls back to `_detect_controller_type()` with `DeprecationWarning` when env var absent (transitional)
- **Integration**: `resolve_controller()` → `preflight_auth_check()` → serialize → `get_controller_context()` → adapter receives correct `auth_method`
- **Negative tests**: missing env vars → `NoCredentialsFound`; partial vars → `IncompleteCredentials`; multiple controllers → `MultipleControllersFound`

### nac-test-pyats-common

- **Unit tests**: Auth adapters receive correct `auth_method` from mocked `get_controller_context()`
- **Fallback tests**: Verify that subprocess gracefully falls back to `detect_controller_type()` when `NAC_TEST_CONTROLLER_CONTEXT` is absent (transitional) and emits `DeprecationWarning`
- **CI compatibility**: Tests requiring new nac-test API use `pytest.importorskip("nac_test.core.controller")` — skip cleanly when published nac-test is stale
- **Local validation**: Full integration tested in shared venv where both packages are installed from source (`pip install -e ../nac-test -e .`)
- **Release decoupling**: Either package can ship a bug-fix release independently — the fallback handles version skew at runtime

## References

- Issue: https://github.com/netascode/nac-test/issues/856
- PR #847 (credential sets): https://github.com/netascode/nac-test/pull/847
- Related: nac-test-pyats-common#34
