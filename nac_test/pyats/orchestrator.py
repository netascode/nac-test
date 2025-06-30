# -*- coding: utf-8 -*-

"""Main PyATS orchestration logic for nac-test."""

import multiprocessing as mp
from pathlib import Path
import psutil
import os
from typing import List, Dict, Any, Optional
import logging
import subprocess
import tempfile
import textwrap
import threading
import queue
import json
import re
import zipfile
import shutil
from datetime import datetime

from .constants import (
    DEFAULT_CPU_MULTIPLIER,
    MEMORY_PER_WORKER_GB,
    MAX_WORKERS_HARD_LIMIT,
    DEFAULT_TEST_TIMEOUT,
)
from .progress_reporter import ProgressReporter
from nac_test.data_merger import DataMerger

logger = logging.getLogger(__name__)


class PyATSOrchestrator:
    """Orchestrates PyATS test execution with dynamic resource management."""

    def __init__(
        self,
        data_paths: List[Path],
        test_dir: Path,
        output_dir: Path,
        merged_data_filename: str,
    ):
        """Initialize the PyATS orchestrator.

        Args:
            data_paths: List of paths to data model YAML files
            test_dir: Directory containing PyATS test files
            output_dir: Directory for test output
            merged_data_filename: Name of the merged data model file
        """
        self.data_paths = data_paths
        self.test_dir = Path(test_dir)
        self.output_dir = Path(output_dir)
        self.merged_data_filename = merged_data_filename
        self.max_workers = self._calculate_workers()
        # Note: ProgressReporter will be initialized later with total test count

    def _calculate_workers(self) -> int:
        """Calculate optimal worker count based on CPU and memory"""
        # CPU-based calculation
        cpu_workers = mp.cpu_count() * DEFAULT_CPU_MULTIPLIER

        # Memory-based calculation
        available_memory = psutil.virtual_memory().available
        # Convert from bytes to GB
        memory_workers = int(
            available_memory / (MEMORY_PER_WORKER_GB * 1024 * 1024 * 1024)
        )

        # Consider system load
        load_avg = os.getloadavg()[0]  # 1-minute load average
        if load_avg > mp.cpu_count():
            cpu_workers = max(1, int(cpu_workers * 0.5))  # Reduce if system is loaded

        # Use the more conservative limit
        actual_workers = max(
            1, min(cpu_workers, memory_workers, MAX_WORKERS_HARD_LIMIT)
        )

        # Allow override via environment variable
        return int(os.environ.get("PYATS_MAX_WORKERS", actual_workers))

    def validate_environment(self) -> None:
        """Pre-flight check: Validate required environment variables before running tests.
        
        This ensures we fail fast with clear error messages rather than starting
        PyATS only to have all tests fail due to missing configuration.
        
        Raises:
            SystemExit: If required environment variables are missing
        """
        # Get controller type (defaults to ACI in the MVP)
        controller_type = os.environ.get("CONTROLLER_TYPE", "ACI")
        
        # Define required environment variables based on controller type
        required_vars = [
            f"{controller_type}_URL",
            f"{controller_type}_USERNAME",
            f"{controller_type}_PASSWORD"
        ]
        
        # Check for missing variables
        missing = [var for var in required_vars if not os.environ.get(var)]
        
        if missing:
            # Get formatted error message for terminal display
            error_msg = terminal.format_env_var_error(missing, controller_type)
            
            # Print the colored error message
            print(error_msg)
            
            # Exit with error code (don't start PyATS)
            sys.exit(1)
    def discover_pyats_tests(self) -> List[Path]:
        """Find all .py test files when --pyats flag is set

        Searches for Python test files in the standard test directories:
        - */test/config/
        - */test/operational/
        - */test/health/

        This mirrors the Robot Framework test structure while excluding
        utility directories like pyats_common and jinja_filters.
        """
        test_files = []

        # Use rglob for recursive search - finds .py files at any depth
        for test_path in self.test_dir.rglob("*.py"):
            # Skip non-test files
            if "__pycache__" in str(test_path):
                continue
            if test_path.name.startswith("_"):
                continue
            if test_path.name == "__init__.py":
                continue

            # Convert to string for efficient path checking
            path_str = str(test_path)

            # Only include files in the standard test directories
            if (
                "/test/config/" in path_str
                or "/test/operational/" in path_str
                or "/test/health/" in path_str
            ):
                # Exclude utility directories
                if "pyats_common" not in path_str and "jinja_filters" not in path_str:
                    test_files.append(test_path)

        return sorted(test_files)

    def _generate_job_file_content(self, test_files: List[Path]) -> str:
        """Generate the content for a PyATS job file"""
        # Convert test file paths to strings for the job file
        test_files_str = ",\n        ".join([f'"{str(tf)}"' for tf in test_files])

        job_content = textwrap.dedent(f'''
        """Auto-generated PyATS job file by nac-test"""
        
        import os
        from pathlib import Path
        
        # Test files to execute
        TEST_FILES = [
            {test_files_str}
        ]
        
        def main(runtime):
            """Main job file entry point"""
            # Set max workers
            runtime.max_workers = {self.max_workers}
            
            # Note: runtime.directory is read-only and set by --archive-dir
            # The output directory is: {str(self.output_dir)}
            
            # Run all test files
            for idx, test_file in enumerate(TEST_FILES):
                runtime.tasks.run(
                    testscript=test_file,
                    taskid=f"test_{{idx}}",
                    max_runtime={DEFAULT_TEST_TIMEOUT}
                )
        ''')

        return job_content

    def run_tests(self) -> None:
        """Main entry point from nac-test CLI with real-time progress reporting"""
        # Pre-flight check: Validate environment variables BEFORE doing anything else
        self.validate_environment()
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Merge data files and write to output directory for tests to access
        merged_data = DataMerger.merge_data_files(self.data_paths)
        DataMerger.write_merged_data_model(
            merged_data, self.output_dir, self.merged_data_filename
        )

        # Discover test files
        test_files = self.discover_pyats_tests()

        if not test_files:
            print("No PyATS test files (*.py) found in test directory")
            return

        print(f"Discovered {len(test_files)} PyATS test files")
        print(f"Running with {self.max_workers} parallel workers")

        # Create progress reporter with total test count and max workers
        self.progress_reporter = ProgressReporter(
            total_tests=len(test_files), max_workers=self.max_workers
        )

        # Generate job file content
        job_content = self._generate_job_file_content(test_files)

        # Create temporary job file
        with tempfile.NamedTemporaryFile(mode="w", suffix="_job.py", delete=False) as f:
            f.write(job_content)
            job_file = f.name

        # Create temporary plugin configuration file
        plugin_config = textwrap.dedent("""
        plugins:
            ProgressReporterPlugin:
                enabled: True
                module: nac_test.pyats.progress_plugin
                order: 1.0
        """)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_plugin_config.yaml", delete=False
        ) as f:
            f.write(plugin_config)
            plugin_config_file = f.name

        try:
            # Generate controlled archive name with timestamp
            job_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            archive_name = f"nac_test_job_{job_timestamp}.zip"
            self.archive_name = archive_name  # Store for later reference

            # Build PyATS command with plugin configuration
            cmd = [
                "pyats",
                "run",
                "job",
                job_file,
                "--configuration",
                plugin_config_file,
                "--archive-dir",
                str(self.output_dir),
                "--archive-name",
                archive_name,
                "--no-archive-subdir",  # Prevent YY-MM subdirectory creation
                "--no-mail",  # Disable email notifications
            ]

            # Set up environment to suppress warnings and set PYTHONPATH
            env = os.environ.copy()
            env["PYTHONWARNINGS"] = "ignore::UserWarning"
            # Suppress verbose logs
            env["PYATS_LOG_LEVEL"] = "ERROR"
            env["HTTPX_LOG_LEVEL"] = "ERROR"

            # Set the DATA_FILE environment variable to point to the merged data model
            env["DATA_FILE"] = str(self.output_dir / self.merged_data_filename)

            # Add the test directory to PYTHONPATH so imports work
            # This allows "from pyats_common.<architecture>_base_test import <ARCHITECTURE>TestBase" to work
            test_parent_dir = str(self.test_dir)

            # Also add nac-test directory so the plugin can be imported
            nac_test_dir = str(
                Path(__file__).parent.parent.parent
            )  # Go up to nac-test root

            if "PYTHONPATH" in env:
                env["PYTHONPATH"] = (
                    f"{test_parent_dir}{os.pathsep}{nac_test_dir}{os.pathsep}{env['PYTHONPATH']}"
                )
            else:
                env["PYTHONPATH"] = f"{test_parent_dir}{os.pathsep}{nac_test_dir}"

            # Run with output capture
            print(f"Executing PyATS with command: {' '.join(cmd)}")
            return_code = self._run_with_progress(cmd, test_files, env)

            if return_code != 0:
                # Only log error for critical failures (not test failures)
                # Return code 1 = some tests failed (expected)
                # Return code > 1 = execution error (unexpected)
                if return_code > 1:
                    logger.error(
                        f"PyATS execution failed with return code: {return_code}"
                    )
        finally:
            # Clean up temporary files
            os.unlink(job_file)
            os.unlink(plugin_config_file)

    def _run_with_progress(
        self, cmd: List[str], test_files: List[Path], env: Dict[str, str]
    ) -> int:
        """Run PyATS command with real-time progress reporting"""
        self.test_status: Dict[str, Dict[str, Any]] = {}
        self.start_time = datetime.now()

        # Initialize progress reporter's test_status reference
        self.progress_reporter.test_status = self.test_status

        # Start subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=env,
            cwd=str(self.output_dir),
        )

        # Process output in real-time
        output_queue: queue.Queue[str] = queue.Queue()

        def read_output() -> None:
            if process.stdout:
                line_count = 0  # Initialize line_count
                for line in iter(process.stdout.readline, ""):
                    line_count += 1
                    output_queue.put(line)
                process.stdout.close()

        # Start output reader thread
        reader_thread = threading.Thread(target=read_output)
        reader_thread.daemon = True
        reader_thread.start()

        # Process output and report progress
        while True:
            try:
                line = output_queue.get(timeout=0.1)
                self._process_output_line(line.strip())
            except queue.Empty:
                if process.poll() is not None:
                    break

        # Wait for process to complete
        return_code = process.wait()

        # Print summary
        self._print_summary()

        return return_code

    def _process_output_line(self, line: str) -> None:
        """Process output line, looking for our progress events"""
        # Look for our structured progress events
        if line.startswith("NAC_PROGRESS:"):
            try:
                # Parse our JSON event
                event_json = line[13:]  # Remove "NAC_PROGRESS:" prefix
                event = json.loads(event_json)

                # Validate event schema version
                if event.get("version", "1.0") != "1.0":
                    logger.warning(
                        f"Unknown event schema version: {event.get('version')}"
                    )

                self._handle_progress_event(event)
            except json.JSONDecodeError:
                # If parsing fails, show the line in debug mode
                if os.environ.get("PYATS_DEBUG"):
                    print(f"Failed to parse progress event: {line}")
            except Exception as e:
                logger.error(f"Error processing progress event: {e}")
        else:
            # Show line if it matches our criteria
            if self._should_show_line(line):
                print(line)

    def _handle_progress_event(self, event: Dict[str, Any]) -> None:
        """Handle structured progress event from plugin"""
        event_type = event.get("event")

        if event_type == "task_start":
            # Assign global test ID
            test_id = self.progress_reporter.get_next_test_id()

            # Report test starting
            self.progress_reporter.report_test_start(
                event["test_name"], event["pid"], event["worker_id"], test_id
            )

            # Track status with assigned test ID and title
            self.test_status[event["test_name"]] = {
                "start_time": event["timestamp"],
                "status": "EXECUTING",
                "worker": event["worker_id"],
                "test_id": test_id,
                "taskid": event["taskid"],
                "title": event.get(
                    "test_title", event["test_name"]
                ),  # Use test_name as final fallback
            }

        elif event_type == "task_end":
            # Retrieve the test ID we assigned at start
            test_info = self.test_status.get(event["test_name"], {})
            test_id = test_info.get("test_id", 0)

            # Report test completion
            self.progress_reporter.report_test_end(
                event["test_name"],
                event["pid"],
                event["worker_id"],
                test_id,
                event["result"],
                event["duration"],
            )

            # Update status
            if event["test_name"] in self.test_status:
                self.test_status[event["test_name"]].update(
                    {"status": event["result"], "duration": event["duration"]}
                )

            # After progress reporter shows the line, add title display
            title = test_info.get("title", event["test_name"])
            status_text = event["result"].upper()

            # Display title line like Robot Framework
            print("-" * 78)
            print(f"{title:<70} | {status_text} |")
            print("-" * 78)

        elif event_type == "section_start" and os.environ.get("PYATS_DEBUG"):
            # In debug mode, show section progress
            print(f"  -> Section {event['section']} starting")

        elif event_type == "section_end" and os.environ.get("PYATS_DEBUG"):
            print(f"  -> Section {event['section']} {event['result']}")

    def _should_show_line(self, line: str) -> bool:
        """Determine if line should be shown to user"""
        # In debug mode, show everything
        if os.environ.get("PYATS_DEBUG"):
            return True

        # Always suppress these patterns
        suppress_patterns = [
            r"%HTTPX-INFO:",
            r"%AETEST-INFO:",
            r"%AETEST-ERROR:",  # Suppress error details unless debugging
            r"%EASYPY-INFO:",
            r"%WARNINGS-WARNING:",
            r"%GENIE-INFO:",
            r"%UNICON-INFO:",
            r"NAC_PROGRESS_PLUGIN:",  # Suppress plugin debug output
            r"^\s*$",  # Empty lines
            r"^\+[-=]+\+$",  # PyATS table borders
            r"^\|.*\|$",  # PyATS table content
        ]

        for pattern in suppress_patterns:
            if re.search(pattern, line):
                return False

        # Only show critical errors in production mode
        show_patterns = [
            r"ERROR",
            r"FAILED",
            r"CRITICAL",
            r"Traceback",
            r"Exception.*Error",
        ]

        for pattern in show_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True

        return False

    def _find_pyats_output_files(self) -> Dict[str, Any]:
        """Find PyATS generated output files in archive directory"""
        output_files: Dict[str, Any] = {}

        # Look for our controlled archive name
        if hasattr(self, "archive_name"):
            archive_path = self.output_dir / self.archive_name
            if archive_path.exists():
                # Extract the zip file to a temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)

                    # Extract zip contents
                    with zipfile.ZipFile(archive_path, "r") as zip_ref:
                        zip_ref.extractall(temp_path)

                    # Now look for the actual PyATS output files
                    patterns = {
                        "results_json": "results.json",
                        "results_xml": "ResultsDetails.xml",
                        "summary_xml": "ResultsSummary.xml",
                        "report": "*.report",
                        "job_log": "JobLog.*",
                        "task_logs": "TaskLog.*",
                    }

                    for key, pattern in patterns.items():
                        matches = list(temp_path.glob(pattern))
                        if matches:
                            # For task logs, there might be multiple
                            if key == "task_logs":
                                output_files[key] = [str(m) for m in matches]
                            else:
                                output_files[key] = str(matches[0])

                # Store the archive location
                output_files["archive"] = str(archive_path)

        return output_files

    def _extract_pyats_results(self) -> Optional[Path]:
        """Extract PyATS results from zip archive to a permanent location"""
        # Look for our controlled archive name
        if not hasattr(self, "archive_name"):
            return None

        archive_path = self.output_dir / self.archive_name
        if not archive_path.exists():
            return None

        # Create extraction directory
        extract_dir = self.output_dir / "pyats_results"
        extract_dir.mkdir(exist_ok=True)

        # Clear previous results
        for item in extract_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        # Extract
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        return extract_dir

    def _print_summary(self) -> None:
        """Print execution summary matching Robot format"""
        wall_time = (datetime.now() - self.start_time).total_seconds()

        # Calculate total test time (sum of all individual test durations)
        total_test_time = sum(
            test.get("duration", 0)
            for test in self.test_status.values()
            if "duration" in test
        )

        # PyATS returns lowercase status values: 'passed', 'failed', 'skipped', 'errored'
        passed = sum(
            1 for t in self.test_status.values() if t.get("status") == "passed"
        )
        failed = sum(
            1 for t in self.test_status.values() if t.get("status") == "failed"
        )
        skipped = sum(
            1 for t in self.test_status.values() if t.get("status") == "skipped"
        )
        errored = sum(
            1 for t in self.test_status.values() if t.get("status") == "errored"
        )
        total = len(self.test_status)

        # Include errored tests in the failed count for the summary
        failed_total = failed + errored

        print("\n" + "=" * 80)
        print(
            f"{total} tests, {passed} passed, {failed_total} failed, {skipped} skipped."
        )
        print("=" * 80)

        # Extract and find PyATS output files
        extract_dir = self._extract_pyats_results()
        if extract_dir:
            results_json = extract_dir / "results.json"
            results_xml = extract_dir / "ResultsDetails.xml"
            summary_xml = extract_dir / "ResultsSummary.xml"
            report_files = list(extract_dir.glob("*.report"))

            print("PyATS Output Files:")
            print("=" * 80)

            if results_json.exists():
                print(f"Results JSON:    {results_json}")
            if results_xml.exists():
                print(f"Results XML:     {results_xml}")
            if summary_xml.exists():
                print(f"Summary XML:     {summary_xml}")
            if report_files:
                print(f"Report:          {report_files[0]}")

            # Also show the original archive location
            if hasattr(self, "archive_name"):
                archive_path = self.output_dir / self.archive_name
                if archive_path.exists():
                    print(f"Archive:         {archive_path}")

        print(f"\nTotal testing: {self._format_duration(total_test_time)}")
        print(f"Elapsed time:  {self._format_duration(wall_time)}")

    def _format_duration(self, seconds: float) -> str:
        """Format duration like Robot does"""
        if seconds < 60:
            return f"{seconds:.2f} seconds"
        else:
            minutes = int(seconds / 60)
            secs = seconds % 60
            return f"{minutes} minutes {secs:.2f} seconds"
