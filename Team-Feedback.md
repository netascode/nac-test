# Changes/Enhancements/Feature Requests

## Issue #1 - nac-test: Output directory behavior

Was:
tests/results/aci/ (this is in reality selected via -o, what the user means is that this is the typical path customers use )

But now in this version of nac-test is:
Tests/results/aci/robot_results/

And pyats is:
tests/results/aci/pyats_results/api/html_reports/

This looks better now from logical point of view, but changing robot testing output folder would be problematic for every customer using older version of nac-test/iac-test after they upgrade. This will fail their pipelines, because they will be not able to save artifacts properly.

Suggested fix:

1) keep current old robot test cases at the "root" (where -o is), and then just have a pyats_results sub-folder for interop between the two for now.

### Technical Implementation

**Problem:**
Robot Framework results moved from root output directory to `robot_results/` subdirectory, breaking existing CI/CD pipelines.

**Solution:**
Remove subdirectory creation for Robot Framework while keeping PyATS in its subdirectory.

**Implementation:**

1. **File:** `nac_test/robot/orchestrator.py`

   ```python
   # Line 68-70, change from:
   self.output_dir = self.base_output_dir / "robot_results"

   # To:
   self.output_dir = self.base_output_dir  # Keep at root for backward compatibility
   ```

2. **File:** `nac_test/combined_orchestrator.py`

   ```python
   # Line 224, change from:
   typer.echo(f"   📁 Results: {self.output_dir}/robot_results/")

   # To:
   typer.echo(f"   📁 Results: {self.output_dir}/")
   ```

**Testing:**

- Run combined test execution
- Verify Robot results at root level
- Verify PyATS results in subdirectory
- Test with existing CI/CD pipeline configuration

**Impact:**

- Zero breaking changes for existing users
- Clean separation maintained between frameworks
- No performance impact

**Recommended Directory Structure (Option 1):**

```
tests/results/aci/                    # -o output directory
├── report.html                       # Robot report (backward compatible)
├── log.html                          # Robot log (backward compatible)
├── output.xml                        # Robot output (backward compatible)
├── *.robot                          # Generated Robot test files
├── merged_data_model_test_variables.yaml
└── pyats_results/                   # PyATS results in subdirectory
    ├── api/
    │   └── html_reports/
    └── device/
        └── html_reports/
```

**Implementation Effort:**

- Code changes: 2-3 hours
- Testing: 4-6 hours
- Documentation updates: 2 hours
- Total: ~1-2 days

**Risk Assessment:**

- Low risk with Option 1 (simple reversion)
- Medium risk with Option 2 (requires testing both modes)
- Medium risk with Option 3 (filesystem complexity)

**Next Steps:**

1. Decide on approach (recommend Option 1)
2. Implement changes in robot/orchestrator.py
3. Update combined_orchestrator.py output messages
4. Test with sample customer pipeline configurations
5. Document any migration requirements

## Issue #2 - This is really a results thing

In Robot, we can see what is expected in the YAML versus what is actually returned from the APIC, making it more obvious when and where things don't align.

### Technical Implementation

**Problem:**
PyATS HTML reports don't show expected vs actual values side-by-side, making it hard to debug test failures.

**Solution:**
Enhance failure messages to include expected/actual comparison data and display in HTML reports.

**Implementation:**

1. **File:** `nac_test/pyats_core/reporting/collector.py`

   ```python
   # Enhance add_result to accept comparison data
   def add_result(
       self, status: ResultStatus, message: str,
       test_context: Optional[str] = None,
       expected: Optional[Any] = None,  # NEW
       actual: Optional[Any] = None     # NEW
   ) -> None:
       # ... existing code ...
       record = {
           "type": "result",
           "status": status.value,
           "message": message,
           "context": context,
           "expected": expected,  # NEW - store expected value
           "actual": actual,      # NEW - store actual value
           "timestamp": datetime.now().isoformat(),
       }
   ```

