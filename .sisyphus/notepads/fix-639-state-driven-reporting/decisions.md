# Architectural Decisions - Fix #639/#644

## [2026-03-15] Wave 1 Design Decisions

### Decision 1: CombinedResults as REQUIRED parameter
**Context**: xunit_merger.py needs state awareness to avoid stale file collection

**Decision**: Make `results: CombinedResults` a REQUIRED parameter (no default, not optional)

**Rationale**:
- Breaking change is acceptable (enforces correct usage)
- Type safety prevents accidental filesystem-only checks
- Clear API contract: "You must provide execution state"

**Alternative Rejected**: Optional parameter with `None` default
- Would allow callers to skip state checks
- Defeats the purpose of state-driven reporting

### Decision 2: Use `is_empty` instead of `state == SUCCESS`
**Context**: Need to determine if framework produced results

**Decision**: Use `not test_results.is_empty` for all frameworks

**Rationale**:
- `is_empty` returns `self.total == 0` - simple and clear
- Works correctly for ALL ExecutionState values (SUCCESS, EMPTY, ERROR, SKIPPED)
- Semantic meaning: "Did we get any test results?" not "Was execution successful?"

**Alternative Rejected**: Check `state == ExecutionState.SUCCESS`
- Too restrictive (would hide reports for ERROR states that still produced test data)
- Doesn't handle edge cases where state != SUCCESS but tests ran

### Decision 3: Keep function name `cleanup_stale_test_artifacts`
**Context**: Function name doesn't perfectly describe behavior

**Decision**: Keep existing name, do not rename

**Rationale**:
- Backward compatibility with existing code and documentation
- Name is "good enough" - clearly describes purpose
- Renaming creates churn without significant benefit

**Alternative Rejected**: Rename to `cleanup_output_dir`
- More generic but less descriptive
- Breaking change with no functional benefit
