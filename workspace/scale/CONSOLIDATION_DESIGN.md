# Automatic D2D Test Consolidation - Design Document

**Status:** Design Phase  
**Date:** February 7, 2026  
**Author:** Atlas (Oh-My-OpenCode)

---

## Executive Summary

This document outlines the design for automatic runtime consolidation of D2D (Direct-to-Device) PyATS tests to eliminate subprocess overhead and achieve **5.7× performance improvement** for production workloads.

**Problem:** Manual consolidation achieves 6.9× speedup but is incompatible with incremental test submission workflow.  
**Solution:** Automatic runtime consolidation that transforms multiple user test files into single consolidated file per base class.

---

## Background

### Proven Performance Impact

**Manual Consolidation Results (PoC):**
- 2 verification types: 102.17s → 14.82s (**6.9× faster**)
- Root cause: 87% of time is subprocess overhead (~9s per test file)
- Pattern: PyATS `aetest.loop.mark()` runs N iterations in 1 subprocess

**Production Projection:**
- 20 devices, 11 verification types
- Current: ~9m 23s
- After consolidation: ~1m 38s (**5.7× faster**)

### The User Constraint

Users submit test files **incrementally** over time:

```
Day 1: templates/tests/d2d/verify_control.py
Day 2: templates/tests/d2d/verify_sync.py
Week 2: templates/tests/d2d/verify_interfaces.py
```

**Cannot** ask users to manually merge files. Must consolidate automatically at runtime.

---

## Architecture Overview

### Test Flow (Current - No Consolidation)

```
┌──────────────────────────────────────────────────────────────┐
│ 1. TEST DISCOVERY                                            │
│    Input: templates/ directory                              │
│    Output: List[Path] of *.py files                         │
│    (test_discovery.py: discover_pyats_tests)                │
└──────────────────┬───────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────┐
│ 2. TEST CATEGORIZATION                                       │
│    Input: List[Path]                                         │
│    Output: (api_tests: List[Path], d2d_tests: List[Path])   │
│    (test_type_resolver.py: AST analysis detects base class) │
└──────────────────┬───────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────┐
│ 3. JOB GENERATION                                            │
│    Input: device + List[Path] of d2d test files             │
│    Output: Job file (Python code as string)                 │
│    ❌ ISSUE: Generates multiple run() calls                 │
│    for test_file in TEST_FILES:                             │
│        run(testscript=test_file, ...) # 1 subprocess each!  │
└──────────────────┬───────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────┐
│ 4. DEVICE EXECUTION                                          │
│    Input: Job file + testbed + device                       │
│    Output: Test results archive                             │
│    Subprocess runner executes job via pyats run job         │
└──────────────────────────────────────────────────────────────┘
```

### Test Flow (Proposed - With Consolidation)

```
┌──────────────────────────────────────────────────────────────┐
│ 1. TEST DISCOVERY                                            │
│    (unchanged)                                               │
└──────────────────┬───────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────┐
│ 2. TEST CATEGORIZATION                                       │
│    (unchanged)                                               │
└──────────────────┬───────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────┐
│ 3. JOB GENERATION (MODIFIED)                                 │
│    Input: device + List[Path] of d2d test files             │
│                                                              │
│    IF --consolidate-d2d-tests flag enabled:                 │
│      A. Parse each test file (extract TEST_CONFIG)          │
│      B. Group by base class (IOSXETestBase, etc.)           │
│      C. Generate consolidated file per group                │
│      D. Replace test_files list with consolidated files     │
│                                                              │
│    Output: Job file with consolidated test files            │
│    for consolidated_file in CONSOLIDATED_FILES:             │
│        run(testscript=consolidated_file, ...) # 1 per group!│
└──────────────────┬───────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────┐
│ 4. DEVICE EXECUTION                                          │
│    (unchanged - executes consolidated files)                │
└──────────────────────────────────────────────────────────────┘
```

**Key Insight:** Inject consolidation at job generation step (Step 3) - has access to both device info and test file list.

---

## Detailed Design

### Component Architecture

```
nac_test/pyats_core/consolidation/
├── __init__.py
├── test_parser.py          # Extract TEST_CONFIG via AST
├── file_generator.py       # Generate consolidated test file
└── orchestrator.py         # Group tests + coordinate generation
```

### Component 1: Test File Parser

