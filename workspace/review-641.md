# Code Review: Issue #641 — `--` separator enforcement for Robot args

## Overall Assessment

The design direction is sound: moving validation out of `pabot.py` and into a dedicated
`cli/validators/args.py` is the right architectural call — it makes validation a CLI concern
(fail fast, before expensive operations) rather than an execution concern. The rename from
`robot_loglevel` to `default_robot_loglevel` is a nice semantic improvement. That said,
there are several concrete issues worth addressing.

---

## Issues

### 1. `_build_controlled_options_lookup()` — move result to module level

`_CONTROLLED_ROBOT_OPTIONS` is a static module-level constant, so the dict derived from
it is equally static. Building it inside `_raise_if_controlled_robot_options` is
non-obvious and invites the question "why isn't this cached?". The straightforward Python
pattern is to derive it once at module level:

```python
_CONTROLLED_ROBOT_OPTIONS: list[tuple[str, str | None, str]] = [...]

# Flat lookup dict derived from the above — built once at import time
_CONTROLLED_OPTIONS_LOOKUP: dict[str, str] = _build_controlled_options_lookup()
```

`_build_controlled_options_lookup` can then be removed or kept as a private helper called
only during module initialisation, and `_raise_if_controlled_robot_options` simply
references `_CONTROLLED_OPTIONS_LOOKUP` directly.

---

### 2. `_PABOT_SPECIFIC_OPTIONS` hardcoded list is stale and entirely unnecessary

The list was written against pabot 4.x but the project now requires `>=5.2.2`, which
added `--processtimeout`, `--shard`, `--chunk`, `--no-pabotlib`, `--no-rebot`,
`--pabotconsole`, `--command`/`--end-command`, and `--argumentfile`. All of these are
missing from `_PABOT_SPECIFIC_OPTIONS`, so the check has gaps today and will silently
drift again with future pabot releases.

More importantly, the hardcoded list is entirely unnecessary: `parse_args` (already called
in `parse_and_validate_extra_args`) returns a `pabot_args` dict as its third element
containing **all** pabot options with their parsed values. Any pabot option the user
passes will be reflected there as a non-default value. The detection can therefore be done
by comparing `pabot_args` against the known defaults — no list to maintain at all:

```python
_PABOT_DEFAULTS = parse_args(["__dummy__.robot"])[2]

# in parse_and_validate_extra_args, after calling parse_args:
pabot_options_found = [
    k for k, v in pabot_args.items() if v != _PABOT_DEFAULTS[k]
]
if pabot_options_found:
    raise ValueError(...)
```

This makes the check future-proof by construction — no list to maintain.

---

### 3. `_raise_if_controlled_robot_options` — case-normalisation is asymmetric

Long options are lowercased (`arg[2:].lower()`), but short options are not (`arg[1]`),
which is correct since `-I` and `-i` are different flags in Robot. However the asymmetry
is non-obvious to a reader. Add a brief comment explaining the deliberate difference:

```python
if arg.startswith("--"):
    key = arg[2:].lower()  # long options are case-insensitive
elif arg.startswith("-") and len(arg) == 2:
    key = arg[1]  # short options are case-sensitive (-i != -I)
```

---

### 4. `logger.error()` before raising in validation helpers is redundant noise

In `_raise_if_controlled_robot_options`, `_raise_if_pabot_options`, and
`_raise_if_datasources`, the pattern is:

```python
logger.error(error_msg)
raise ValueError(error_msg)
```

The caller in `main.py` catches the exception and prints to stderr via `typer.echo`, so
the message appears twice — once in the log (at ERROR level) and once in the CLI output.
Validators shouldn't be responsible for user-facing error reporting; that's the CLI's job.
Either drop the `logger.error()` calls from the validators entirely, or downgrade to
`logger.debug()` for diagnostics. Consistent with the project preference ("Prefer
`logger.error()` naturally; no workarounds for side-effects"), this double-reporting is a
side effect worth eliminating.

---

### 5. `ignore_unknown_options: False` in `main.py` — just drop it

```python
context_settings={"ignore_unknown_options": False, "allow_extra_args": True}
```

`False` is the default, so the explicit setting adds noise without adding clarity.
Simply remove it:

```python
context_settings={"allow_extra_args": True}
```

---

### 6. `tests/unit/test_pabot_args.py` — file and class name no longer match scope

The file went from testing argument validation broadly to only testing `run_pabot`
loglevel behaviour. The class `TestRunPabotRobotLoglevel` and the file name
`test_pabot_args.py` are now misleading. Consider renaming:

- file: `test_pabot_loglevel.py`
- class: `TestRunPabotLoglevel`

The tests that were removed now live in their correct homes
(`tests/unit/cli/validators/test_args.py` and `tests/unit/robot/test_pabot_error_handling.py`).

---

### 7. `test_extra_args_loglevel_takes_precedence` — assertion message could be more helpful

```python
assert loglevel_count == 1, (
    f"Expected exactly one loglevel arg, got {loglevel_count}"
)
```

When this fails the message doesn't show what was actually passed to pabot. Including
`call_args` makes failures much easier to diagnose:

```python
assert loglevel_count == 1, (
    f"Expected exactly one loglevel arg, got {loglevel_count} in {call_args}"
)
```

---

## Summary

| # | Severity | Area | Action |
|---|----------|------|--------|
| 1 | Low | `args.py` | Move `_build_controlled_options_lookup()` result to module level — it's derived from a static constant |
| 2 | Medium | `args.py` | `_PABOT_SPECIFIC_OPTIONS` list is stale (missing pabot 5.2 options) and unnecessary — derive from `parse_args` return value instead |
| 3 | Low | `args.py` | Asymmetric case handling — add inline comment |
| 4 | Medium | `args.py` | `logger.error` + raise causes double reporting; drop or downgrade |
| 5 | Low | `main.py` | `ignore_unknown_options: False` is the default — just remove it |
| 6 | Low | `test_pabot_args.py` | File/class names no longer match actual test scope |
| 7 | Low | `test_pabot_args.py` | Assertion message should include `call_args` for diagnostics |

Items **2** and **4** are the most worth addressing before merging; the rest are polish.