2. **File:** `nac_test/pyats_core/reporting/templates/test_case/report.html.j2`

   ```html
   <!-- Add comparison display for failed results -->
   {% if result.status == "failed" and result.expected %}
   <div class="comparison-table">
       <h4>Expected vs Actual:</h4>
       <table>
           <tr>
               <th>Expected (YAML)</th>
               <th>Actual (API)</th>
           </tr>
           <tr>
               <td><pre>{{ result.expected | tojson(indent=2) }}</pre></td>
               <td><pre>{{ result.actual | tojson(indent=2) }}</pre></td>
           </tr>
       </table>
   </div>
   {% endif %}
   ```

3. **Update test files to pass comparison data** (example):

   ```python
   # In test files when comparing values
   if actual_value != expected_value:
       self.result_collector.add_result(
           ResultStatus.FAILED,
           f"Value mismatch for {field_name}",
           expected=expected_value,
           actual=actual_value
       )
   ```

**Note:** Most test files already have expected/actual values in their comparison logic, they just need to pass them to the collector.

## Issue #3 -- nac-test: Add flag to only produce results for FAILED in HTML

re there any plans to optimise further? e.g. file size of artifacts (3.5g+ etc) i.e. do we benefit from seeing JSON output from the passed tests? Maybe this could be a debug toggle instead?

### Technical Implementation

**Problem:**
Test artifacts exceed 3.5GB due to storing full command outputs for all tests, including passed ones.

**Solution:**
Add `--failed-only` flag to skip storing command outputs for passing tests (90% size reduction).

**Implementation:**

1. **File:** `nac_test/cli/main.py`

   ```python
   # Add new CLI option
   FailedOnly = Annotated[
       bool,
       typer.Option(
           "--failed-only",
           help="Only store detailed output for failed tests",
           envvar="NAC_TEST_FAILED_ONLY",
       ),
   ]

   # Add to main() signature
   def main(..., failed_only: FailedOnly = False, ...):
   ```

2. **File:** `nac_test/pyats_core/orchestrator.py`

   ```python
   # Add to __init__
   def __init__(..., failed_only: bool = False):
       self.failed_only = failed_only

   # Pass to collector via environment (line ~200)
   # Note: Environment variable is correct here since tests run in subprocesses
   env["NAC_TEST_FAILED_ONLY"] = str(self.failed_only)
   ```

3. **File:** `nac_test/combined_orchestrator.py`

   ```python
   # Pass failed_only to PyATS orchestrator (line ~147)
   orchestrator = PyATSOrchestrator(
       data_paths=self.data_paths,
       test_dir=self.templates_dir,
       output_dir=self.output_dir,
       merged_data_filename=self.merged_data_filename,
       failed_only=self.failed_only  # NEW - pass through
   )
   ```

4. **File:** `nac_test/pyats_core/reporting/collector.py`

   ```python
   # In __init__ (line ~30)
   self.failed_only = os.environ.get("NAC_TEST_FAILED_ONLY", "False") == "True"

   # Store commands always, filter later based on final test status
   # No changes to add_command_api_execution - store everything
   ```

5. **File:** `nac_test/pyats_core/reporting/generator.py`

   ```python
   # In _read_jsonl_results(), filter commands for failed-only mode
   async def _read_jsonl_results(self, jsonl_path: Path) -> Dict[str, Any]:
       # ... existing code to read JSONL ...

       # Filter command executions if in failed-only mode
       failed_only = os.environ.get("NAC_TEST_FAILED_ONLY", "False") == "True"
       if failed_only and test_data.get("overall_status") == "passed":
           # Remove command executions for passed tests to save space
           test_data["command_executions"] = []

       return test_data
   ```

**Benefits:**

- Immediate 80-95% reduction in artifact size
- Faster report generation
- Preserves all critical debugging information
- Simple implementation with minimal risk

**Expected Results:**

| Mode | Typical Size | Use Case |
|------|-------------|----------|
| Normal (current) | 3.5GB+ | Deep debugging |
| Failed-only | ~100-500MB | Normal CI/CD runs |

**Implementation Details:**

- Add CLI flag: `--failed-only`
- Pass flag through orchestrator to collector
- Conditionally skip command output storage for passing tests
- Keep all test results/status information regardless

**Implementation Effort:**

