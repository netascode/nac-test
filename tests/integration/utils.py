# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import json
from pathlib import Path

import yaml  # type: ignore
from robot.api import ExecutionResult


def validate_pyats_results(output_dir: str | Path, passed: int, failed: int) -> None:
    """Validate PyATS test results from results.json files.

    Args:
        output_dir: Base output directory containing pyats_results/

    Raises:
        AssertionError: If validation fails (no tests run, tests failed, etc.)
    """
    output_path = Path(output_dir)
    pyats_results_dir = output_path / "pyats_results"
    assert pyats_results_dir.exists(), (
        f"PyATS results directory not found: {pyats_results_dir}"
    )

    # Find all results.json files (can be in api/ or d2d/ subdirs)
    results_files = list(pyats_results_dir.glob("**/results.json"))

    # DEBUG: If test errored, try to find and print the error log
    for results_file in results_files:
        with open(results_file) as f:
            results_data = yaml.safe_load(f)

        if results_data.get("report", {}).get("summary", {}).get("errored", 0) > 0:
            print("DEBUG: Test ERRORED, searching for error details")
            # Look for TaskLog.* files which contain test execution details
            log_dir = results_file.parent
            for log_file in log_dir.glob("*TaskLog*"):
                print(f"DEBUG: Contents of {log_file.name}")
                with open(log_file) as f:
                    print(f.read()[-5000:])  # Print last 5000 chars
            print("DEBUG: END ERROR DEBUG")

    assert len(results_files) > 0, f"No results.json files found in {pyats_results_dir}"

    total_passed = total_failed = 0

    # Validate each results.json file
    for results_file in results_files:
        with open(results_file) as f:
            results_data = yaml.safe_load(f)

        # Check that results were generated
        assert "report" in results_data, f"No 'report' key in {results_file}"
        assert "summary" in results_data["report"], (
            f"No 'summary' in report for {results_file}"
        )

        summary = results_data["report"]["summary"]

        # Print full summary for CI debugging
        print(
            f"DEBUG: Full results from {results_file.parent.name}: "
            f"{json.dumps(summary, indent=2)}"
        )

        # Verify tests were run
        assert summary["total"] > 0, (
            f"No tests were run in {results_file.parent.name}: total={summary['total']}"
        )
        total_passed += summary["passed"]
        total_failed += summary["failed"]

    # Verify passed and failed counts
    assert (total_passed, total_failed) == (passed, failed), (
        f"Test results do not match expected values: "
        f"expected passed={passed}, failed={failed}; "
        f"actual passed={total_passed}, failed={total_failed}"
    )


def validate_robot_results(output_dir: str | Path, passed: int, failed: int) -> None:
    """Validate Robot Framework test results from output.xml.

    Args:
        output_dir: Base output directory containing output.xml
        passed: Expected number of passed tests
        failed: Expected number of failed tests

    Raises:
        AssertionError: If validation fails (no tests run, tests failed, etc.)
    """
    output_path = Path(output_dir)
    output_xml = output_path / "output.xml"

    assert output_xml.exists(), f"Robot Framework output.xml not found: {output_xml}"

    # Parse the execution result
    result = ExecutionResult(str(output_xml))

    # Get statistics from the suite
    stats = result.suite.statistics
    total = stats.total
    actual_passed = stats.passed
    actual_failed = stats.failed

    # Verify tests were run
    assert total > 0, f"No tests were run in Robot Framework: total={total}"

    # Verify passed and failed counts
    assert (actual_passed, actual_failed) == (passed, failed), (
        f"Robot Framework results do not match expected values: "
        f"expected passed={passed}, failed={failed}; "
        f"actual passed={actual_passed}, failed={actual_failed}"
    )


def validate_reporting_artifacts_pyats_html(
    output_dir: str | Path, test_types: list[str]
) -> None:
    """Validate that PyATS HTML reporting artifacts were generated correctly.

    Checks for:
    - HTML reports directory structure
    - Individual test HTML reports
    - Summary HTML report
    - Combined summary (if multiple test types)

    Args:
        output_dir: Base output directory containing pyats_results/
        test_types: List of test types to check (e.g., ["api", "d2d"])

    Raises:
        AssertionError: If expected artifacts are missing
    """
    output_path = Path(output_dir)
    pyats_results_dir = output_path / "pyats_results"

    assert pyats_results_dir.exists(), (
        f"PyATS results directory not found: {pyats_results_dir}"
    )

    for test_type in test_types:
        html_dir = pyats_results_dir / test_type / "html_reports"

        assert html_dir.exists(), f"HTML reports directory not found: {html_dir}"

        print(f"Validating HTML reports in {test_type}/")

        # Check for summary report
        summary_report = html_dir / "summary_report.html"
        assert summary_report.exists(), f"Summary report not found: {summary_report}"

        # Check for individual test reports (should have at least one)
        test_reports = list(html_dir.glob("*.html"))
        test_reports = [r for r in test_reports if r.name != "summary_report.html"]
        assert len(test_reports) > 0, f"No individual test reports found in {html_dir}"

        print(f"  ✓ Found {len(test_reports)} test report(s) and summary")

    # Check for combined summary if multiple test types
    if len(test_types) > 1:
        combined_summary = pyats_results_dir / "combined_summary.html"
        assert combined_summary.exists(), (
            f"Combined summary not found: {combined_summary}"
        )
        print(f"  ✓ Found combined summary for {len(test_types)} test types")


