# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import json
import logging
from pathlib import Path

import yaml  # type: ignore

logger = logging.getLogger(__name__)


def _validate_pyats_results(output_dir: str | Path, passed: int, failed: int) -> None:
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
            logger.debug("Test ERRORED, searching for error details")
            # Look for TaskLog.* files which contain test execution details
            log_dir = results_file.parent
            for log_file in log_dir.glob("*TaskLog*"):
                logger.debug("Contents of %s", log_file.name)
                with open(log_file) as f:
                    logger.debug(f.read()[-5000:])  # Log last 5000 chars
            logger.debug("END ERROR DEBUG")

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

        # Log full summary for CI debugging
        logger.debug(
            "Full results from %s: %s",
            results_file.parent.name,
            json.dumps(summary, indent=2),
        )

        # Verify tests were run
        assert summary["total"] > 0, (
            f"No tests were run in {results_file.parent.name}: total={summary['total']}"
        )
        total_passed += summary["passed"]
        total_failed += summary["failed"]

    # Verify passed and failed counts
    assert total_passed == passed, f"passed: expected={passed}, actual={total_passed}"
    assert total_failed == failed, f"failed: expected={failed}, actual={total_failed}"
