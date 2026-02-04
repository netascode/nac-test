# Final Implementation Plan: Option D - Enhanced Combined Dashboard

## Executive Summary

**Objective**: Create a unified reporting dashboard at root level (`combined_summary.html`) that displays aggregated statistics for Robot Framework, PyATS API, and PyATS D2D tests. Additionally, return test statistics from orchestrators to CLI for issue #469 (failed test count visibility).

**Timeline**: 4-5 days

**Risk Level**: Very Low - reuses proven patterns and Robot Framework APIs

**Key Changes**:
1. Robot files output to `robot_results/` directory (via pabot options)
2. Backward-compatibility symlinks at root
3. New `nac_test/robot/reporting/` module (parser + generator)
4. New `nac_test/core/reporting/` module (combined generator)
5. Orchestrators return test statistics to CLI
6. Root-level `combined_summary.html` replaces `pyats_results/combined_summary.html`
7. PyATS summaries link back to root combined dashboard

---

## Architecture Decisions

### Module Structure

```
nac_test/
├── core/
│   └── reporting/                      # NEW: Core reporting orchestration
│       ├── __init__.py
│       └── combined_generator.py       # Orchestrates all frameworks
├── pyats_core/
│   └── reporting/
│       ├── generator.py                # MODIFIED: Returns stats
│       ├── multi_archive_generator.py  # MODIFIED: Returns stats instead of generating combined HTML
│       └── templates/
│           └── summary/
│               ├── report.html.j2      # MODIFIED: Add breadcrumb link
│               └── combined_report.html.j2  # MODIFIED: Add Robot badge CSS
└── robot/
    ├── reporting/                      # NEW: Robot reporting module
    │   ├── __init__.py
    │   ├── robot_parser.py             # Parse output.xml using ResultVisitor
    │   └── robot_generator.py          # Generate Robot summary report
    ├── orchestrator.py                 # MODIFIED: Create symlinks, return stats
    └── pabot.py                        # MODIFIED: Use --output, --log, --report options
```

### Statistics Return Format

All orchestrators return typed dataclasses from `nac_test.core.types`:

**RobotOrchestrator.run_tests() returns:**
```python
from nac_test.core.types import TestResults

# Returns TestResults (Robot doesn't distinguish test types)
TestResults(total=100, passed=97, failed=3, skipped=0, errors=[])
# str(): "100/97/3/0" (total/passed/failed/skipped)
```

**PyATSOrchestrator.run_tests() returns:**
```python
from nac_test.core.types import PyATSResults, TestResults

# Returns PyATSResults grouping API and D2D results
PyATSResults(
    api=TestResults(total=30, passed=28, failed=2, skipped=0, errors=[]),
    d2d=TestResults(total=20, passed=20, failed=0, skipped=0, errors=[])
)
# str(): "PyATSResults(API: 30/28/2/0, D2D: 20/20/0/0)"
```

**CombinedOrchestrator uses CombinedResults internally:**
```python
from nac_test.core.types import CombinedResults, TestResults

# CombinedResults aggregates all frameworks with explicit attributes
CombinedResults(
    api=TestResults(total=30, passed=28, failed=2, skipped=0, errors=[]),
    d2d=TestResults(total=20, passed=20, failed=0, skipped=0, errors=[]),
    robot=TestResults(total=100, passed=97, failed=3, skipped=0, errors=[])
)
# str(): "CombinedResults(API: 30/28/2/0, D2D: 20/20/0/0, Robot: 100/97/3/0)"

# CombinedResults provides computed properties:
combined.total    # 150 (sum across all frameworks)
combined.passed   # 145
combined.failed   # 5
combined.skipped  # 0
combined.success_rate  # 96.67%
combined.has_failures  # True
combined.exit_code     # 5 (min of failed count, 250)
```

### Efficiency: Avoid Re-reading JSONL Files

**Approach**: Modify `MultiArchiveReportGenerator._generate_combined_summary()` to:
- Read JSONL files once (as it does now)
- Return stats dict instead of generating HTML
- `CombinedReportGenerator` uses those stats to generate the combined HTML

This is the most efficient approach (Option A from our discussion).


## 🔍 OPEN DECISION: Robot Framework Deep Linking Enhancement

### Background

**Issue Discovered**: When linking from our Robot summary report to Robot's `log.html#test-id`, **passed tests remain collapsed** and are not visible to users. Only failed/skipped tests auto-expand.

**Root Cause**: Robot Framework's `makeElementVisible()` function (log.html line 2180) calls `expandFailed()` which only expands tests with status FAIL or SKIP (line 796). This is intentional Robot behavior - they collapse passed tests by default to reduce clutter.

**User Requirement**: When users click a test link from our summary report, they expect to see that test **regardless of whether it passed or failed**.

**Testing**: Confirmed in Firefox and Safari that navigating to `file:///tmp/log.html#s1-s1-t2-k4` (a passed test) does NOT expand the test. The hash is removed from the URL and the test remains collapsed.

---

### Constraint

**MUST NOT modify Robot's original log.html** - it is collected as an artifact and must remain pristine as generated by Robot Framework.

---

### Implementation Options for Team Review

#### Option A: Post-process log.html (REJECTED)
**Approach**: After Robot generates log.html, modify line 2184 to replace `expandFailed()` with `expandElement()`.

**Rejected Reason**: Violates constraint - modifies artifact file.

---

#### Option B: URL Parameter + Appended Script ⚠️

**Approach**:
1. Append a small enhancement script to the **end** of log.html (after `</body>`)
2. Summary report links to: `log.html?expand=true#s1-t2`
3. Appended script detects `?expand=true` and overrides behavior

**Pros**:
- ✅ Simple implementation (~30 lines appended)
- ✅ Doesn't modify Robot's original code (just appends)
- ✅ Works in all browsers
- ✅ Gracefully degrades if script fails