- Code changes: 4-6 hours
- Testing: 2-3 hours
- Documentation: 1 hour
- Total: ~1 day

**Backward Compatibility:**

- Default behavior unchanged (full output)
- Opt-in via `--failed-only` flag
- Environment variable override: `NAC_TEST_FAILED_ONLY`

**Next Steps:**

1. Implement failed-only flag in collector.py
2. Add CLI parameter and pass through orchestrators
3. Test with large test suites to verify size reduction
4. Document flag usage in README and help text

## Issue #4 - Can we click on total tests summary (i.e. failed, passed, skipped, to filter/sort a view similar to how we do in Robot results?)

Table for later. Need to ask the HSBC internal team for speciics perhaps. Or mock something to see...

### Technical Implementation (Simplified)

**Problem:**
Users want to click on test summary counts (Passed/Failed/Skipped) to filter the results view.

**Solution:**
Make summary counts clickable to filter test results table (basic Robot Framework parity).

**Implementation:**

**1. File:** `nac_test/pyats_core/reporting/templates/summary/report.html.j2`

```html
<!-- Make summary counts clickable (modify existing summary cards) -->
<div class="summary-item passed" onclick="filterTests('passed')" style="cursor: pointer;">
    <p>Passed</p>
    <h3>{{ passed_tests }}</h3>
</div>
<div class="summary-item failed" onclick="filterTests('failed')" style="cursor: pointer;">
    <p>Failed</p>
    <h3>{{ failed_tests }}</h3>
</div>
<div class="summary-item skipped" onclick="filterTests('skipped')" style="cursor: pointer;">
    <p>Skipped</p>
    <h3>{{ skipped_tests }}</h3>
</div>

<!-- Add JavaScript at bottom of template -->
<script>
let currentFilter = '';

function filterTests(status) {
    // Toggle filter on/off if clicking same status
    currentFilter = (currentFilter === status) ? '' : status;

    const rows = document.querySelectorAll('.results-table tbody tr');
    rows.forEach(row => {
        const testStatus = row.querySelector('.status-cell').textContent.toLowerCase();
        if (currentFilter === '' || testStatus.includes(currentFilter)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });

    // Update visual feedback
    document.querySelectorAll('.summary-item').forEach(item => {
        item.style.opacity = currentFilter ? '0.6' : '1';
    });
    if (currentFilter) {
        document.querySelector('.summary-item.' + currentFilter).style.opacity = '1';
        document.querySelector('.summary-item.' + currentFilter).style.boxShadow = '0 0 0 2px var(--accent)';
    }
}

// Simple column sorting
function sortTable(column) {
    const table = document.querySelector('.results-table tbody');
    const rows = Array.from(table.querySelectorAll('tr'));

    rows.sort((a, b) => {
        const aText = a.children[column].textContent;
        const bText = b.children[column].textContent;
        return aText.localeCompare(bText);
    });

    rows.forEach(row => table.appendChild(row));
}
</script>

<!-- Make column headers clickable for sorting -->
<thead>
    <tr>
        <th onclick="sortTable(0)" style="cursor: pointer;">Test Name ↕</th>
        <th onclick="sortTable(1)" style="cursor: pointer;">Status ↕</th>
        <th onclick="sortTable(2)" style="cursor: pointer;">Date ↕</th>
        <th>Action</th>
    </tr>
</thead>
```

**Benefits:**

- Click summary counts to filter (matches basic Robot behavior)
- Click again to clear filter
- Sortable columns
- Minimal complexity, maximum value

**Implementation Effort:**

- Template changes: 1-2 hours
- Testing: 1 hour
- **Total: 2-3 hours** (not 2-3 days)

**Files to Modify:**

- `nac_test/pyats_core/reporting/templates/summary/report.html.j2` - Add click handlers and JavaScript

## Issue #5 - nac-test: Can we have tests by default sorted by Failed > Skipped > Passed similar to how we do in Robot results?

### Technical Implementation

**Problem:**
Tests sorted by timestamp, burying failed tests in long lists.

**Solution:**
Sort by status (Failed → Skipped → Passed) with timestamp as secondary sort.

**Implementation:**

**File:** `nac_test/pyats_core/reporting/generator.py`

