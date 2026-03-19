## Goal

Enable include/exclude filtering for pyATS tests in nac-test, similar to how Robot tests can be filtered with `--include`/`--exclude` tags.

## TL;DR

- pyATS supports **`groups`** - a simple class attribute on test classes
- This maps well to nac-test's test generation pattern
- Recommended: Use `groups` for filtering, expose via `--include-groups`/`--exclude-groups` CLI flags

## How pyATS Groups Work

Test classes can declare group membership:

```python
class MyTestcase(Testcase):
    groups = ['sanity', 'regression', 'slow']
```

Then filter at runtime: include only `sanity` tests, or exclude `slow` tests.

## Proposed Approach

| Step | Description |
|------|-------------|
| 1. Parse groups at discovery | Extract `groups` attribute from test classes via AST |
| 2. Pre-filter test files | Skip files where no test classes match the filter |
| 3. Pass to pyATS runtime | For partial matches, let pyATS handle fine-grained filtering |

**Benefits:**
- ✅ Native pyATS mechanism (no custom filtering logic)
- ✅ Matches nac-test's existing test generation
- ✅ Consistent UX with Robot's tag filtering

**Trade-offs:**
- ⚠️ Groups must be statically declared (no runtime assignment)
- ⚠️ Adds complexity to discovery phase

## Alternative pyATS Filtering Options

pyATS also supports UID-based filtering:

| Mechanism | Description | Use Case |
|-----------|-------------|----------|
| `uids` | Include test sections by UID pattern | Filter specific testcases by class name |
| `exclude_uids` | Exclude test sections by UID pattern | Skip specific testcases |

**UIDs** default to the class name (e.g., `MyTestcase`) and can be filtered with regex patterns or Logic expressions (`And`, `Or`, `Not`).

**Why `groups` is preferred for nac-test:**
- Groups are semantic ("sanity", "slow") vs UIDs which are structural (class names)
- Groups allow multiple categories per test; UIDs are single identifiers
- Groups align better with Robot's tag-based filtering model

## Open Questions

| Question | Options |
|----------|---------|
| CLI interface | New flags (`--include-groups`) vs extend existing (`--include`) |
| Unified filtering | Same filter for Robot + pyATS, or separate? |
| Group conventions | Free-form or predefined set (sanity, regression, etc.)? |
| UID filtering | Also expose `--include-uids`/`--exclude-uids`, or groups-only? |

## Current State

- `TestDiscovery`: File-level only, doesn't extract groups
- `JobGenerator`: Doesn't pass filtering params to pyATS

## Next Steps

1. Decide on CLI interface approach
2. Implement group extraction in discovery
3. Wire up filtering in job generator