**Cons**:
- ⚠️ Still modifies log.html file (adds content at end)
- ⚠️ Timing-sensitive (needs setTimeout for Robot's lazy loading)
- ⚠️ Could conflict if Robot changes their internal structure
- ⚠️ May still be considered "altering the artifact"

**Implementation Snippet**:
```python
# In robot/orchestrator.py after pabot completes
def _add_deep_link_enhancement_script(self) -> None:
    """Append enhancement script to log.html for better deep linking."""
    log_html = self.output_dir / "robot_results" / "log.html"
    
    enhancement_script = """
<!-- NAC-Test Enhancement: Deep link expansion for all test statuses -->
<script type="text/javascript">
(function() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('expand') === 'true' && window.location.hash) {
        setTimeout(function() {
            const elementId = window.location.hash.substring(1);
            if (elementId && window.testdata) {
                window.testdata.ensureLoaded(elementId, function (ids) {
                    ids.forEach(id => expandElementWithId(id));
                    if (ids.length) {
                        const element = window.testdata.findLoaded(ids[ids.length - 1]);
                        if (element) {
                            expandElement(element);  // Force expand regardless of status
                            window.location.hash = elementId;
                            document.getElementById(elementId)?.scrollIntoView();
                        }
                    }
                });
            }
        }, 200);
    }
})();
</script>
</body>
</html>"""
    
    content = log_html.read_text(encoding='utf-8')
    content = content.replace('</body>\n</html>', enhancement_script)
    log_html.write_text(content, encoding='utf-8')
```

---

#### Option C: Wrapper HTML (iframe) ✅ RECOMMENDED

**Approach**:
1. Generate `robot_results/robot_log_viewer.html` wrapper page
2. Summary report links to: `robot_log_viewer.html#s1-t2`
3. Wrapper loads `log.html` in an iframe and controls navigation
4. **Original log.html remains 100% untouched**

**Pros**:
- ✅ **Original log.html completely untouched** - perfect for artifacts
- ✅ Clean separation of concerns (our code vs Robot's code)
- ✅ More maintainable long-term
- ✅ Can add future enhancements easily (filtering, highlighting, etc.)
- ✅ Users can still open log.html directly for Robot's default behavior
- ✅ Professional approach - respects Robot Framework's output

**Cons**:
- ⚠️ Slightly more complex than Option B
- ⚠️ Iframe approach (though should work fine for local files)
- ⚠️ Users might wonder why there's a wrapper file

**Implementation Snippet**:
```python
# In robot/reporting/robot_generator.py
async def _generate_log_viewer_wrapper(self) -> Path:
    """Generate wrapper HTML for enhanced log.html navigation.
    
    Creates robot_log_viewer.html that loads log.html in iframe with
    enhanced navigation. Original log.html remains completely untouched.
    """
    wrapper_html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Robot Framework Test Log</title>
    <style>
        body { margin: 0; padding: 0; overflow: hidden; }
        iframe { 
            width: 100vw; 
            height: 100vh; 
            border: none; 
            display: block; 
        }
    </style>
</head>
<body>
    <iframe id="logFrame" src="log.html"></iframe>
    <script>
        (function() {
            const iframe = document.getElementById('logFrame');
            const targetHash = window.location.hash;
            
            iframe.onload = function() {
                if (!targetHash) return;
                
                try {
                    const iframeWindow = iframe.contentWindow;
                    const elementId = targetHash.substring(1);
                    
                    setTimeout(function() {
                        if (iframeWindow.testdata && iframeWindow.expandElement) {
                            iframeWindow.testdata.ensureLoaded(elementId, function(ids) {
                                ids.forEach(id => iframeWindow.expandElementWithId(id));
                                if (ids.length) {
                                    const element = iframeWindow.testdata.findLoaded(ids[ids.length - 1]);
                                    if (element) {
                                        iframeWindow.expandElement(element);
                                        iframeWindow.location.hash = elementId;
                                        iframeWindow.document.getElementById(elementId)?.scrollIntoView();
                                    }
                                }
                            });
                        }
                    }, 300);
                } catch (e) {
                    console.warn('Failed to enhance navigation:', e);
                }
            };
            
            window.addEventListener('hashchange', function() {
                iframe.contentWindow.location.hash = window.location.hash;
            });
        })();
    </script>
</body>
</html>'''
    
    wrapper_path = self.robot_results_dir / "robot_log_viewer.html"
    wrapper_path.write_text(wrapper_html)
    logger.info(f"Created log viewer wrapper: {wrapper_path}")
    return wrapper_path

# Then in generate_summary_report(), link to wrapper instead of log.html:
results.append({
    "title": test["name"],
    "status": status,
    "duration": test["duration"],
    "timestamp": test["start_time"],
    "result_file_path": f"robot_log_viewer.html#{test['test_id']}",  # Link to wrapper
    "hostname": None,
})
```

---

#### Option D: Submit Enhancement to Robot Framework (Long-term)

**Approach**: Submit a PR or feature request to Robot Framework to add a URL parameter like `?autoexpand=true` that forces expansion of target elements regardless of status.

**Pros**:
- ✅ Proper upstream solution
- ✅ Benefits entire Robot community
- ✅ No workarounds needed

**Cons**:
- ⏰ Takes time (weeks/months)
- ⏰ Not under our control
- ⏰ Doesn't help current implementation

**Recommendation**: Pursue this in parallel with Options B or C for long-term benefit.

---

### Decision Required

**Team to decide**: Which option should we implement?

**Questions for Discussion**:
1. Is appending to log.html (Option B) acceptable, or does it violate the "pristine artifact" requirement?
2. Are there any concerns about iframe-based approach (Option C) in your deployment environment?
3. Should we pursue Option D (upstream PR) in parallel regardless of B/C choice?
4. Are there browser compatibility requirements we should test against?

**Recommendation from Technical Analysis**: **Option C (Wrapper HTML)** is the safest choice that preserves log.html integrity while providing the desired UX.

---

### Impact on Implementation Plan

**If Option B chosen**: Add to Phase 1 (Robot Orchestrator) - ~30 minutes
**If Option C chosen**: Add to Phase 3 (Robot Report Generator) - ~1-2 hours

Both options are low-risk and can be implemented without affecting other phases.

---

## Summary

I've documented three feasible options for the Robot Framework deep linking enhancement:

- **Option B**: Append enhancement script to end of log.html (modifies file slightly)
- **Option C**: Create wrapper HTML with iframe (log.html untouched) ✅ **RECOMMENDED**
- **Option D**: Submit to Robot Framework upstream (long-term)

The document includes:
- ✅ Background and root cause analysis
- ✅ Testing details (Firefox/Safari behavior)
- ✅ Pros/cons for each option
- ✅ Implementation code snippets
- ✅ Questions for team discussion
- ✅ Impact on implementation timeline

---

## Detailed Implementation Plan

### Phase 1: Robot Output Directory Changes ✅ COMPLETE (Day 1, Morning - 2-3 hours)

#### File: `nac_test/robot/pabot.py`

**Changes**:

1. Add `output_dir` parameter to `run_pabot()`:

```python
def run_pabot(
    output_dir: Path,  # NEW parameter
    path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    processes: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    ordering_file: Path | None = None,
    extra_args: list[str] | None = None,
) -> int:
    """Run pabot with output to robot_results/ subdirectory.
    
    Args:
        output_dir: Base output directory (robot files go to output_dir/robot_results/)
        path: Path to Robot test files
        # ... other params ...
    """
    include = include or []
    exclude = exclude or []
    robot_args: list[str] = []
    pabot_args = ["--pabotlib", "--pabotlibport", "0"]

    # ... existing pabot args setup ...

    # Define robot_results paths
    robot_results_dir = output_dir / "robot_results"
    robot_results_dir.mkdir(parents=True, exist_ok=True)
    
    # Use individual file options (do NOT change outputdir)
    robot_args.extend([
        "--output", str(robot_results_dir / "output.xml"),
        "--log", str(robot_results_dir / "log.html"),
        "--report", str(robot_results_dir / "report.html"),
        "--xunit", str(robot_results_dir / "xunit.xml"),
        "--skiponfailure", "non-critical",
    ])

    # ... rest of existing code ...
    
    args = pabot_args + robot_args + [str(path)]
    logger.info("Running pabot with args: %s", " ".join(args))
    exit_code: int = pabot.pabot.main_program(args)
    if exit_code != 0:
        raise RuntimeError(f"Pabot execution failed with exit code {exit_code}")
    return 0
```

**Note**: We do NOT change the CWD or use `--outputdir`. This preserves existing Robot use cases.

#### File: `nac_test/robot/orchestrator.py`

**Changes**:

1. Update `run_tests()` signature to return `TestResults`:

```python
from nac_test.core.types import TestResults

def run_tests(self) -> TestResults:
    """Execute Robot Framework tests.
    
    Returns:
        TestResults with test statistics (total, passed, failed, skipped, errors)
    """
    # ... existing setup code ...
    
    # Run pabot with output_dir parameter
    exit_code = run_pabot(
        output_dir=self.output_dir,  # NEW
        path=self.output_dir,
        include=self.include_tags,
        exclude=self.exclude_tags,
        processes=self.processes,
        dry_run=self.dry_run,
        verbose=self.verbosity >= VerbosityLevel.DEBUG,
        ordering_file=ordering_file,
        extra_args=self.extra_args,
    )
    
    # Create backward-compatibility symlinks at root
    self._create_backward_compat_symlinks()
    
    # Parse results and return stats
    return self._get_test_statistics()
```

2. Add helper methods:

```python
def _create_backward_compat_symlinks(self) -> None:
    """Create symlinks at root pointing to robot_results/ for backward compatibility.
    
    Creates:
        output.xml -> robot_results/output.xml
        log.html -> robot_results/log.html
        report.html -> robot_results/report.html
        xunit.xml -> robot_results/xunit.xml
    """
    robot_results_dir = self.output_dir / "robot_results"
    files_to_link = ["output.xml", "log.html", "report.html", "xunit.xml"]
    
    for filename in files_to_link:
        source = robot_results_dir / filename
        target = self.output_dir / filename
        
        if source.exists():
            # Remove existing file/symlink if it exists
            if target.exists() or target.is_symlink():
                target.unlink()
            # Create relative symlink
            target.symlink_to(f"robot_results/{filename}")
            logger.debug(f"Created symlink: {target} -> robot_results/{filename}")

def _get_test_statistics(self) -> TestResults:
    """Get test statistics from Robot output.xml.
    
    Returns:
        TestResults with total, passed, failed, skipped counts
    """
    output_xml = self.output_dir / "robot_results" / "output.xml"
    
    if not output_xml.exists():
        logger.warning("No output.xml found, returning empty stats")
        return TestResults.empty()
    
    try:
        from robot.api import ExecutionResult
        
        result = ExecutionResult(str(output_xml))
        stats = result.statistics.total.all
        
        return TestResults(
            total=stats.total,
            passed=stats.passed,
            failed=stats.failed,
            skipped=stats.skipped,
        )
    except Exception as e:
        logger.error(f"Failed to read Robot statistics: {e}")
        return TestResults.from_error(str(e))
```

**Tests to Add** (create `tests/unit/robot/test_orchestrator.py`):
- Test symlink creation
- Test symlink overwriting existing files
- Test statistics parsing
- Test missing output.xml handling

---

### Phase 2: Robot Report Parser ✅ COMPLETE (Day 1, Afternoon - 3-4 hours)

#### File: `nac_test/robot/reporting/__init__.py`

```python
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot Framework reporting module."""

from nac_test.robot.reporting.robot_generator import RobotReportGenerator
from nac_test.robot.reporting.robot_output_parser import RobotResultParser

__all__ = ["RobotReportGenerator", "RobotResultParser"]
```

#### File: `nac_test/robot/reporting/robot_output_parser.py`

```python
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot Framework output.xml parser using ResultVisitor API.

This module uses Robot Framework's ExecutionResult and ResultVisitor APIs
to extract test statistics and individual test results from output.xml.

Example usage from nac-test-utils/result-analysis/analyze_longest_suites.py.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from robot.api import ExecutionResult, ResultVisitor

logger = logging.getLogger(__name__)


class TestDataCollector(ResultVisitor):
    """ResultVisitor that collects test statistics and individual test data.
    
    This visitor traverses the Robot Framework result tree and collects:
    - Aggregated statistics (total, passed, failed, skipped)
    - Individual test details (name, status, duration, message, test_id)
    
    Failed tests are automatically sorted to the top of the results list.
    
    Attributes:
        tests: List of test result dictionaries
        stats: Aggregated statistics dictionary
    """

    def __init__(self):
        """Initialize the test data collector."""
        self.tests: list[dict[str, Any]] = []
        self.stats = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "success_rate": 0.0,
        }

    def visit_test(self, test):
        """Visit each test and collect its data.
        
        Called by ExecutionResult.visit() for each test case.
        
        Args:
            test: Robot Framework test object with attributes:
                - name: Test name
                - status: 'PASS', 'FAIL', or 'SKIP'
                - starttime: Start timestamp string (format: '20250131 12:34:56.789')
                - endtime: End timestamp string
                - elapsedtime: Duration in milliseconds
                - message: Result message
                - id: Test ID for deep linking (e.g., 's1-t3', 's1-s2-t5')
                - parent: Parent suite object
        """
        # Extract test data
        status = test.status  # PASS, FAIL, SKIP
        
        # Calculate duration (elapsedtime is in milliseconds)
        duration_seconds = test.elapsedtime / 1000.0 if test.elapsedtime else 0.0
        
        # Parse start time
        start_time = self._parse_timestamp(test.starttime)
        start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S") if start_time else ""
        
        # Get parent suite name
        suite_name = test.parent.name if test.parent else "Unknown Suite"
        
        # Collect test data
        test_data = {
            "name": test.name,
            "status": status,
            "duration": duration_seconds,
            "start_time": start_time_str,
            "message": test.message.strip() if test.message else "",
            "test_id": test.id,  # e.g., 's1-s2-t3' for suite1.suite2.test3
            "suite_name": suite_name,
        }
        
        self.tests.append(test_data)
        
        # Update statistics
        self.stats["total_tests"] += 1
        if status == "PASS":
            self.stats["passed_tests"] += 1
        elif status == "FAIL":
            self.stats["failed_tests"] += 1
        elif status == "SKIP":
            self.stats["skipped_tests"] += 1

    def end_suite(self, suite):
        """Called when suite ends - calculate final statistics.
        
        We calculate success rate at the root suite level (when parent is None).
        Also sort tests to put failed tests first.
        
        Args:
            suite: Robot Framework suite object
        """
        if suite.parent is None:
            # This is the root suite - finalize statistics
            total = self.stats["total_tests"]
            skipped = self.stats["skipped_tests"]
            passed = self.stats["passed_tests"]
            
            tests_with_results = total - skipped
            if tests_with_results > 0:
                self.stats["success_rate"] = (passed / tests_with_results) * 100
            
            # Sort tests: failed first, then by name
            self.tests.sort(key=lambda t: (t["status"] != "FAIL", t["name"]))
            
            logger.debug(
                f"Collected {total} tests: {passed} passed, "
                f"{self.stats['failed_tests']} failed, {skipped} skipped"
            )

    @staticmethod
    def _parse_timestamp(timestamp_str: str) -> datetime | None:
        """Parse Robot Framework timestamp format.
        
        Robot Framework uses format: '20250131 12:34:56.789' or '20250131 12:34:56'
        
        Args:
            timestamp_str: Timestamp string from Robot Framework
            
        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp_str:
            return None
        try:
            # Try with milliseconds first
            return datetime.strptime(timestamp_str, '%Y%m%d %H:%M:%S.%f')
        except ValueError:
            try:
                # Try without milliseconds
                return datetime.strptime(timestamp_str, '%Y%m%d %H:%M:%S')
            except ValueError:
                logger.warning(f"Failed to parse timestamp: {timestamp_str}")
                return None


class RobotResultParser:
    """Parser for Robot Framework output.xml files.
    
    Uses Robot Framework's ExecutionResult API with a custom ResultVisitor
    to extract test statistics and individual test results.
    
    Example:
        >>> parser = RobotResultParser(Path("output.xml"))
        >>> data = parser.parse()
        >>> print(data["aggregated_stats"])
        {'total_tests': 100, 'passed_tests': 97, 'failed_tests': 3, ...}
    """

    def __init__(self, output_xml_path: Path):
        """Initialize parser with path to output.xml.
        
        Args:
            output_xml_path: Path to Robot Framework's output.xml file
        """
        self.output_xml_path = output_xml_path

    def parse(self) -> dict[str, Any]:
        """Parse output.xml and extract all data.
        
        Returns:
            Dictionary containing:
                - aggregated_stats: Overall statistics dict with keys:
                    - total_tests, passed_tests, failed_tests, skipped_tests, success_rate
                - tests: List of individual test result dicts with keys:
                    - name, status, duration, start_time, message, test_id, suite_name
                
        Raises:
            FileNotFoundError: If output.xml doesn't exist
            Exception: If parsing fails
        """
        if not self.output_xml_path.exists():
            raise FileNotFoundError(f"output.xml not found: {self.output_xml_path}")

        try:
            # Use Robot Framework's ExecutionResult API
            logger.info(f"Parsing Robot results from {self.output_xml_path}")
            result = ExecutionResult(str(self.output_xml_path))
            
            # Visit the result tree with our custom collector
            collector = TestDataCollector()
            result.visit(collector)
            
            logger.info(
                f"Parsed {collector.stats['total_tests']} tests "
                f"({collector.stats['passed_tests']} passed, "
                f"{collector.stats['failed_tests']} failed, "
                f"{collector.stats['skipped_tests']} skipped)"
            )
            
            return {
                "aggregated_stats": collector.stats,
                "tests": collector.tests,
            }
            
        except Exception as e:
            logger.error(f"Failed to parse {self.output_xml_path}: {e}")
            raise
```

**Tests to Add** (create `tests/unit/robot/reporting/test_robot_parser.py`):
- Test parsing valid output.xml with mixed statuses
- Test with all tests passed
- Test with all tests failed
- Test with skipped tests
- Test status sorting (failed tests first)
- Test timestamp parsing (with and without milliseconds)
- Test missing file handling
- Test empty results (no tests)
- Test test_id extraction for deep linking

---

### Phase 3: Robot Report Generator ✅ COMPLETE (Day 2, Morning - 3-4 hours)

#### File: `nac_test/robot/reporting/robot_generator.py`

```python
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot Framework HTML report generator.

Generates summary report following PyATS dashboard pattern for visual consistency.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from nac_test.pyats_core.reporting.templates import TEMPLATES_DIR, get_jinja_environment
from nac_test.robot.reporting.robot_output_parser import RobotResultParser

logger = logging.getLogger(__name__)


class RobotReportGenerator:
    """Generates HTML summary report for Robot Framework tests.
    
    Follows the same pattern as PyATS ReportGenerator for consistency:
    - Reuses PyATS Jinja2 templates and styling
    - Creates summary_report.html with test list and sortable columns
    - Links to log.html with deep linking to specific tests (log.html#test-id)
    - Failed tests highlighted at top
    
    Attributes:
        output_dir: Base output directory
        robot_results_dir: robot_results subdirectory
        output_xml_path: Path to output.xml
        log_html_path: Path to log.html
        env: Jinja2 environment (shared with PyATS)
    """

    def __init__(self, output_dir: Path):
        """Initialize Robot report generator.
        
        Args:
            output_dir: Base output directory where robot_results/ exists
        """
        self.output_dir = output_dir
        self.robot_results_dir = output_dir / "robot_results"
        self.output_xml_path = self.robot_results_dir / "output.xml"
        self.log_html_path = self.robot_results_dir / "log.html"
        
        # Initialize Jinja2 environment (reuse PyATS templates)
        self.env = get_jinja_environment(TEMPLATES_DIR)

    async def generate_summary_report(self) -> Path | None:
        """Generate Robot summary report asynchronously.
        
        Creates robot_results/summary_report.html with:
        - List of all Robot tests (failed at top)
        - Columns: Test Name, Status, Duration, Date, Action
        - Sortable/filterable (JavaScript from PyATS template)
        - Links to log.html#test-id for detailed view
        - Same styling as PyATS summaries for consistency
        
        Returns:
            Path to generated summary report, or None if generation fails or no tests found
        """
        try:
            # Check if output.xml exists
            if not self.output_xml_path.exists():
                logger.warning(f"No Robot results found at {self.output_xml_path}")
                return None
            
            # Parse output.xml using ResultVisitor
            logger.info(f"Parsing Robot results from {self.output_xml_path}")
            parser = RobotResultParser(self.output_xml_path)
            data = parser.parse()
            
            # Get aggregated stats
            stats = data["aggregated_stats"]
            
            # If no tests, don't generate report
            if stats["total_tests"] == 0:
                logger.info("No Robot tests found, skipping summary report")
                return None
            
            # Prepare results for template (match PyATS format)
            results = []
            for test in data["tests"]:
                # Map Robot status (PASS/FAIL/SKIP) to PyATS format (passed/failed/skipped)
                # This allows reusing PyATS template's status_style filter
                status_map = {"PASS": "passed", "FAIL": "failed", "SKIP": "skipped"}
                status = status_map.get(test["status"], "skipped")
                
                results.append({
                    "title": test["name"],
                    "status": status,
                    "duration": test["duration"],
                    "timestamp": test["start_time"],
                    # Deep link to Robot's log.html with test ID anchor
                    "result_file_path": f"log.html#{test['test_id']}",
                    "hostname": None,  # Robot tests don't have per-device structure
                })
            
            # Render template (reuse PyATS summary template)
            template = self.env.get_template("summary/report.html.j2")
            html_content = template.render(
                generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                total_tests=stats["total_tests"],
                passed_tests=stats["passed_tests"],
                failed_tests=stats["failed_tests"],
                skipped_tests=stats["skipped_tests"],
                success_rate=stats["success_rate"],
                results=results,
            )
            
            # Write summary report
            summary_path = self.robot_results_dir / "summary_report.html"
            summary_path.write_text(html_content)
            
            logger.info(f"Generated Robot summary report: {summary_path}")
            logger.info(
                f"  Tests: {stats['total_tests']} total, "
                f"{stats['passed_tests']} passed, {stats['failed_tests']} failed"
            )
            
            return summary_path
            
        except Exception as e:
            logger.error(f"Failed to generate Robot summary report: {e}")
            return None

    def get_aggregated_stats(self) -> dict[str, Any]:
        """Get aggregated statistics without generating full report.
        
        Used by combined dashboard to show Robot block stats.
        This is more efficient than generating the full HTML report.
        
        Returns:
            Dictionary with aggregated statistics:
                - total_tests, passed_tests, failed_tests, skipped_tests, success_rate
            Returns zeros if output.xml doesn't exist or parsing fails.
        """
        try:
            if not self.output_xml_path.exists():
                logger.debug(f"No Robot output.xml found at {self.output_xml_path}")
                return self._empty_stats()
            
            parser = RobotResultParser(self.output_xml_path)
            data = parser.parse()
            return data["aggregated_stats"]
            
        except Exception as e:
            logger.warning(f"Failed to get Robot statistics: {e}")
            return self._empty_stats()

    @staticmethod
    def _empty_stats() -> dict[str, Any]:
        """Return empty statistics structure.
        
        Used when no Robot tests were run or parsing fails.
        """
        return {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "success_rate": 0.0,
        }
```

**Tests to Add** (create `tests/unit/robot/reporting/test_robot_generator.py`):
- Test summary report generation
- Test with various test statuses
- Test get_aggregated_stats()
- Test missing output.xml returns empty stats
- Test empty stats structure
- Test status mapping (PASS→passed, FAIL→failed, SKIP→skipped)
- Test deep link generation (log.html#test-id)

---

### Phase 4: Core Combined Report Generator ✅ COMPLETE (Day 2, Afternoon - 3-4 hours)

#### File: `nac_test/core/reporting/__init__.py`

```python
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Core reporting module for combined test results across all frameworks."""

from nac_test.core.reporting.combined_generator import CombinedReportGenerator

__all__ = ["CombinedReportGenerator"]
```

#### File: `nac_test/core/reporting/combined_generator.py`

```python
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Combined report generator for all test frameworks.

Orchestrates report generation across PyATS, Robot Framework, and future frameworks,
creating a unified dashboard at the root level.
"""

import logging
from datetime import datetime
from pathlib import Path

from nac_test.core.types import CombinedResults
from nac_test.pyats_core.reporting.templates import TEMPLATES_DIR, get_jinja_environment

logger = logging.getLogger(__name__)


class CombinedReportGenerator:
    """Generates combined dashboard across all test frameworks.
    
    Creates root-level combined_summary.html with up to 3 blocks (Robot, API, D2D).
    Accepts CombinedResults directly - no dict transformation needed.
    
    Attributes:
        output_dir: Base output directory for all test results
        env: Jinja2 environment (shared with PyATS)
    """

    def __init__(self, output_dir: Path):
        """Initialize combined report generator.
        
        Args:
            output_dir: Base output directory for all test results
        """
        self.output_dir = output_dir
        self.env = get_jinja_environment(TEMPLATES_DIR)

    def generate_combined_summary(
        self, results: CombinedResults | None = None
    ) -> Path | None:
        """Generate combined summary dashboard.
        
        Args:
            results: CombinedResults with api, d2d, robot TestResults.
                    If None, generates empty dashboard.
        
        Returns:
            Path to combined_summary.html at root level, or None if generation fails
        """
        try:
            if results is None:
                results = CombinedResults()
            
            # Build test_type_stats for template (preserving template compatibility)
            test_type_stats = {}
            
            if results.api is not None:
                test_type_stats["API"] = {
                    "title": "API",
                    "total_tests": results.api.total,
                    "passed_tests": results.api.passed,
                    "failed_tests": results.api.failed,
                    "skipped_tests": results.api.skipped,
                    "success_rate": results.api.success_rate,
                    "report_path": "pyats_results/api/html_reports/summary_report.html",
                }
            
            if results.d2d is not None:
                test_type_stats["D2D"] = {
                    "title": "Direct-to-Device (D2D)",
                    "total_tests": results.d2d.total,
                    "passed_tests": results.d2d.passed,
                    "failed_tests": results.d2d.failed,
                    "skipped_tests": results.d2d.skipped,
                    "success_rate": results.d2d.success_rate,
                    "report_path": "pyats_results/d2d/html_reports/summary_report.html",
                }
            
            if results.robot is not None:
                test_type_stats["ROBOT"] = {
                    "title": "Robot Framework",
                    "total_tests": results.robot.total,
                    "passed_tests": results.robot.passed,
                    "failed_tests": results.robot.failed,
                    "skipped_tests": results.robot.skipped,
                    "success_rate": results.robot.success_rate,
                    "report_path": "robot_results/summary_report.html",
                }
            
            # Use CombinedResults computed properties for overall stats
            overall_stats = {
                "total_tests": results.total,
                "passed_tests": results.passed,
                "failed_tests": results.failed,
                "skipped_tests": results.skipped,
                "success_rate": results.success_rate,
            }
            
            # Render combined summary template
            template = self.env.get_template("summary/combined_report.html.j2")
            html_content = template.render(
                generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                overall_stats=overall_stats,
                test_type_stats=test_type_stats,
            )
            
            # Write to root-level combined_summary.html
            combined_summary_path = self.output_dir / "combined_summary.html"
            combined_summary_path.write_text(html_content)
            
            logger.info(f"Generated combined dashboard: {combined_summary_path}")
            logger.info(f"  Results: {results}")  # Uses __str__: "CombinedResults(API: 30/28/2/0, ...)"
            
            return combined_summary_path
            
        except Exception as e:
            logger.error(f"Failed to generate combined summary: {e}")
            return None
```

**Tests to Add** (create `tests/unit/core/reporting/test_combined_generator.py`):
- Test combined summary with CombinedResults(api, d2d, robot)
- Test combined summary with Robot only (robot attribute set)
- Test combined summary with PyATS only (api/d2d attributes set)
- Test combined summary with None results (empty dashboard)
- Test CombinedResults computed properties used correctly
- Test template receives correct data structure

---

### Phase 5: Update PyATS Multi-Archive Generator ✅ COMPLETE (Day 3, Morning - 3 hours)

#### File: `nac_test/pyats_core/reporting/multi_archive_generator.py`

**Changes**:

1. Rename `_generate_combined_summary()` to `_collect_pyats_stats()` and modify to return stats instead of generating HTML:

```python
async def _collect_pyats_stats(
    self, results: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Collect PyATS statistics for combined dashboard.
    
    Reads JSONL files once to extract statistics for API and D2D test types.
    Does NOT generate combined_summary.html (that's done by CombinedReportGenerator).
    
    Args:
        results: Dictionary mapping archive types to their generation results
    
    Returns:
        Dictionary mapping archive type to stats dict.
        Format: {"API": {...stats...}, "D2D": {...stats...}}
        Each stats dict contains: title, total_tests, passed_tests, failed_tests,
        skipped_tests, success_rate, report_path
    """
    test_type_stats = {}
    
    for archive_type, result in results.items():
        if result.get("status") != "success":
            continue

        # Read JSONL files from the archive's html_report_data directory
        archive_dir = self.pyats_results_dir / archive_type
        json_dir = archive_dir / "html_reports" / "html_report_data"

        stats = {
            "title": "API" if archive_type == "api" else "Direct-to-Device (D2D)",
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "success_rate": 0.0,
            "report_path": f"pyats_results/{archive_type}/html_reports/summary_report.html",
        }

        # Read all JSONL files to calculate statistics
        # (Keep existing JSONL reading logic from lines 348-379)
        if json_dir.exists():
            for jsonl_file in json_dir.glob("*.jsonl"):
                try:
                    test_data = await self._read_jsonl_summary(jsonl_file)
                    status = test_data.get(
                        "overall_status", ResultStatus.SKIPPED.value
                    )

                    stats["total_tests"] = int(stats.get("total_tests", 0)) + 1

                    if status == ResultStatus.PASSED.value:
                        stats["passed_tests"] = (
                            int(stats.get("passed_tests", 0)) + 1
                        )
                    elif status in [
                        ResultStatus.FAILED.value,
                        ResultStatus.ERRORED.value,
                    ]:
                        stats["failed_tests"] = (
                            int(stats.get("failed_tests", 0)) + 1
                        )
                    elif status == ResultStatus.SKIPPED.value:
                        stats["skipped_tests"] = (
                            int(stats.get("skipped_tests", 0)) + 1
                        )

                except Exception as e:
                    logger.warning(
                        f"Failed to read test data from {jsonl_file}: {e}"
                    )

        # Calculate success rate for this test type
        total_tests = int(stats.get("total_tests", 0))
        skipped_tests = int(stats.get("skipped_tests", 0))
        passed_tests = int(stats.get("passed_tests", 0))

        tests_with_results = total_tests - skipped_tests
        if tests_with_results > 0:
            stats["success_rate"] = (passed_tests / tests_with_results) * 100

        test_type_stats[archive_type.upper()] = stats
    
    return test_type_stats
```

2. Update `generate_reports_from_archives()` to collect and return PyATS stats:

```python
async def generate_reports_from_archives(
    self, archive_paths: list[Path]
) -> dict[str, Any]:
    """Generate reports from multiple PyATS archives.
    
    This is the main entry point that coordinates the entire process:
    1. Extracts each archive to its appropriate subdirectory
    2. Runs ReportGenerator on each extracted archive
    3. Collects PyATS statistics (but does NOT generate combined summary)
    
    The combined summary is now generated by CombinedReportGenerator which
    includes both PyATS and Robot results.
    
    Args:
        archive_paths: List of paths to PyATS archive files
    
    Returns:
        Dictionary containing:
            - status: 'success', 'partial', or 'failed'
            - results: Dict mapping archive type to generation results
            - pyats_stats: Dict of PyATS statistics by framework (API/D2D) - NEW
            - duration: Total time taken
    """
    start_time = datetime.now()

    if not archive_paths:
        logger.warning("No archive paths provided")
        return {
            "status": "failed",
            "results": {},
            "pyats_stats": None,
            "duration": 0,
        }

    # ... existing archive extraction and processing code (lines 89-158) ...

    # Collect PyATS stats for combined dashboard
    pyats_stats = None
    successful_archives = [
        k for k, v in results.items() if v.get("status") == "success"
    ]
    
    if len(successful_archives) > 0:
        try:
            pyats_stats = await self._collect_pyats_stats(results)
        finally:
            # Clean up JSONL files after collecting stats
            os.environ.pop("KEEP_HTML_REPORT_DATA", None)
            await self._cleanup_all_jsonl_files()
    elif len(archive_paths) > 1:
        # Multiple archives were requested but not all succeeded, still clean up
        os.environ.pop("KEEP_HTML_REPORT_DATA", None)
        await self._cleanup_all_jsonl_files()

    # Determine overall status
    # ... existing status determination code (lines 150-157) ...

    return {
        "status": overall_status,
        "duration": (datetime.now() - start_time).total_seconds(),
        "results": results,
        "pyats_stats": pyats_stats,  # NEW: Return stats for CombinedReportGenerator
    }
```

**Note**: This approach ensures JSONL files are read only once (efficient as required).

**Tests to Update**:
- Update existing tests for `MultiArchiveReportGenerator` to check for `pyats_stats` in return value
- Test that `_collect_pyats_stats()` returns correct format
- Test that JSONL files are cleaned up after stats collection

---

### Phase 6: Update PyATS Orchestrator ✅ COMPLETE (Day 3, Afternoon - 2 hours)

#### File: `nac_test/pyats_core/orchestrator.py`

**Changes**:

1. Update `run_tests()` signature to return `PyATSResults`:

```python
from nac_test.core.types import PyATSResults, TestResults

def run_tests(self) -> PyATSResults:
    """Execute PyATS tests (API and/or D2D).
    
    Returns:
        PyATSResults with api and d2d TestResults (either may be None)
    """
    # ... existing test discovery and execution code ...
    
    # After report generation, extract stats from report result
    return self._extract_pyats_stats(report_result)

def _extract_pyats_stats(self, report_result: dict) -> PyATSResults:
    """Extract PyATSResults from report generation result.
    
    Args:
        report_result: Dict from MultiArchiveReportGenerator
    
    Returns:
        PyATSResults with api/d2d TestResults (either may be None)
    """
    api_results = None
    d2d_results = None
    
    if pyats_stats := report_result.get("pyats_stats"):
        if api_stats := pyats_stats.get("API"):
            api_results = TestResults(
                total=api_stats["total_tests"],
                passed=api_stats["passed_tests"],
                failed=api_stats["failed_tests"],
                skipped=api_stats["skipped_tests"],
            )
        if d2d_stats := pyats_stats.get("D2D"):
            d2d_results = TestResults(
                total=d2d_stats["total_tests"],
                passed=d2d_stats["passed_tests"],
                failed=d2d_stats["failed_tests"],
                skipped=d2d_stats["skipped_tests"],
            )
    
    return PyATSResults(api=api_results, d2d=d2d_results)
```

**Tests to Update**:
- Update existing PyATS orchestrator tests to check return value
- Test stats aggregation across API and D2D

---

### Phase 7: Update Combined Orchestrator ✅ COMPLETE (Day 3, Afternoon - 3 hours)

#### File: `nac_test/combined_orchestrator.py`

**Changes**:

1. Update `run_tests()` to use typed results:

```python
from nac_test.core.types import CombinedResults, PyATSResults, TestResults

def run_tests(self) -> CombinedResults:
    """Main entry point for combined test execution.
    
    Handles development modes (PyATS only, Robot only) and production mode (combined).
    
    Returns:
        CombinedResults with api, d2d, robot TestResults (any may be None)
    """
    # Note: Output directory and merged data file created by main.py
    combined_results = CombinedResults()

    # Handle development mode (PyATS only)
    if self.dev_pyats_only:
        typer.secho(
            "\n\n⚠️  WARNING: --pyats flag is for development use only.",
            fg=typer.colors.YELLOW,
        )
        typer.echo("🧪 Running PyATS tests only (development mode)...")
        self._check_python_version()

        orchestrator = PyATSOrchestrator(...)
        if self.max_parallel_devices is not None:
            orchestrator.max_parallel_devices = self.max_parallel_devices
        pyats_results = orchestrator.run_tests()  # Returns PyATSResults
        
        combined_results.api = pyats_results.api
        combined_results.d2d = pyats_results.d2d
        return combined_results

    # Handle development mode (Robot only)
    if self.dev_robot_only:
        typer.secho(
            "\n\n⚠️  WARNING: --robot flag is for development use only.",
            fg=typer.colors.YELLOW,
        )
        typer.echo("🤖 Running Robot Framework tests only (development mode)...")

        robot_orchestrator = RobotOrchestrator(...)
        combined_results.robot = robot_orchestrator.run_tests()  # Returns TestResults
        return combined_results

    # Production mode: Combined execution
    has_pyats, has_robot = self._discover_test_types()

    if not has_pyats and not has_robot:
        typer.echo("No test files found")
        return combined_results  # Empty CombinedResults

    # Sequential execution - PyATS first
    if has_pyats:
        typer.echo("\n🧪 Running PyATS tests...\n")
        self._check_python_version()

        orchestrator = PyATSOrchestrator(...)
        if self.max_parallel_devices is not None:
            orchestrator.max_parallel_devices = self.max_parallel_devices
        pyats_results = orchestrator.run_tests()  # Returns PyATSResults
        
        combined_results.api = pyats_results.api
        combined_results.d2d = pyats_results.d2d

    # Then Robot
    if has_robot:
        typer.echo("\n🤖 Running Robot Framework tests...\n")

        robot_orchestrator = RobotOrchestrator(...)
        combined_results.robot = robot_orchestrator.run_tests()  # Returns TestResults
        
        # Generate Robot summary report
        if not self.render_only and not self.dry_run:
            typer.echo("\n📊 Generating Robot summary report...")
            from nac_test.robot.reporting.robot_generator import RobotReportGenerator
            import asyncio
            
            robot_generator = RobotReportGenerator(self.output_dir)
            loop = asyncio.get_event_loop()
            summary_path = loop.run_until_complete(
                robot_generator.generate_summary_report()
            )
            if summary_path:
                typer.echo(f"   ✅ {summary_path}")

    # Generate combined dashboard if any tests ran
    if not combined_results.is_empty:
        typer.echo("\n📊 Generating combined dashboard...")
        from nac_test.core.reporting.combined_generator import CombinedReportGenerator
        import asyncio
        
        combined_generator = CombinedReportGenerator(self.output_dir)
        loop = asyncio.get_event_loop()
        combined_path = loop.run_until_complete(
            combined_generator.generate_combined_summary(combined_results)
        )
        if combined_path:
            typer.echo(f"   ✅ Combined dashboard: {combined_path}")

    # Print summary using CombinedResults computed properties
    self._print_execution_summary(combined_results)
    
    return combined_results

def _print_execution_summary(self, results: CombinedResults) -> None:
    """Print execution summary with statistics.
    
    Args:
        results: CombinedResults with api, d2d, robot TestResults
    """
    if self.dev_pyats_only or self.dev_robot_only:
        return

    typer.echo("\n" + "=" * 70)
    typer.echo("📋 Combined Test Execution Summary")
    typer.echo("=" * 70)
    
    # Show overall stats using CombinedResults computed properties
    typer.echo(f"\n📊 Overall Results:")
    typer.echo(f"   Total: {results.total} tests")
    typer.echo(f"   ✅ Passed: {results.passed}")
    typer.echo(f"   ❌ Failed: {results.failed}")
    typer.echo(f"   ⊘ Skipped: {results.skipped}")
    
    # Combined dashboard is the main entry point
    typer.echo("\n🎯 Combined Dashboard:")
    typer.echo(f"   📊 {self.output_dir}/combined_summary.html")
    typer.echo("   (Aggregated results from all test frameworks)")

    if results.robot:
        typer.echo("\n✅ Robot Framework tests: Completed")
        typer.echo(f"   📁 Results: {self.output_dir}/robot_results/")
        typer.echo(
            f"   📊 {results.robot.total} tests: "
            f"{results.robot.passed} passed, {results.robot.failed} failed"
        )
        if not self.render_only:
            typer.echo(f"   📊 Summary: {self.output_dir}/robot_results/summary_report.html")
            typer.echo(f"   📊 Detailed: {self.output_dir}/robot_results/log.html")

    if results.api or results.d2d:
        typer.echo("\n✅ PyATS tests: Completed")
        typer.echo(f"   📁 Results: {self.output_dir}/pyats_results/")
        if results.api:
            typer.echo(f"   📊 API: {results.api.total} tests ({results.api.passed} passed)")
        if results.d2d:
            typer.echo(f"   📊 D2D: {results.d2d.total} tests ({results.d2d.passed} passed)")

    typer.echo(f"\n📄 Merged data model: {self.output_dir}/{self.merged_data_filename}")
    typer.echo("=" * 70)
```

**Note**: The `_get_pyats_dashboard_stats()` method is no longer needed since `PyATSOrchestrator.run_tests()` now returns `PyATSResults` directly with the api/d2d breakdown.

**Tests to Update**:
- Update existing combined orchestrator tests to check return value
- Test stats aggregation
- Test by_framework breakdown
- Test with only PyATS tests
- Test with only Robot tests
- Test with both test types

---

### Phase 8: Update CLI Main ✅ COMPLETE (Day 4, Morning - 1 hour)

#### File: `nac_test/cli/main.py`

**Changes**:

1. Update main CLI entry point to use returned CombinedResults (for issue #469):

```python
from nac_test.core.types import CombinedResults

@cli.command()
@click.pass_context
def run(...):
    """Run tests."""
    # ... existing setup code ...
    
    # Create and run orchestrator
    orchestrator = CombinedOrchestrator(...)
    results = orchestrator.run_tests()  # Returns CombinedResults
    
    # Use CombinedResults computed properties for exit code (issue #469)
    if results.has_failures:
        typer.echo(
            f"\n❌ Tests failed: {results.failed} out of {results.total} tests",
            err=True
        )
        raise typer.Exit(results.exit_code)  # Uses CombinedResults.exit_code property
    elif results.is_empty:
        typer.echo("\n⚠️  No tests were executed", err=True)
        raise typer.Exit(1)
    else:
        typer.echo(f"\n✅ All tests passed: {results.passed} out of {results.total} tests")
        raise typer.Exit(0)
```

**Tests to Update**:
- Update CLI tests to check exit codes based on test results
- Test with failed tests (exit code 1)
- Test with all passed tests (exit code 0)
- Test with no tests (exit code 1)

---

### Phase 9: Update Templates ✅ COMPLETE (Day 4, Morning - 1 hour)

#### File: `nac_test/pyats_core/reporting/templates/summary/combined_report.html.j2`

**Changes**:

1. Add Robot badge CSS after line 79:

```css
.robot-badge {
    background-color: rgba(231, 76, 60, 0.15);
    color: var(--danger);
    border: 1px solid var(--danger);
}
```

**Note**: The template already shows blocks with 0 tests (displays "0" in counts). No need to add conditional logic unless user wants to hide empty blocks later.

#### File: `nac_test/pyats_core/reporting/templates/summary/report.html.j2`

**Changes**:

1. Add breadcrumb navigation in header (after line 56):

```html
header h1 {
    color: white;
    margin-bottom: 10px;
}

/* Add breadcrumb styles */
.breadcrumb {
    margin-top: 10px;
    font-size: 14px;
}
.breadcrumb a {
    color: rgba(255, 255, 255, 0.9);
    text-decoration: none;
}
.breadcrumb a:hover {
    color: white;
    text-decoration: underline;
}
```

2. Add breadcrumb HTML in header section (after line 381):

```html
<header>
    <div class="container">
        <h1>Network as Code Test Results Summary</h1>
        <div class="date-info">Generated on {{ generation_time }}</div>
        <div class="breadcrumb">
            <a href="../../combined_summary.html">← Back to Combined Dashboard</a>
        </div>
    </div>
</header>
```

---

### Phase 10: Unit Tests ✅ COMPLETE (Day 4, Afternoon - 4 hours)

Create comprehensive unit tests for all new modules:

#### `tests/unit/robot/test_orchestrator.py`
- Test `_create_backward_compat_symlinks()`
- Test `_get_test_statistics()`
- Test return value format
- Test missing output.xml

#### `tests/unit/robot/test_robot_parser.py`
- Test `TestDataCollector` visitor
- Test parsing with mixed statuses
- Test sorting (failed first)
- Test timestamp parsing
- Test empty results
- Test statistics calculation

#### `tests/unit/robot/test_robot_generator.py`
- Test `generate_summary_report()`
- Test `get_aggregated_stats()`
- Test status mapping
- Test deep link generation
- Test missing output.xml

#### `tests/unit/core/test_combined_generator.py`
- Test combined summary generation
- Test with Robot + PyATS
- Test with Robot only
- Test with PyATS only
- Test stats accumulation
- Test success rate calculation

#### Update existing tests:
- `tests/unit/pyats_core/reporting/test_multi_archive_generator.py`
- `tests/unit/pyats_core/test_orchestrator.py`
- `tests/unit/test_combined_orchestrator.py`
- `tests/unit/cli/test_main.py`

---

### Phase 11: Integration Tests ✅ COMPLETE (Day 5 - Placeholder)

**Implementation Status**: ✅ COMPLETE

Integration tests already exist and pass:
- `test_phase1_robot_output_directory_and_symlinks`: Comprehensive test covering Phases 1-9
- `test_combined_reporting_happy_path`: Full E2E test for all scenarios

**Test Coverage:**
- ✅ Combined tests (PyATS + Robot) run successfully
- ✅ combined_summary.html exists at root
- ✅ Robot, API, D2D blocks present in dashboard
- ✅ robot_results/summary_report.html exists
- ✅ Symlinks created at root
- ✅ Statistics accuracy across all frameworks
- ✅ Exit codes based on test results
- ✅ Directory structure verified
- ✅ Report generation validated

**Test Results:**
- 2 integration tests: 2 passed, 0 failed
- Test duration: ~60 seconds each
- All assertions passing

**Actual Implementation:**

See `tests/integration/test_combined_reporting.py` for complete test implementation covering:
- `test_phase1_robot_output_directory_and_symlinks()` - Phases 1-9 validation
- `test_combined_reporting_happy_path()` - Full E2E validation

---

### Phase 12: Update PRD Documentation ✅ COMPLETE (Day 5 - 1 hour)

**Implementation Status**: ✅ COMPLETE

Added comprehensive "Combined Reporting Dashboard" section to `dev-docs/PRD_AND_ARCHITECTURE.md`.

**Changes Made**:

Added comprehensive "Combined Reporting Dashboard" section to `dev-docs/PRD_AND_ARCHITECTURE.md` (after line 3503).

**Documentation Includes:**

1. **Architecture Overview**
   - Module structure and organization
   - Report file structure
   - Backward compatibility symlinks

2. **Component Documentation**
   - `CombinedReportGenerator`: Orchestrates unified dashboard
   - `RobotResultParser`: Parses output.xml using ResultVisitor
   - `RobotReportGenerator`: Generates Robot summary reports

3. **Statistics Flow Diagram**
   - Mermaid diagram showing data flow from test execution to CLI exit codes
   - Clear visualization of orchestrator interactions

4. **API Documentation**
   - Method signatures and return types
   - Statistics format specifications
   - Integration points between components

5. **Features Documentation**
   - Unified dashboard capabilities
   - Framework badges and visual indicators
   - Deep linking strategy
   - Breadcrumb navigation

6. **Backward Compatibility**
   - Symlink structure documented
   - Migration path for existing tools

See lines 3506-3712 in `dev-docs/PRD_AND_ARCHITECTURE.md` for complete documentation.

---

## Implementation Summary

```
{output_dir}/
├── combined_summary.html                  # NEW: Root-level combined dashboard
├── merged_data_model_test_variables.yaml
├── robot_results/                         # NEW: Robot results directory
│   ├── output.xml
│   ├── log.html
│   ├── report.html
│   ├── xunit.xml
│   └── summary_report.html                # NEW: Robot summary (PyATS style)
├── output.xml                             #