**Location:** `nac_test/pyats_core/consolidation/test_parser.py`

**Purpose:** Parse user test files to extract TEST_CONFIG and metadata.

```python
class TestFileParser:
    """Extract test configuration from user test files via AST analysis."""
    
    def parse_test_file(self, test_path: Path) -> TestFileInfo:
        """
        Parse user test file to extract configuration.
        
        Returns:
            TestFileInfo:
                - base_class: "IOSXETestBase", "SDWANTestBase", etc.
                - test_config: {resource_type, api_endpoint, expected_values, ...}
                - test_name: "verify_control" (from filename stem)
                - class_name: "VerifySdwanControlConnectionsState"
                - has_custom_verify_item: bool (if verify_item() is overridden)
        """
```

**Implementation Strategy:**

1. **Parse Python file into AST**
   ```python
   tree = ast.parse(test_path.read_text())
   ```

2. **Find test class (inherits from SSHTestBase or subclass)**
   ```python
   for node in ast.walk(tree):
       if isinstance(node, ast.ClassDef):
           for base in node.bases:
               base_name = self._extract_base_name(base)
               if base_name in KNOWN_SSH_BASE_CLASSES:
                   test_class = node
                   break
   ```

3. **Extract TEST_CONFIG dictionary**
   ```python
   for node in test_class.body:
       if isinstance(node, ast.Assign):
           for target in node.targets:
               if getattr(target, 'id', None) == 'TEST_CONFIG':
                   # Use ast.literal_eval to safely evaluate dict
                   test_config = ast.literal_eval(node.value)
   ```

4. **Detect custom verify_item() method**
   ```python
   has_custom_verify = any(
       isinstance(node, ast.FunctionDef) and node.name == 'verify_item'
       for node in test_class.body
   )
   ```

**Edge Cases:**
- TEST_CONFIG not found → Skip file with warning
- Multiple classes in file → Use first one inheriting from SSH base
- TEST_CONFIG references variables → Use ast.literal_eval (only supports literals)

---

### Component 2: Consolidated File Generator

**Location:** `nac_test/pyats_core/consolidation/file_generator.py`

**Purpose:** Generate single consolidated test file from multiple parsed test files.

```python
class ConsolidatedFileGenerator:
    """Generate consolidated test file using aetest.loop.mark() pattern."""
    
    def generate_consolidated_file(
        self,
        base_class: str,
        test_infos: list[TestFileInfo],
        output_path: Path
    ) -> Path:
        """
        Generate consolidated test file.
        
        Args:
            base_class: "IOSXETestBase", "SDWANTestBase", etc.
            test_infos: List of parsed test file information
            output_path: Where to write consolidated file
            
        Returns:
            Path to generated consolidated file
        """
```

**File Template:**

```python
# Auto-generated by nac-test consolidation
# Source files: {list of original test files}

from {module} import {base_class}
from pyats import aetest
from nac_test.pyats_core.reporting.types import ResultStatus
import jmespath
import time

VERIFICATION_CONFIGS = {
    "verify_control": {
        "resource_type": "SD-WAN Control Connection",
        "api_endpoint": "show sdwan control connections",
        "expected_values": {"state": "up"},
        "log_fields": [...]
    },
    "verify_sync": {
        "resource_type": "SDWAN Edge Configuration Sync Status",
        "api_endpoint": "/dataservice/system/device/vedges",
        "expected_values": {"configStatusMessage": "In Sync"},
        "log_fields": [...]
    },
    # ... more verification types
}

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def mark_verification_loops(self):
        verification_types = list(VERIFICATION_CONFIGS.keys())
        aetest.loop.mark(DeviceVerification, verification_type=verification_types)

class DeviceVerification({base_class}):
    @aetest.test
    def test_device_verification(self, verification_type, steps):
        # Load config for this verification type
        self.TEST_CONFIG = VERIFICATION_CONFIGS[verification_type]
        self._current_verification_type = verification_type
        
        # Delegate to base class orchestration
        self.run_async_verification_test(steps)
    
    def get_items_to_verify(self):
        # Dispatch based on verification type
        verification_type = self._current_verification_type
        
        if verification_type == "verify_control":
            return [{"check_type": "...", "verification_scope": "..."}]
        elif verification_type == "verify_sync":
            return [{"check_type": "...", "verification_scope": "..."}]
        # ... more types
    
    async def verify_item(self, semaphore, client, context):
        # Dispatch to type-specific verification
        verification_type = self._current_verification_type
        
        if verification_type == "verify_control":
            return await self._verify_control(semaphore, client, context)
        elif verification_type == "verify_sync":
            return await self._verify_sync(semaphore, client, context)
        # ... more types
    
    # Type-specific verification methods
    async def _verify_control(self, semaphore, client, context):
        # Original verify_item() logic from verify_control.py
        ...
    
    async def _verify_sync(self, semaphore, client, context):
        # Original verify_item() logic from verify_sync.py
        ...

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup(self):
        pass
```

