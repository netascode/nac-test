# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""HTML parsing utilities for E2E test assertions.

This module provides robust HTML content extraction and validation
for the generated test reports, replacing weak string-based assertions.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SummaryStats:
    """Test statistics extracted from an HTML summary page.

    Attributes:
        total: Total number of tests.
        passed: Number of passed tests.
        failed: Number of failed tests.
        skipped: Number of skipped tests.
        success_rate: Success rate percentage (0-100).
    """

    total: int
    passed: int
    failed: int
    skipped: int
    success_rate: float

    def __post_init__(self) -> None:
        """Validate statistics consistency."""
        computed_total = self.passed + self.failed + self.skipped
        if computed_total != self.total:
            raise ValueError(
                f"Stats inconsistency: passed({self.passed}) + failed({self.failed}) + "
                f"skipped({self.skipped}) = {computed_total}, but total = {self.total}"
            )


@dataclass(frozen=True)
class TestTypeStats:
    """Statistics for a specific test type (Robot, PyATS API, PyATS D2D).

    Attributes:
        test_type: The test type identifier (e.g., "Robot", "API", "D2D").
        title: Display title for this test type.
        total_tests: Total number of tests of this type.
        passed_tests: Number of passed tests.
        failed_tests: Number of failed tests.
        skipped_tests: Number of skipped tests.
        success_rate: Success rate percentage.
        report_path: Relative path to the detailed report.
    """

    test_type: str
    title: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    success_rate: float
    report_path: str


def extract_summary_stats_from_combined(html_content: str) -> SummaryStats:
    """Extract overall statistics from the combined summary HTML page.

    Parses the combined_summary.html page and extracts statistics from
    the "Overall Executive Summary" section, which has this structure:

        <div class="summary-item total">
            <p>Total Tests</p>
            <h3>{{ overall_stats.total }}</h3>
        </div>
        <div class="summary-item passed">
            <p>Passed</p>
            <h3>{{ overall_stats.passed }}</h3>
        </div>
        ...

    Args:
        html_content: The HTML content of combined_summary.html.

    Returns:
        SummaryStats with extracted values.

    Raises:
        ValueError: If required statistics cannot be found in the HTML.
    """

    def extract_count(css_class: str, label: str) -> int:
        """Extract a count from a summary-item div."""
        # Pattern matches the structure: <div class="summary-item {class}">...<h3>N</h3>
        # Using non-greedy match to get the first h3 within the div
        pattern = rf'class="summary-item\s+{css_class}"[^>]*>.*?<h3>(\d+)</h3>'
        match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
        if match:
            return int(match.group(1))
        raise ValueError(
            f"Could not find '{label}' count (class='summary-item {css_class}') in HTML"
        )

    def extract_rate() -> float:
        """Extract success rate percentage."""
        # Pattern: <h3>XX.X%</h3> within the rate summary-item
        pattern = r'class="summary-item\s+rate"[^>]*>.*?<h3>([\d.]+)%</h3>'
        match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
        if match:
            return float(match.group(1))
        raise ValueError("Could not find success rate in HTML")

    return SummaryStats(
        total=extract_count("total", "Total Tests"),
        passed=extract_count("passed", "Passed"),
        failed=extract_count("failed", "Failed"),
        skipped=extract_count("skipped", "Skipped"),
        success_rate=extract_rate(),
    )


def extract_summary_stats_from_report(html_content: str) -> SummaryStats:
    """Extract statistics from a summary report HTML page (Robot/PyATS).

    Parses the summary_report.html page (used by both Robot and PyATS),
    which has this structure in the Executive Summary section:

        <div class="summary-item total">
            <p>Total Tests</p>
            <h3>{{ stats.total }}</h3>
        </div>
        ...

    Args:
        html_content: The HTML content of summary_report.html.

    Returns:
        SummaryStats with extracted values.

    Raises:
        ValueError: If required statistics cannot be found in the HTML.
    """
    # Same structure as combined report
    return extract_summary_stats_from_combined(html_content)


