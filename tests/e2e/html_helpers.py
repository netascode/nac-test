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
    """Verify basic HTML structure is valid.

    Args:
        html_content: The HTML content to verify.

    Raises:
        AssertionError: If HTML structure is invalid.
    """
    assert "<html" in html_content.lower(), "Missing <html> tag"
    assert "</html>" in html_content.lower(), "Missing </html> closing tag"
    assert "<head>" in html_content.lower(), "Missing <head> tag"
    assert "<body>" in html_content.lower(), "Missing <body> tag"


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


# =============================================================================
# Hostname display validation helpers
# =============================================================================


@dataclass(frozen=True)
class HostnameDisplayInfo:
    """Information about hostname display in HTML reports.

    Attributes:
        test_name: The test name (without hostname).
        hostname: The hostname extracted from display.
        display_text: The full display text as it appears in HTML.
    """

    test_name: str
    hostname: str | None
    display_text: str


def extract_hostname_from_display_text(display_text: str) -> HostnameDisplayInfo:
    """Extract hostname from test display text.

    Parses display text in format "Test Name (hostname)" or just "Test Name".

    Args:
        display_text: The text as displayed in HTML (e.g., "Verify Config (EDGE01)").

    Returns:
        HostnameDisplayInfo with parsed components.
    """
    # Pattern to match "Test Name (hostname)" format
    pattern = r"^(.+?)\s*\(([^)]+)\)$"
    match = re.match(pattern, display_text.strip())

    if match:
        test_name = match.group(1).strip()
        hostname = match.group(2).strip()
        return HostnameDisplayInfo(
            test_name=test_name, hostname=hostname, display_text=display_text
        )
    else:
        # No hostname in parentheses
        return HostnameDisplayInfo(
            test_name=display_text.strip(), hostname=None, display_text=display_text
        )


def extract_hostnames_from_summary_table(
    html_content: str,
) -> list[HostnameDisplayInfo]:
    """Extract hostname display information from summary table.

    Parses the test name column in the summary table to extract hostnames.

    Args:
        html_content: The HTML content of a summary report.

    Returns:
        List of HostnameDisplayInfo for each test in the table.
    """
    results = []

    # Pattern to find test name cells in the table
    # Look for <td data-label="Test Name"> or similar
    pattern = r'<td[^>]*data-label="Test Name"[^>]*>([^<]+(?:<[^>]*>[^<]*</[^>]*>[^<]*)*)</td>'
    matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)

    for match in matches:
        # Clean up HTML tags and get plain text
        clean_text = re.sub(r"<[^>]*>", "", match).strip()
        if clean_text:
            results.append(extract_hostname_from_display_text(clean_text))

    return results


def extract_hostname_from_detail_page_header(
    html_content: str,
) -> HostnameDisplayInfo | None:
    """Extract hostname from detail page header.

    Parses the main <h1> tag in a test detail page to extract hostname.

    Args:
        html_content: The HTML content of a test detail page.

    Returns:
        HostnameDisplayInfo for the header, or None if no header found.
    """
    # Look for the main header - could be in various formats
    patterns = [
        r"<h1[^>]*>([^<]+(?:<[^>]*>[^<]*</[^>]*>[^<]*)*)</h1>",
        r"<h1>([^<]+(?:<[^>]*>[^<]*</[^>]*>[^<]*)*)</h1>",
    ]

    for pattern in patterns:
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            # Clean up HTML tags and get plain text
            clean_text = re.sub(r"<[^>]*>", "", match.group(1)).strip()
            if clean_text:
                return extract_hostname_from_display_text(clean_text)

    return None


def extract_hostnames_from_filenames(
    file_paths: list[Path],
) -> list[tuple[Path, str | None]]:
    """Extract hostnames from HTML report filenames.

    Parses filenames in format "classname_hostname_timestamp.html" to extract hostnames.
    Note: Hostnames are sanitized in filenames (special chars become underscores).

    Format: classname_hostname_YYYYMMDD_HHMMSS_mmm
    Example: verifytest_sd_dc_c8kv_01_20260218_155904_733.html

    Args:
        file_paths: List of HTML file paths to analyze.

    Returns:
        List of tuples (file_path, hostname) where hostname is None for API tests.
    """
    results = []

    for file_path in file_paths:
        filename = file_path.stem  # Remove .html extension
        parts = filename.split("_")

        if len(parts) >= 4:
            # Look for the date part (8 digits) which should be third from last
            # Format: classname_hostname_YYYYMMDD_HHMMSS_mmm
            date_index = -3  # Third from the end
            if (
                len(parts) >= 3
                and len(parts[date_index]) == 8
                and parts[date_index].isdigit()
            ):
                # Found date at expected position
                if len(parts) > 4:  # More than minimum parts means there's a hostname
                    hostname_parts = parts[
                        1:date_index
                    ]  # Everything between classname and date
                    hostname = "_".join(hostname_parts) if hostname_parts else None
                else:
                    # Format: classname_YYYYMMDD_HHMMSS_mmm (no hostname)
                    hostname = None
            else:
                # Try to find date anywhere in the later parts
                date_found = False
                for i in range(2, len(parts)):
                    if len(parts[i]) == 8 and parts[i].isdigit():
                        # Found a date part
                        if (
                            i > 1
                        ):  # There are parts before the date (excluding classname)
                            hostname_parts = parts[1:i]
                            hostname = (
                                "_".join(hostname_parts) if hostname_parts else None
                            )
                        else:
                            hostname = None
                        date_found = True
                        break

                if not date_found:
                    # No clear date pattern, assume no hostname
                    hostname = None
        else:
            hostname = None

        results.append((file_path, hostname))

    return results