**Generation Strategy:**

1. **Extract imports** from original test files (via AST)
2. **Merge VERIFICATION_CONFIGS** from all TEST_CONFIG dictionaries
3. **Generate dispatch logic** in get_items_to_verify() and verify_item()
4. **Copy verify_item() bodies** as separate methods (_verify_control, etc.)
5. **Write to temp file** with unique name

**Handling Custom verify_item():**

If test has custom `verify_item()` method:
1. Extract method body via AST
2. Create dedicated method `_verify_{test_name}()`
3. Add dispatch case in consolidated verify_item()

**Import Resolution:**

```python
BASE_CLASS_IMPORT_MAP = {
    "IOSXETestBase": "from nac_test_pyats_common.iosxe import IOSXETestBase",
    "SDWANTestBase": "from nac_test_pyats_common.sdwan import SDWANTestBase",
    "CatalystCenterSSHTestBase": "from nac_test_pyats_common.catc import CatalystCenterSSHTestBase",
}
```

---

### Component 3: Consolidation Orchestrator

**Location:** `nac_test/pyats_core/consolidation/orchestrator.py`

**Purpose:** Coordinate parsing, grouping, and file generation.

```python
class TestConsolidator:
    """Orchestrate D2D test consolidation."""
    
    def __init__(self):
        self.parser = TestFileParser()
        self.generator = ConsolidatedFileGenerator()
    
    def consolidate_d2d_tests(
        self,
        test_files: list[Path],
        output_dir: Path
    ) -> dict[str, Path]:
        """
        Consolidate D2D tests by base class.
        
        Args:
            test_files: List of D2D test file paths
            output_dir: Directory for consolidated files (typically /tmp)
            
        Returns:
            {
                "IOSXETestBase": Path("/tmp/consolidated_IOSXETestBase_abc123.py"),
                "SDWANTestBase": Path("/tmp/consolidated_SDWANTestBase_def456.py"),
            }
        """
```

**Algorithm:**

```python
def consolidate_d2d_tests(self, test_files, output_dir):
    # Step 1: Parse all test files
    parsed_tests = []
    for test_file in test_files:
        try:
            info = self.parser.parse_test_file(test_file)
            parsed_tests.append(info)
        except Exception as e:
            logger.warning(f"Failed to parse {test_file}: {e}, skipping consolidation for this file")
            # Fallback: Keep original file in output
            continue
    
    # Step 2: Group by base class
    groups = defaultdict(list)
    for info in parsed_tests:
        groups[info.base_class].append(info)
    
    # Step 3: Generate consolidated file per group
    consolidated_files = {}
    for base_class, test_infos in groups.items():
        if len(test_infos) < 2:
            # No benefit from consolidation, keep originals
            logger.info(f"Only 1 test for {base_class}, skipping consolidation")
            continue
        
        # Generate unique output path
        hash_str = hashlib.md5(
            "".join([t.test_name for t in test_infos]).encode()
        ).hexdigest()[:8]
        output_path = output_dir / f"consolidated_{base_class}_{hash_str}.py"
        
        # Generate consolidated file
        self.generator.generate_consolidated_file(
            base_class, test_infos, output_path
        )
        
        consolidated_files[base_class] = output_path
        logger.info(
            f"Consolidated {len(test_infos)} tests for {base_class} → {output_path}"
        )
    
    return consolidated_files
```

**Fallback Strategy:**

- If parsing fails for a test file → Keep original file, log warning
- If only 1 test per base class → No consolidation benefit, keep original
- If consolidation generation fails → Fall back to original files, log error

---

### Component 4: JobGenerator Integration

**Modify:** `nac_test/pyats_core/execution/job_generator.py`

