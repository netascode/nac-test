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