def extract_test_type_sections(html_content: str) -> list[TestTypeStats]:
    """Extract per-test-type statistics from combined summary HTML.

    Parses the test-type-section elements from combined_summary.html:

        <div class="test-type-section">
            <span class="test-type-badge {{ test_type.lower() }}-badge">{{ test_type }}</span>
            <h2>{{ framework_data.title }} Test Results</h2>
            ...
            <div class="mini-stat-value total-value">{{ framework_data.stats.total }}</div>
            ...
        </div>

    Args:
        html_content: The HTML content of combined_summary.html.

    Returns:
        List of TestTypeStats, one per test type section found.

    Raises:
        ValueError: If sections cannot be parsed correctly.
    """
    results = []

    # Find all test-type-section divs
    section_pattern = r'<div class="test-type-section">(.*?)</div>\s*(?=<div class="test-type-section">|<footer>|$)'
    sections = re.findall(section_pattern, html_content, re.DOTALL)

    for section in sections:
        # Extract test type from badge
        type_match = re.search(r'class="test-type-badge[^"]*">([^<]+)</span>', section)
        test_type = type_match.group(1).strip() if type_match else "Unknown"

        # Extract title
        title_match = re.search(r"<h2>([^<]+)\s*Test Results</h2>", section)
        title = title_match.group(1).strip() if title_match else test_type

        # Extract mini-stat values
        def get_mini_stat(css_class: str, section: str = section) -> int:
            pattern = rf'class="mini-stat-value\s+{css_class}"[^>]*>(\d+)</div>'
            match = re.search(pattern, section)
            return int(match.group(1)) if match else 0

        def get_mini_stat_rate(section: str = section) -> float:
            # Rate doesn't have a specific class, it's the last mini-stat
            pattern = r'class="mini-stat-value"[^>]*>([\d.]+)%</div>'
            match = re.search(pattern, section)
            return float(match.group(1)) if match else 0.0

        # Extract report path
        path_match = re.search(r'href="([^"]+)"[^>]*class="view-report-btn"', section)
        if not path_match:
            path_match = re.search(
                r'class="view-report-btn"[^>]*href="([^"]+)"', section
            )
        report_path = path_match.group(1) if path_match else ""

        results.append(
            TestTypeStats(
                test_type=test_type,
                title=title,
                total_tests=get_mini_stat("total-value"),
                passed_tests=get_mini_stat("passed-value"),
                failed_tests=get_mini_stat("failed-value"),
                skipped_tests=get_mini_stat("skipped-value"),
                success_rate=get_mini_stat_rate(),
                report_path=report_path,
            )
        )

    return results


def verify_html_structure(html_content: str) -> None:
    """Verify basic HTML structure is valid, including UTF-8 charset declaration.

    Checks for required HTML elements and UTF-8 charset meta tag. Without an
    explicit charset meta tag, browsers (especially Safari) may default to a
    different encoding, causing UTF-8 characters (arrows, checkmarks, etc.)
    to display as garbled text.

    Args:
        html_content: The HTML content to verify.

    Raises:
        AssertionError: If HTML structure is invalid or charset is missing.
    """
    assert "<html" in html_content.lower(), "Missing <html> tag"
    assert "</html>" in html_content.lower(), "Missing </html> closing tag"
    assert "<head>" in html_content.lower(), "Missing <head> tag"
    assert "<body>" in html_content.lower(), "Missing <body> tag"

    # Check for <meta charset="UTF-8"> (case-insensitive)
    charset_pattern = r'<meta\s+charset\s*=\s*["\']?UTF-8["\']?\s*/?>'
    has_charset = re.search(charset_pattern, html_content, re.IGNORECASE)
    assert has_charset, (
        "Missing UTF-8 charset declaration. "
        'Add <meta charset="UTF-8"> to <head> to prevent garbled characters in Safari.'
    )


def verify_breadcrumb_link(html_content: str, expected_target: str) -> None:
    """Verify breadcrumb navigation link exists.

    Args:
        html_content: The HTML content to check.
        expected_target: Expected link target (e.g., "combined_summary.html").

    Raises:
        AssertionError: If breadcrumb link is missing.
    """
    assert expected_target in html_content, (
        f"Missing breadcrumb link to '{expected_target}'"
    )


def verify_table_structure(html_content: str) -> None:
    """Verify HTML contains a results table.

    Args:
        html_content: The HTML content to check.

    Raises:
        AssertionError: If table structure is missing.
    """
    assert "<table" in html_content.lower(), "Missing results table"
    assert "results-table" in html_content, "Missing results-table class"