```python
class JobGenerator:
    def __init__(
        self,
        max_workers: int,
        output_dir: Path,
        consolidate_d2d_tests: bool = False  # NEW FLAG
    ):
        self.max_workers = max_workers
        self.output_dir = Path(output_dir)
        self.consolidate_d2d_tests = consolidate_d2d_tests
        
        # Initialize consolidator if enabled
        if self.consolidate_d2d_tests:
            from nac_test.pyats_core.consolidation import TestConsolidator
            self.consolidator = TestConsolidator()
        else:
            self.consolidator = None
    
    def generate_device_centric_job(
        self, device: dict, test_files: list[Path]
    ) -> str:
        """Generate job file for device-centric D2D tests."""
        
        # NEW: Check if consolidation is enabled
        if self.consolidate_d2d_tests and self.consolidator:
            logger.info(f"Consolidating {len(test_files)} D2D tests...")
            
            # Consolidate test files
            consolidated_map = self.consolidator.consolidate_d2d_tests(
                test_files,
                output_dir=Path(tempfile.gettempdir())
            )
            
            # Replace test_files with consolidated files
            if consolidated_map:
                # Use consolidated files + any unparseable originals
                test_files = list(consolidated_map.values())
                logger.info(
                    f"Using {len(test_files)} consolidated file(s) "
                    f"instead of {len(test_files)} original files"
                )
        
        # Rest of job generation (unchanged)
        test_files_str = ",\n        ".join([f'"{str(tf)}"' for tf in test_files])
        
        job_content = textwrap.dedent(f'''
        """Auto-generated PyATS job file for device {device["hostname"]}"""
        
        TEST_FILES = [
            {test_files_str}
        ]
        
        def main(runtime):
            for test_file in TEST_FILES:
                run(testscript=test_file, ...)
        ''')
        
        return job_content
```

**Key Changes:**
1. Add `consolidate_d2d_tests` flag to constructor
2. Initialize `TestConsolidator` if flag is enabled
3. Call `consolidator.consolidate_d2d_tests()` before job generation
4. Replace `test_files` list with consolidated files
5. Continue with existing job generation logic

---

### Component 5: CLI Integration

**Modify:** Main CLI entry point (wherever nac-test CLI is defined)

```python
@click.option(
    "--consolidate-d2d-tests",
    is_flag=True,
    default=False,
    help="Enable automatic consolidation of D2D tests for performance optimization",
    envvar="NAC_TEST_CONSOLIDATE_D2D"
)
def main(..., consolidate_d2d_tests: bool):
    """Main CLI entry point."""
    
    # Pass flag to JobGenerator
    job_generator = JobGenerator(
        max_workers=max_workers,
        output_dir=output_dir,
        consolidate_d2d_tests=consolidate_d2d_tests  # NEW
    )
```

**Usage:**

```bash
# Enable consolidation (opt-in)
nac-test --data ./data --templates ./tests --output ./results \
         --pyats --consolidate-d2d-tests

# Or via environment variable
export NAC_TEST_CONSOLIDATE_D2D=1
nac-test --data ./data --templates ./tests --output ./results --pyats
```

---

## Implementation Plan

### Phase 1: Core Components (Week 1)

#### Task 1.1: TestFileParser
- [ ] Create `test_parser.py` with AST parsing logic
- [ ] Implement `parse_test_file()` method
- [ ] Add TEST_CONFIG extraction
- [ ] Add base class detection
- [ ] Unit tests for various test file structures

#### Task 1.2: ConsolidatedFileGenerator
- [ ] Create `file_generator.py` with template logic
- [ ] Implement `generate_consolidated_file()` method
- [ ] Add import resolution
- [ ] Add dispatch logic generation
- [ ] Unit tests for generated file structure

#### Task 1.3: TestConsolidator
- [ ] Create `orchestrator.py` with grouping logic
- [ ] Implement `consolidate_d2d_tests()` method
- [ ] Add grouping by base class
- [ ] Add fallback handling
- [ ] Unit tests for grouping and error cases

### Phase 2: Integration (Week 1-2)

#### Task 2.1: JobGenerator Integration
- [ ] Modify `JobGenerator.__init__()` to accept flag
- [ ] Add consolidation call in `generate_device_centric_job()`
- [ ] Add logging for consolidation steps
- [ ] Integration tests with sample test files