def validate_reporting_artifacts_pyats_robot(
    output_dir: str | Path,
    test_types: list[str],
    expected_passed: int,
    expected_failed: int,
) -> None:
    """Validate that Robot Framework reporting artifacts were generated correctly.

    Checks for:
    - Individual output.xml files per test type (api, d2d, etc.)
    - Combined output.xml at pyats_results level
    - log.html (Robot Framework interactive log)
    - report.html (Robot Framework summary report)
    - Validates test counts match expected values

    Args:
        output_dir: Base output directory containing pyats_results/
        test_types: List of test types to check (e.g., ["api", "d2d"])
        expected_passed: Expected number of passed tests in combined results
        expected_failed: Expected number of failed tests in combined results

    Raises:
        AssertionError: If expected artifacts are missing or test counts don't match
    """
    output_path = Path(output_dir)
    pyats_results_dir = output_path / "pyats_results"

    assert pyats_results_dir.exists(), (
        f"PyATS results directory not found: {pyats_results_dir}"
    )

    # Check individual output.xml files per test type
    individual_test_counts = {"passed": 0, "failed": 0, "total": 0}

    for test_type in test_types:
        xml_file = pyats_results_dir / test_type / "output.xml"

        assert xml_file.exists(), (
            f"Robot output.xml not found for {test_type}: {xml_file}"
        )

        print(f"Validating Robot XML for {test_type}/")

        # Verify XML is valid by parsing it
        try:
            result = ExecutionResult(str(xml_file))
            stats = result.suite.statistics
            print(
                f"  ✓ output.xml: {stats.total} tests ({stats.passed} passed, {stats.failed} failed)"
            )

            # Track individual counts for debugging
            individual_test_counts["total"] += stats.total
            individual_test_counts["passed"] += stats.passed
            individual_test_counts["failed"] += stats.failed
        except Exception as e:
            raise AssertionError(f"Invalid Robot XML {xml_file}: {e}") from e

    print(f"DEBUG: Individual XML totals: {individual_test_counts}")

    # Check for combined Robot Framework reports at top level
    combined_output = pyats_results_dir / "output.xml"
    assert combined_output.exists(), f"Combined output.xml not found: {combined_output}"

    log_html = pyats_results_dir / "log.html"
    assert log_html.exists(), f"Robot Framework log.html not found: {log_html}"

    report_html = pyats_results_dir / "report.html"
    assert report_html.exists(), f"Robot Framework report.html not found: {report_html}"

    # Verify combined output.xml is valid and has expected test counts
    try:
        print(f"DEBUG: Parsing combined output.xml: {combined_output}")
        print(
            f"DEBUG: File exists: {combined_output.exists()}, size: {combined_output.stat().st_size if combined_output.exists() else 0}"
        )

        result = ExecutionResult(str(combined_output))
        stats = result.suite.statistics

        actual_passed = stats.passed
        actual_failed = stats.failed

        print(
            f"  ✓ Combined output.xml: {stats.total} tests ({actual_passed} passed, {actual_failed} failed)"
        )
        print(f"DEBUG: Expected: passed={expected_passed}, failed={expected_failed}")
        print(f"DEBUG: Actual:   passed={actual_passed}, failed={actual_failed}")

        # Verify counts match expectations
        assert (actual_passed, actual_failed) == (expected_passed, expected_failed), (
            f"Combined Robot results do not match expected values: "
            f"expected passed={expected_passed}, failed={expected_failed}; "
            f"actual passed={actual_passed}, failed={actual_failed}"
        )

    except Exception as e:
        print(f"DEBUG: Exception during combined XML validation: {e}")
        raise AssertionError(f"Invalid combined output.xml: {e}") from e

    # Verify HTML files are not empty
    assert log_html.stat().st_size > 0, "log.html is empty"
    assert report_html.stat().st_size > 0, "report.html is empty"

    print(f"  ✓ Found log.html ({log_html.stat().st_size:,} bytes)")
    print(f"  ✓ Found report.html ({report_html.stat().st_size:,} bytes)")