def verify_hostname_in_console_output(
    console_output: str, expected_hostnames: list[str]
) -> list[str]:
    """Verify hostnames appear in console output with correct format.

    Uses simple string matching to find hostnames in console output.

    Args:
        console_output: The CLI stdout/stderr output.
        expected_hostnames: List of hostnames that should appear.

    Returns:
        List of hostnames found in the console output.

    Raises:
        AssertionError: If expected hostnames are missing from console output.
    """
    found_hostnames = []

    for hostname in expected_hostnames:
        # Look for hostname in parentheses format: (hostname)
        if f"({hostname})" in console_output:
            found_hostnames.append(hostname)

    # Verify all expected hostnames were found
    missing_hostnames = set(expected_hostnames) - set(found_hostnames)
    if missing_hostnames:
        raise AssertionError(
            f"Missing hostnames in console output: {sorted(missing_hostnames)}\n"
            f"Found hostnames: {sorted(set(found_hostnames))}\n"
            f"Console output:\n{console_output}"
        )

    return found_hostnames


def assert_hostname_display_in_summary(
    html_path: Path, expected_hostnames: list[str]
) -> list[str]:
    """Assert that hostnames are correctly displayed in summary table.

    Uses simple string matching to find hostnames in HTML content.

    Args:
        html_path: Path to the summary_report.html file.
        expected_hostnames: List of hostnames that should appear.

    Returns:
        List of hostnames found in the summary.

    Raises:
        AssertionError: If expected hostnames are missing.
    """
    html_content = load_html_file(html_path)
    found_hostnames = []

    for hostname in expected_hostnames:
        # Look for hostname in parentheses format in HTML content
        if f"({hostname})" in html_content:
            found_hostnames.append(hostname)

    # Verify all expected hostnames were found
    missing_hostnames = set(expected_hostnames) - set(found_hostnames)
    if missing_hostnames:
        raise AssertionError(
            f"Missing hostnames in summary table of {html_path}: {sorted(missing_hostnames)}\n"
            f"Found hostnames: {sorted(set(found_hostnames))}"
        )

    return found_hostnames


def assert_hostname_display_in_detail_pages(
    detail_file_paths: list[Path], expected_hostnames: list[str]
) -> list[str]:
    """Assert that hostnames are correctly displayed in detail page headers.

    Uses simple string matching to find hostnames in HTML content.

    Args:
        detail_file_paths: List of paths to test detail HTML files.
        expected_hostnames: List of hostnames that should appear.

    Returns:
        List of hostnames found in the detail pages.

    Raises:
        AssertionError: If expected hostnames are missing.
    """
    found_hostnames = []

    for hostname in expected_hostnames:
        # Look for hostname in parentheses format across all detail files
        for file_path in detail_file_paths:
            html_content = load_html_file(file_path)
            if f"({hostname})" in html_content:
                found_hostnames.append(hostname)
                break  # Found this hostname, move to next

    # Verify all expected hostnames were found
    missing_hostnames = set(expected_hostnames) - set(found_hostnames)
    if missing_hostnames:
        raise AssertionError(
            f"Missing hostnames in detail page headers: {sorted(missing_hostnames)}\n"
            f"Found hostnames: {sorted(set(found_hostnames))}\n"
            f"Checked files: {[str(p) for p in detail_file_paths]}"
        )

    return found_hostnames


def assert_hostname_in_filenames(
    html_files: list[Path], expected_hostnames: list[str]
) -> list[tuple[Path, str | None]]:
    """Assert that hostnames are correctly included in HTML filenames.

    Uses simple string matching to find sanitized hostnames in filenames.

    Args:
        html_files: List of HTML file paths to check.
        expected_hostnames: List of hostnames that should appear in filenames.
                          Note: These should be sanitized versions (dashes → underscores).

    Returns:
        List of tuples (file_path, hostname) found in filenames.

    Raises:
        AssertionError: If expected hostnames are missing from filenames.
    """
    found_hostnames = []

    for hostname in expected_hostnames:
        # Simply check if the sanitized hostname appears anywhere in any filename
        for file_path in html_files:
            if hostname in str(file_path):
                found_hostnames.append(hostname)
                break  # Found this hostname, move to next

    # Verify all expected hostnames were found
    missing_hostnames = set(expected_hostnames) - set(found_hostnames)
    if missing_hostnames:
        raise AssertionError(
            f"Missing hostnames in HTML filenames: {sorted(missing_hostnames)}\n"
            f"Found hostnames: {sorted(set(found_hostnames))}\n"
            f"Checked files: {[f.name for f in html_files]}"
        )

    # Return the original format for compatibility
    return [(f, None) for f in html_files]