#### Task 2.2: CLI Integration
- [ ] Add `--consolidate-d2d-tests` flag
- [ ] Add environment variable support
- [ ] Update CLI help text
- [ ] Update documentation

### Phase 3: Testing & Validation (Week 2)

#### Task 3.1: Unit Tests
- [ ] Test file parser with various TEST_CONFIG formats
- [ ] Test generator with different base classes
- [ ] Test orchestrator grouping logic
- [ ] Test error handling and fallbacks

#### Task 3.2: Integration Tests
- [ ] Test with 2 test files (same base class)
- [ ] Test with 11 test files (production scale)
- [ ] Test with mixed base classes
- [ ] Test with unparseable files (fallback)
- [ ] Measure performance improvement

#### Task 3.3: End-to-End Validation
- [ ] Run against workspace/scale setup (22 files → 1 file)
- [ ] Verify 6.9× speedup maintained
- [ ] Verify independent test reporting
- [ ] Verify HTML report quality

### Phase 4: Documentation & Rollout (Week 2-3)

#### Task 4.1: User Documentation
- [ ] Update README with consolidation feature
- [ ] Add troubleshooting guide
- [ ] Create migration guide for existing projects
- [ ] Add performance benchmarks

#### Task 4.2: Production Rollout
- [ ] Beta testing with architecture teams
- [ ] Collect feedback and iterate
- [ ] Consider making default (opt-out instead of opt-in)
- [ ] Release notes and changelog

---

## Testing Strategy

### Unit Tests

**TestFileParser:**
```python
def test_parse_simple_test_file():
    """Test parsing test with simple TEST_CONFIG."""
    content = '''
    class MyTest(IOSXETestBase):
        TEST_CONFIG = {
            "resource_type": "Connection",
            "api_endpoint": "show connections",
        }
    '''
    info = parser.parse_test_file(Path("test.py"))
    assert info.base_class == "IOSXETestBase"
    assert info.test_config["resource_type"] == "Connection"

def test_parse_missing_test_config():
    """Test handling of missing TEST_CONFIG."""
    content = '''
    class MyTest(IOSXETestBase):
        pass
    '''
    with pytest.raises(ValueError, match="TEST_CONFIG not found"):
        parser.parse_test_file(Path("test.py"))
```

**ConsolidatedFileGenerator:**
```python
def test_generate_single_base_class():
    """Test generating consolidated file for single base class."""
    test_infos = [
        TestFileInfo(base_class="IOSXETestBase", test_name="verify_control", ...),
        TestFileInfo(base_class="IOSXETestBase", test_name="verify_sync", ...),
    ]
    
    output = generator.generate_consolidated_file(
        "IOSXETestBase", test_infos, Path("/tmp/test.py")
    )
    
    assert output.exists()
    content = output.read_text()
    assert "VERIFICATION_CONFIGS" in content
    assert "verify_control" in content
    assert "verify_sync" in content
    assert "aetest.loop.mark" in content
```

**TestConsolidator:**
```python
def test_group_by_base_class():
    """Test grouping by base class."""
    test_files = [
        Path("verify_control.py"),  # IOSXETestBase
        Path("verify_sync.py"),     # IOSXETestBase
        Path("verify_api.py"),      # SDWANTestBase
    ]
    
    result = consolidator.consolidate_d2d_tests(test_files, Path("/tmp"))
    
    assert len(result) == 2  # 2 base classes
    assert "IOSXETestBase" in result
    assert "SDWANTestBase" in result
```

### Integration Tests

**2-File Consolidation:**
```bash
# Setup: 2 test files (verify_control.py + verify_sync.py)
nac-test --data ./data --templates ./tests --output ./results \
         --pyats --consolidate-d2d-tests

# Expected:
# - 1 consolidated file generated
# - 2× speedup (2 subprocesses → 1 subprocess)
# - All tests PASS
# - Independent reporting maintained
```

**11-File Consolidation (Production Scale):**
```bash
# Setup: 11 test files (all IOSXETestBase)
nac-test --data ./data --templates ./tests --output ./results \
         --pyats --consolidate-d2d-tests

# Expected:
# - 1 consolidated file generated
# - 5.7× speedup (11 subprocesses → 1 subprocess)
# - Execution time: ~1m 38s (from 9m 23s baseline)
# - All 11 verification types reported independently
```

