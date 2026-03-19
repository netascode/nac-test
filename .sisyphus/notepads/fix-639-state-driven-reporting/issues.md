# Issues & Gotchas - Fix #639/#644

## [2026-03-15] Wave 1 Issues Encountered

### Issue 1: LSP diagnostics not available for project root
**Context**: Attempted to run `lsp_diagnostics(filePath=".")` for project-level checks

**Problem**: No LSP server configured for extension ""

**Workaround**: Use import checks and specific file verification instead
- Import test: `uv run python -c "from module import func; print('Import successful')"`
- Specific tests: Run pytest on affected test files

**Resolution**: This is acceptable - import checks + pytest provide sufficient verification

### Issue 2: Existing tests didn't cover `has_report` field
**Context**: Added `has_report` to combined_generator.py framework data dict

**Observation**: All 20 existing tests passed without modification
- Tests don't assert on the full framework data structure
- Tests focus on aggregate stats and high-level behavior
- New field doesn't break existing assertions

**Action Required**: Task 8 will add explicit tests for `has_report` behavior

## Known Gotchas
- **is_empty semantics**: Returns `self.total == 0` - works for all ExecutionState values, not just SUCCESS
- **CombinedResults attributes**: `robot`, `api`, `d2d` are all `TestResults | None` - must check both None AND is_empty
- **Template context**: Framework data dict structure in combined_generator.py affects template rendering
