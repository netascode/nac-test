# Phase 1 Task 1: TestFileParser Component - Design Decisions

## 1. AST Parsing Pattern
**Decision**: Adapt the proven pattern from `test_type_resolver.py` rather than using other approaches

**Alternatives Considered**:
- `importlib.util.spec_from_file_location()` - executes code (security risk)
- Manual regex parsing - fragile, hard to maintain
- Using `ast.walk()` vs iterating `tree.body` - chose `tree.body` for clarity (only top-level classes)

**Rationale**: 
- Proven pattern already in codebase
- Safe (no code execution)
- Explicit iteration order
- Handles both direct and qualified inheritance

## 2. Async Method Detection
**Decision**: Check both `ast.FunctionDef` and `ast.AsyncFunctionDef`

**Discovery Process**:
- Initial implementation only checked `FunctionDef`
- Testing revealed actual test file uses `async def verify_item()`
- Python AST creates `AsyncFunctionDef` for async methods, not `FunctionDef`

**Impact**: Critical for accurate detection in real test files with async verification methods

## 3. Safe Dictionary Evaluation
**Decision**: Use `ast.literal_eval()` for TEST_CONFIG extraction

**Why Not `eval()`**:
- eval() executes arbitrary code - major security risk
- Could execute function calls in TEST_CONFIG (e.g., `get_config()`)
- Users might accidentally include unsafe code

**Why `ast.literal_eval()`**:
- Only evaluates literal structures (dicts, lists, strings, numbers)
- Rejects function calls, variable references
- Perfect for TEST_CONFIG (should be static data)
- Safe by design

## 4. Error Handling Strategy
**Decision**: Three-tier error handling

1. **Propagate OSError/SyntaxError** - Let caller handle file and syntax issues
2. **Raise ValueError** - For logical errors (missing class, config, base class)
3. **Wrap ast.literal_eval errors** - Convert to ValueError with helpful message

**Rationale**:
- OSError/SyntaxError are environmental - caller context matters
- ValueError signals data validation failure - appropriate for caller
- Helpful error messages aid debugging

## 5. Dataclass vs Other Structures
**Decision**: Use @dataclass for TestFileInfo

**Alternatives**:
- dict - less type-safe, harder to document
- NamedTuple - works but less flexible
- Custom class - more boilerplate

**Rationale**:
- Type-safe with modern Python
- Automatic __init__, __repr__, __eq__
- Clear field documentation
- Integrates well with typing system

## 6. Base Class Constants
**Decision**: Define KNOWN_SSH_BASE_CLASSES as module-level set

**Classes Included**:
- SSHTestBase (base class)
- IOSXETestBase (IOS-XE devices)
- SDWANTestBase (SD-WAN devices)
- SDWANSSHTestBase (SD-WAN with SSH)
- CatalystCenterSSHTestBase (Catalyst Center)

**Future Extensibility**: Easy to add new base classes without code changes

## 7. Test Name Derivation
**Decision**: Use filename stem (Path.stem) for test_name

**Example**: `verify_iosxe_control.py` → `verify_iosxe_control`

**Why Not Class Name**:
- Filename is user-facing (appears in UI, reports)
- More predictable and stable
- Class name varies per file

## 8. Documentation Style
**Decision**: Comprehensive docstrings for public API only

**Public API**:
- `TestFileParser` class docstring
- `parse_test_file()` method docstring
- `TestFileInfo` dataclass docstring

**Private Methods**:
- Short docstrings for clarity
- Minimal but clear

**Rationale**: Balance between documentation and code cleanliness

## 9. Logging Strategy
**Decision**: Use `logging.getLogger(__name__)` for module-level logger

**Log Levels**:
- DEBUG: Parsing steps, base classes found
- INFO: Successful parsing
- ERROR: Validation failures

**Use Cases**: 
- Troubleshooting parsing issues
- Tracking which files were processed
- Understanding extraction failures

## 10. Security Considerations
**Decision**: No code execution, only AST analysis

**Threat Model**:
- User test files might contain malicious code
- Parser reads files but never executes
- Only evaluates literal data structures

**Mitigation**:
- AST parsing (no execution)
- ast.literal_eval (no code execution)
- Comprehensive error handling
- Clear documentation of safe behavior

---

## Implementation Notes

### Key Methods and Their Purpose
1. `parse_test_file()` - Main entry point, orchestrates parsing
2. `_extract_base_name()` - Handles both Name and Attribute AST nodes
3. `_extract_test_config()` - Uses ast.literal_eval with error handling
4. `_has_custom_verify_item()` - Detects both sync and async methods

### Testing Coverage
- ✅ Happy path (real test file)
- ✅ Qualified inheritance (module.ClassName)
- ✅ No custom verify_item
- ✅ Complex nested TEST_CONFIG
- ✅ File not found (OSError)
- ✅ Syntax errors (SyntaxError)
- ✅ Missing test class (ValueError)
- ✅ Missing TEST_CONFIG (ValueError)
- ✅ Invalid TEST_CONFIG (ValueError)