def load_html_file(path: Path) -> str:
    """Load HTML content from a file.

    Args:
        path: Path to the HTML file.

    Returns:
        The HTML content as a string.

    Raises:
        FileNotFoundError: If file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"HTML file not found: {path}")
    return path.read_text()


# =============================================================================
# Convenience functions for common assertions
# =============================================================================


def assert_combined_stats(
    html_path: Path,
    expected_total: int,
    expected_passed: int,
    expected_failed: int,
    expected_skipped: int = 0,
) -> SummaryStats:
    """Assert combined summary statistics match expected values.

    Args:
        html_path: Path to combined_summary.html.
        expected_total: Expected total test count.
        expected_passed: Expected passed test count.
        expected_failed: Expected failed test count.
        expected_skipped: Expected skipped test count.

    Returns:
        The extracted SummaryStats for further assertions.

    Raises:
        AssertionError: If any statistic doesn't match.
        FileNotFoundError: If HTML file doesn't exist.
    """
    html_content = load_html_file(html_path)
    stats = extract_summary_stats_from_combined(html_content)

    assert stats.total == expected_total, (
        f"Total tests: expected {expected_total}, got {stats.total}"
    )
    assert stats.passed == expected_passed, (
        f"Passed tests: expected {expected_passed}, got {stats.passed}"
    )
    assert stats.failed == expected_failed, (
        f"Failed tests: expected {expected_failed}, got {stats.failed}"
    )
    assert stats.skipped == expected_skipped, (
        f"Skipped tests: expected {expected_skipped}, got {stats.skipped}"
    )

    return stats


def assert_report_stats(
    html_path: Path,
    expected_total: int,
    expected_passed: int,
    expected_failed: int,
    expected_skipped: int = 0,
) -> SummaryStats:
    """Assert summary report statistics match expected values.

    Args:
        html_path: Path to summary_report.html.
        expected_total: Expected total test count.
        expected_passed: Expected passed test count.
        expected_failed: Expected failed test count.
        expected_skipped: Expected skipped test count.

    Returns:
        The extracted SummaryStats for further assertions.

    Raises:
        AssertionError: If any statistic doesn't match.
        FileNotFoundError: If HTML file doesn't exist.
    """
    html_content = load_html_file(html_path)
    stats = extract_summary_stats_from_report(html_content)

    assert stats.total == expected_total, (
        f"Total tests: expected {expected_total}, got {stats.total}"
    )
    assert stats.passed == expected_passed, (
        f"Passed tests: expected {expected_passed}, got {stats.passed}"
    )
    assert stats.failed == expected_failed, (
        f"Failed tests: expected {expected_failed}, got {stats.failed}"
    )
    assert stats.skipped == expected_skipped, (
        f"Skipped tests: expected {expected_skipped}, got {stats.skipped}"
    )

    return stats


def extract_view_details_links(html_content: str) -> list[str]:
    """Extract all "View Details" link hrefs from HTML content.

    Finds all anchor tags with class="view-btn" that contain "View Details" text.
    The href may contain anchors (e.g., "log.html#s1-s2-t1") which are stripped
    to return just the file path.

    Args:
        html_content: The HTML content to parse.

    Returns:
        List of file paths (without anchors) from View Details links.
    """
    # Pattern to match: <a href="..." class="view-btn">...View Details...</a>
    # Also handles class before href: <a class="view-btn" href="...">
    pattern = r'<a\s+(?:[^>]*?\s+)?href="([^"]+)"[^>]*class="view-btn"[^>]*>|<a\s+(?:[^>]*?\s+)?class="view-btn"[^>]*href="([^"]+)"[^>]*>'
    matches = re.findall(pattern, html_content, re.IGNORECASE)

    links = []
    for match in matches:
        # match is a tuple of two groups; one will be empty
        href = match[0] or match[1]
        # Strip anchor if present (e.g., "log.html#s1-s2" -> "log.html")
        file_path = href.split("#")[0]
        if file_path:
            links.append(file_path)

    return links


def verify_view_details_links_resolve(html_path: Path) -> list[str]:
    """Verify all "View Details" links in a summary report point to existing files.

    Args:
        html_path: Path to the summary_report.html file.

    Returns:
        List of verified link paths (relative to the HTML file's directory).

    Raises:
        AssertionError: If any link target file does not exist.
        FileNotFoundError: If the HTML file doesn't exist.
    """
    html_content = load_html_file(html_path)
    links = extract_view_details_links(html_content)

    if not links:
        raise AssertionError(f"No 'View Details' links found in {html_path}")

    html_dir = html_path.parent
    missing_files = []
    verified_links = []

    for link in links:
        target_path = html_dir / link
        if not target_path.exists():
            missing_files.append(f"  - {link} (expected at: {target_path})")
        else:
            verified_links.append(link)

    if missing_files:
        raise AssertionError(
            f"View Details links point to missing files in {html_path}:\n"
            + "\n".join(missing_files)
        )

    return verified_links