```python
# Line 371, replace:
all_results.sort(key=lambda x: x["timestamp"])

# With:
status_priority = {"failed": 0, "errored": 0, "skipped": 1, "passed": 2}
all_results.sort(key=lambda x: (
    status_priority.get(x["status"], 3),
    x["timestamp"]
))
```

**Benefits:**

- Failed tests always appear at the top
- Matches Robot Framework convention
- No UI changes needed
- Preserves timestamp ordering within each status group

**Implementation Effort:**

- Code change: 5 minutes
- Testing: 15 minutes
- Total: ~20 minutes

**Files to Modify:**

- `nac_test/pyats_core/reporting/generator.py:371`

**Next Steps:**

1. Replace sort logic in generator.py
2. Test with reports containing mixed statuses
3. Done

## Issue #6 -- nac-test: Keep current folder sturcture but add cross-compatibility support

Can we have this working against HSBC's current test folder structure? (example below) This makes retrofitting the test structure into their current environments much simpler.

i.e. hsbc setup doesn't currently have the additional folders of, [ > apic > test > ], can we get this working without changing this structure?

### Technical Implementation

**Problem:**
Tests must be under `/api/` or `/d2d/` directories. HSBC organizes by functionality (config, operational) not test type.

**Solution:**
Make api/d2d categorization optional. Uncategorized tests default to API type.

**Implementation:**

1. **File:** `nac_test/pyats_core/discovery/test_discovery.py`

   ```python
   # Line 108, modify method signature:
   def categorize_tests_by_type(
       self, test_files: List[Path], strict_mode: bool = False
   ) -> Tuple[List[Path], List[Path]]:

   # Line 140-152, replace error handling with:
   if not strict_mode and uncategorized:
       logger.info(f"Found {len(uncategorized)} tests outside api/d2d - treating as API tests")
       api_tests.extend(uncategorized)
       uncategorized = []

   if strict_mode and uncategorized:
       # Keep existing error for strict mode
       raise ValueError(...)
   ```

2. **File:** `nac_test/pyats_core/orchestrator.py`

   ```python
   # Add to __init__ (line ~50):
   def __init__(..., strict_structure: bool = False):
       self.strict_structure = strict_structure

   # Pass to categorize_tests_by_type (line ~where it's called):
   api_tests, d2d_tests = self.test_discovery.categorize_tests_by_type(
       test_files, strict_mode=self.strict_structure
   )
   ```

3. **File:** `nac_test/cli/main.py`

   ```python
   # Add CLI option:
   StrictStructure = Annotated[
       bool,
       typer.Option(
           "--strict-structure",
           help="Enforce api/d2d directory structure",
           envvar="NAC_TEST_STRICT_STRUCTURE",
       ),
   ]

   # Add to main() signature:
   def main(..., strict_structure: StrictStructure = False, ...):
       # Pass to CombinedOrchestrator
       orchestrator = CombinedOrchestrator(
           ...,
           strict_structure=strict_structure,
       )
   ```

4. **File:** `nac_test/combined_orchestrator.py`

   ```python
   # Add to __init__:
   def __init__(..., strict_structure: bool = False):
       self.strict_structure = strict_structure

   # Pass to PyATSOrchestrator (line ~147):
   orchestrator = PyATSOrchestrator(
       data_paths=self.data_paths,
       test_dir=self.templates_dir,
       output_dir=self.output_dir,
       merged_data_filename=self.merged_data_filename,
       strict_structure=self.strict_structure  # NEW
   )
   ```

**Benefits:**

- **Backward Compatible:** Existing users with api/d2d structure work unchanged
- **Flexible:** HSBC can use any folder structure they want
- **Simple:** Uncategorized tests default to API type (most common)
- **Optional Strict Mode:** Can still enforce structure if desired

**Alternative: Auto-detect Test Type by Content**

```python
def detect_test_type(test_file: Path) -> str:
    """Detect if test is API or D2D based on content."""
    content = test_file.read_text()

    # D2D tests typically have device connections
    if "testbed" in content or "device.connect" in content:
        return "d2d"

    # Default to API
    return "api"
```