**Mixed Base Classes:**
```bash
# Setup: 6 IOSXETestBase + 3 SDWANTestBase + 2 CatalystCenterSSHTestBase
nac-test --data ./data --templates ./tests --output ./results \
         --pyats --consolidate-d2d-tests

# Expected:
# - 3 consolidated files (1 per base class)
# - Speedup: (11 → 3) = 3.7× improvement
```

### Performance Validation

**Baseline (No Consolidation):**
```bash
time nac-test --data ./data --templates ./tests --output ./results --pyats

# Expected: ~102s for 22 files (2 types × 11 duplicates)
```

**Optimized (With Consolidation):**
```bash
time nac-test --data ./data --templates ./tests --output ./results \
              --pyats --consolidate-d2d-tests

# Expected: ~14.82s (6.9× faster)
```

---

## Risk Analysis

| Risk | Impact | Mitigation |
|------|--------|-----------|
| AST parsing fails for complex files | High | Fallback to original files, log warning |
| TEST_CONFIG references variables | Medium | Document limitation, suggest literal values |
| Different base classes mixed incorrectly | High | Group by base class before consolidation |
| verify_item() extraction incomplete | Medium | Detect custom methods, copy full body |
| Backward compatibility breaks | High | Make opt-in with `--consolidate-d2d-tests` |
| Debugging harder with consolidated files | Low | Keep consolidated files, add source comments |
| Performance not as expected | Medium | Validate with benchmarks, document results |

---

## Success Criteria

### Functional Requirements
- [ ] Consolidates N test files into 1 file per base class
- [ ] Maintains independent test reporting (each type separate result)
- [ ] Preserves all test metadata and logging
- [ ] Falls back gracefully on parse errors
- [ ] Works with IOSXETestBase, SDWANTestBase, CatalystCenterSSHTestBase

### Performance Requirements
- [ ] 2 test files → 2× speedup minimum
- [ ] 11 test files → 5× speedup minimum
- [ ] Production (20 devices, 11 types) → under 2 minutes total

### Quality Requirements
- [ ] 80%+ unit test coverage
- [ ] All integration tests pass
- [ ] No regressions in existing functionality
- [ ] Documentation complete and clear

---

## Future Enhancements

### Phase 2 (Post-MVP)
1. **Smart consolidation threshold:** Only consolidate if N > 2 (configurable)
2. **Custom verify_item() inlining:** Better handling of custom verification logic
3. **Parallel consolidation:** Generate consolidated files in parallel
4. **Caching:** Cache consolidated files if test files unchanged

### Phase 3 (Advanced)
1. **Auto-enable by default:** Make consolidation default after beta testing
2. **Mixed architecture support:** Consolidate across architectures if compatible
3. **Dynamic loading:** Load verification methods dynamically instead of dispatch
4. **Consolidation analytics:** Track consolidation metrics in reports

---

## Open Questions

1. **Fallback strategy:** If consolidation fails, should we:
   - ❓ Silently fall back to original files?
   - ❓ Fail fast with clear error?
   - ✅ **DECISION:** Fall back with warning log (graceful degradation)

2. **Opt-in vs opt-out:** Should consolidation be:
   - ✅ Opt-in initially (`--consolidate-d2d-tests`) for safety
   - ❓ Opt-out later (`--no-consolidate-d2d-tests`) after validation

3. **Custom verify_item():** How to handle tests with heavily customized verification?
   - ✅ **DECISION:** Extract full method body via AST, create dedicated method

4. **Consolidation threshold:** Minimum number of tests to justify consolidation?
   - ✅ **DECISION:** N ≥ 2 (any consolidation is beneficial due to fixed overhead)

---

## References

- **Manual PoC:** `/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/consolidated_verifications.py`
- **Performance Analysis:** `/Users/oboehmer/Documents/DD/nac-test/workspace/scale/PERFORMANCE_ANALYSIS.md`
- **PyATS Loop Marking:** https://pubhub.devnetcloud.com/media/pyats/docs/aetest/loop.html
- **Base Classes:**
  - `SSHTestBase`: `nac_test/pyats_core/common/ssh_base_test.py`
  - `IOSXETestBase`: `nac-test-pyats-common/src/nac_test_pyats_common/iosxe/test_base.py`

---

**Next Steps:**
1. Review design with team
2. Answer open questions
3. Begin implementation (Phase 1: Core Components)
4. Validate with integration tests
