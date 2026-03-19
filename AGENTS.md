# AI Agent Guidelines for nac-test

This file provides context and guidelines for AI coding assistants working on this project.

## Critical Constraints (NEVER violate)

- **⚠️ NEVER commit, push, or create issues/PRs without explicit user approval**
- NEVER use `git add -A`, `git add .`, or `git add -a` — always use `git add -u` or explicit file paths

## Unit Testing Guidelines

### 1. Patch at the call site, not where defined

```python
# WRONG - patches the stdlib directly, breaks if module refactors imports
with patch("logging.Logger.debug"):
    ...

# CORRECT - patches where the module looks it up
with patch("nac_test.utils.logging.logging.Logger.debug"):
    ...
```

This ensures tests remain stable if the module under test changes how it imports (e.g., `import logging` → `from logging import getLogger`).

### 2. Test business logic, not implementation details

Focus tests on the code's unique behavior, not language features or stdlib functionality.

```python
# WRONG - testing internal debug message content
mock_debug.assert_called_once()
assert mock_debug.call_args[0][1] == "WARNING"

# WRONG - testing that dataclasses work
config = Config(name="test")
assert config.name == "test"  # Tests Python, not our code

# CORRECT - testing actual observable behavior
configure_logging("WARNING")
assert logging.getLogger().level == logging.WARNING
```

Avoid testing:
- Log message content (unless user-facing)
- Internal state that isn't part of the public API, unless it is required to validate logic.
- Implementation details that may change
- Dataclass/namedtuple field access (stdlib behavior)
- Basic stdlib functionality (e.g., `Path.exists()` returns bool)

### 3. DRY with pytest parametrization (apply judiciously)

- Combine related tests that vary only by input/expected output
- Don't parametrize trivial one-liners where it adds complexity without benefit
- `ids=` parameter is optional — auto-generated IDs are often acceptable for short parameter lists.

```python
@pytest.mark.parametrize(
    ("level_input", "expected_level"),
    [
        (LogLevel.DEBUG, logging.DEBUG),
        (LogLevel.INFO, logging.INFO),
        ("DEBUG", logging.DEBUG),
        ("debug", logging.DEBUG),
    ],
)
def test_valid_input_sets_level(self, level_input, expected_level):
    configure_logging(level_input)
    assert logging.getLogger().level == expected_level
```

### 4. Use pytest-mock (`mocker`) over `unittest.mock`

The codebase uses `mocker` fixture from pytest-mock for consistency. Prefer:

```python
def test_something(self, mocker):
    mocker.patch("nac_test.module.function")
```

Over:

```python
from unittest.mock import patch

def test_something(self):
    with patch("nac_test.module.function"):
        ...
```

### 5. Clean up shared state with fixtures

When tests modify global state (e.g., root logger), use fixtures to restore it:

```python
@pytest.fixture(autouse=True)
def cleanup_root_logger(self) -> Generator[None, Any, None]:
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level
    yield
    root_logger.handlers = original_handlers
    root_logger.setLevel(original_level)
```

### 6. Extract repeated patching logic into fixtures

If patching logic is duplicated across tests, extract to a fixture:

```python
@pytest.fixture
def isolated_tempfile(mocker, tmp_path):
    """Redirect tempfile creation to isolated test directory."""
    original = tempfile.NamedTemporaryFile

    def patched(*args, **kwargs):
        kwargs.setdefault("dir", tmp_path)
        return original(*args, **kwargs)

    mocker.patch(
        "nac_test.module.tempfile.NamedTemporaryFile",
        side_effect=patched,
    )
```

## References


## Git Workflow

- Write clear, imperative commit messages (e.g., "Add feature X" not "Added feature X")
- Keep commits focused on a single change
- Reference issue numbers in commits when applicable
- NEVER use `git add -A`, `git add .`, or `git add -a` — always use `git add -u` or explicit file paths

### Before ANY commit or push

1. Show the user what will be committed (files, diff summary)
2. **Wait for explicit approval** — do NOT proceed without it
3. Only then execute the git command

## Python Execution

- Always use `uv run <command>` to execute Python commands (activates virtual environment)

## Test Execution

- Always use `uv run pytest -n auto --dist loadscope` when running any tests, especially the e2e tests take a long time
