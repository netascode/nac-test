# Code Review: Issue #641 — Round 2

## Overall Assessment

All seven findings from round 1 have been addressed. The architecture is clean and
the key improvements (module-level lookup, `parse_args`-derived pabot detection,
`logger.debug()`, removal of redundant `ignore_unknown_options`) are all in place.
Two new findings remain before merge.

---

## Round 1 — Resolution Status

| # | Status | Notes |
|---|--------|-------|
| 1 | ✅ Fixed | `_CONTROLLED_OPTIONS_LOOKUP` now built at module level |
| 2 | ✅ Fixed | Hardcoded list replaced with `parse_args`-derived diff against defaults |
| 3 | ✅ Fixed | Inline comments added explaining case-sensitivity asymmetry |
| 4 | ✅ Fixed | `logger.error()` replaced with `logger.debug()` in all three helpers |
| 5 | ✅ Fixed | `ignore_unknown_options: False` dropped |
| 6 | ✅ Fixed | `test_pabot_args.py` renamed to `test_pabot_loglevel.py`, class to `TestRunPabotLoglevel`, parametrized test replaced with focused `test_extra_args_loglevel_overrides_default` which already includes `call_args` in assertion message |

---

## New Findings

### A. `_raise_if_pabot_options` error message reports wrong options (Medium)

The error message is built by re-scanning `extra_args` for any `--` prefixed argument,
not from the `pabot_options_found` list that was actually detected:

```python
user_args = [arg for arg in extra_args if arg.startswith("--")]
error_msg = (
    f"Pabot-specific arguments are not allowed in extra arguments: "
    f"{', '.join(user_args)}. ..."
)
```

If a user passes `-- --variable FOO:bar --testlevelsplit`, the error message will
incorrectly report `--variable` as a pabot argument. It should use `pabot_options_found`
instead:

```python
error_msg = (
    f"Pabot-specific arguments are not allowed in extra arguments: "
    f"{', '.join(pabot_options_found)}. Only Robot Framework options are accepted."
)
```

---

### B. Silent skip on pabot API change needs a CI guard (Low)

The graceful-degradation approach — skipping pabot validation with a `logger.warning()`
when the API is unavailable or has changed — is the right choice for deployed users.
However, it means a pabot upgrade that breaks the internal API would silently disable
the feature without anyone noticing until a user reports it.

A dedicated test in `tests/unit/cli/validators/test_args.py` provides the CI-level
safety net without impacting production behaviour:

```python
def test_pabot_parse_args_api_shape() -> None:
    """Guard against pabot API changes that would silently disable pabot validation.

    If this test fails after a pabot upgrade, review _raise_if_pabot_options
    in args.py to ensure pabot option detection still works correctly.
    """
    from nac_test.cli.validators.args import _pabot_parse_args

    assert _pabot_parse_args is not None, "pabot.arguments.parse_args not importable"
    result = _pabot_parse_args(["__dummy__.robot"])
    assert len(result) == 4, f"Expected 4-tuple from parse_args, got {len(result)}"
    pabot_args = result[2]
    assert "pabotlib" in pabot_args, (
        f"Expected 'pabotlib' key in pabot_args, got {list(pabot_args)}"
    )
    assert "testlevelsplit" in pabot_args
```

This gives graceful degradation in production and a noisy failure in CI when pabot
changes its API — which is exactly the right moment to review the validation logic.

---

## Summary

| # | Severity | Area | Action |
|---|----------|-------|--------|
| A | Medium | `args.py` | Error message reports all `--` args, not just detected pabot options — use `pabot_options_found` |
| B | Low | `test_args.py` | Add API shape test to catch pabot upgrades that silently disable pabot validation |

Item **A** must be fixed before merge. **B** is polish.
