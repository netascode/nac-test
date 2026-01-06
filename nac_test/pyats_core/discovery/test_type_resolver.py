"""Test type resolver for NAC-Test framework.

This module provides automated test type detection for PyATS test files, determining
whether tests should be classified as API (controller/REST) or D2D (Direct-to-Device/SSH)
tests. The resolver uses a three-tier detection strategy to accurately classify tests
without executing any code.

Detection Strategy (Priority Order):
    1. **AST Analysis** (Highest Priority):
       - Statically analyzes Python AST to detect base class inheritance
       - Maps known base classes to test types via BASE_CLASS_MAPPING
       - Handles both direct (Name) and qualified (Attribute) class references
       - Most reliable method with <5ms performance per file

    2. **Directory Structure** (Fallback):
       - Checks if test file is under a `/d2d/` directory path
       - Simple path-based heuristic for organized codebases
       - Instant detection with minimal overhead

    3. **Default Classification** (Last Resort):
       - Falls back to 'api' type when no other indicators found
       - Ensures all tests have a valid classification

Performance Characteristics:
    - AST parsing: <5ms per file (typical)
    - Directory check: <0.1ms per file
    - Caching layer reduces repeated detections to <0.01ms
    - Memory overhead: ~100 bytes per cached file

Extending for New Architectures:
    To add support for new network architectures or test bases:

    1. Add the base class mapping to BASE_CLASS_MAPPING:
       ```python
       BASE_CLASS_MAPPING["MyNewTestBase"] = "api"  # or "d2d"
       ```

    2. If creating a new test type beyond api/d2d:
       - Add to VALID_TEST_TYPES set
       - Update discovery logic in test_discovery.py
       - Ensure archive separation logic handles new type

Example Usage:
    ```python
    from nac_test.pyats_core.discovery.test_type_resolver import TestTypeResolver
    from pathlib import Path

    # Initialize resolver (typically done once)
    resolver = TestTypeResolver(Path("/path/to/tests"))

    # Detect test type for a file
    test_type = resolver.resolve(Path("/path/to/verify_bgp.py"))
    # Returns: "api" or "d2d"

    # Bulk detection with caching benefits
    for test_file in test_files:
        test_type = resolver.resolve(test_file)
        if test_type == "d2d":
            # Handle D2D test (SSH-based)
            pass
        else:
            # Handle API test (REST-based)
            pass
    ```

Module Constants:
    BASE_CLASS_MAPPING: Maps base class names to test types
    VALID_TEST_TYPES: Set of valid test type values
    DEFAULT_TEST_TYPE: Fallback test type when detection fails

Exceptions:
    NoRecognizedBaseError: Raised when AST analysis finds no recognized base class
"""

import ast
import logging
from pathlib import Path
from typing import Final

# Module-level constants
VALID_TEST_TYPES: Final[set[str]] = {"api", "d2d"}
DEFAULT_TEST_TYPE: Final[str] = "api"

# Base class to test type mapping
# This dictionary maps known PyATS test base class names to their test types
BASE_CLASS_MAPPING: Final[dict[str, str]] = {
    # API test bases (controller/REST tests)
    "NACTestBase": "api",  # Generic base, defaults to API
    "APICTestBase": "api",  # ACI/APIC controller tests
    "SDWANManagerTestBase": "api",  # SD-WAN vManage/Manager controller tests
    "CatalystCenterTestBase": "api",  # Catalyst Center (formerly DNAC) tests
    "MerakiTestBase": "api",  # Meraki Dashboard API tests
    "FMCTestBase": "api",  # Firepower Management Center tests
    "ISETestBase": "api",  # Identity Services Engine tests
    # D2D test bases (SSH/device tests)
    "SSHTestBase": "d2d",  # Generic SSH-based device tests
    "SDWANTestBase": "d2d",  # SD-WAN edge device tests (cEdge/vEdge)
    "IOSXETestBase": "d2d",  # IOS-XE device tests
    "NXOSTestBase": "d2d",  # NX-OS device tests
    "IOSTestBase": "d2d",  # Classic IOS device tests
}


class NoRecognizedBaseError(Exception):
    """Exception raised when no recognized base class is found during AST analysis.

    This exception is raised when the AST parser successfully analyzes a test file
    but cannot find any base classes that match the known mappings in BASE_CLASS_MAPPING.
    This is a normal condition that triggers fallback to directory-based detection.

    Attributes:
        filename: Path to the test file that was analyzed
        found_bases: List of base class names that were found but not recognized

    Example:
        ```python
        try:
            test_type = resolver._detect_via_ast(test_file)
        except NoRecognizedBaseError as e:
            # Fallback to directory-based detection
            logger.debug(f"No recognized base in {e.filename}, trying directory detection")
            test_type = resolver._detect_via_directory(test_file)
        ```
    """

    def __init__(self, filename: str, found_bases: list[str] | None = None) -> None:
        """Initialize the exception with file context.

        Args:
            filename: Path to the test file that was analyzed
            found_bases: Optional list of base class names that were found but not recognized
        """
        self.filename = filename
        self.found_bases = found_bases or []

        if found_bases:
            message = (
                f"No recognized base class found in {filename}. "
                f"Found bases: {', '.join(found_bases)}, "
                f"but none match known mappings."
            )
        else:
            message = f"No base classes found in {filename}"

        super().__init__(message)


class TestTypeResolver:
    """Resolves test execution type using static analysis.

    This class provides intelligent test type detection for PyATS test files,
    using a multi-tier strategy to classify tests as either API (controller/REST)
    or D2D (Direct-to-Device/SSH) tests.

    The resolver maintains a cache to optimize repeated detections and uses
    static AST analysis to avoid importing or executing test code.

    Attributes:
        test_root: Root directory containing test files
        _cache: Internal cache mapping file paths to detected test types
        logger: Logger instance for debugging and diagnostics

    Example:
        ```python
        resolver = TestTypeResolver(Path("/path/to/tests"))

        # Detect single file
        test_type = resolver.resolve(Path("verify_bgp.py"))

        # Clear cache if files have changed
        resolver.clear_cache()
        ```
    """

    def __init__(self, test_root: Path) -> None:
        """Initialize the test type resolver.

        Args:
            test_root: Root directory containing test files. Will be resolved
                      to an absolute path for consistent cache keys.
        """
        self.test_root = test_root.resolve()
        self._cache: dict[Path, str] = {}
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized TestTypeResolver with root: {self.test_root}")

    def clear_cache(self) -> None:
        """Clear the internal cache of detected test types.

        Call this method if test files have been modified or moved and you need
        to re-detect their types. This is typically only needed during development
        or when test files are dynamically generated.

        Example:
            ```python
            resolver = TestTypeResolver(Path("/tests"))

            # Initial detection
            test_type = resolver.resolve(Path("test_bgp.py"))

            # After modifying the test file's base class
            resolver.clear_cache()
            test_type = resolver.resolve(Path("test_bgp.py"))  # Re-detects
            ```
        """
        cache_size = len(self._cache)
        self._cache.clear()
        self.logger.debug(f"Cleared cache ({cache_size} entries)")

    def _detect_from_base_class(self, file_path: Path) -> str:
        """Detect test type by analyzing base class inheritance using AST.

        This method parses the Python file into an Abstract Syntax Tree (AST)
        and examines the base classes of all top-level class definitions.
        It maps recognized base class names to their corresponding test types.

        The method handles both direct inheritance (ast.Name nodes) and
        qualified inheritance (ast.Attribute nodes for module.ClassName).

        Args:
            file_path: Path to the Python test file to analyze

        Returns:
            Test type string ("api" or "d2d") based on detected base class

        Raises:
            NoRecognizedBaseError: When no recognized base class is found
            OSError: When the file cannot be read (propagated)
            SyntaxError: When the Python file has syntax errors (propagated)

        Example:
            Given a test file with:
            ```python
            class TestBGP(SSHTestBase):
                pass
            ```

            This method will:
            1. Parse the file into an AST
            2. Find the TestBGP class definition
            3. Identify SSHTestBase as the base class
            4. Look up SSHTestBase in BASE_CLASS_MAPPING
            5. Return "d2d" (the mapped test type)
        """
        self.logger.debug(f"Analyzing AST for file: {file_path}")

        # Read the file content - let OSError propagate
        content = file_path.read_text(encoding="utf-8")

        # Parse into AST - let SyntaxError propagate
        tree = ast.parse(content, filename=str(file_path))

        # Track all found base classes for error reporting
        found_bases: list[str] = []

        # Only examine top-level classes (tree.body)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            self.logger.debug(f"Found class: {node.name}")

            # Check each base class of this class
            for base in node.bases:
                base_name: str | None = None

                if isinstance(base, ast.Name):
                    # Direct inheritance: class MyTest(SSHTestBase)
                    base_name = base.id
                    self.logger.debug(f"  Direct base: {base_name}")
                elif isinstance(base, ast.Attribute):
                    # Qualified inheritance: class MyTest(module.SSHTestBase)
                    # We only care about the class name, not the module
                    base_name = base.attr
                    self.logger.debug(f"  Qualified base: {base_name}")

                if base_name:
                    found_bases.append(base_name)

                    # Check if this base class is in our mapping
                    if base_name in BASE_CLASS_MAPPING:
                        test_type = BASE_CLASS_MAPPING[base_name]
                        self.logger.info(
                            f"Detected test type '{test_type}' from base class "
                            f"'{base_name}' in {file_path}"
                        )
                        return test_type

        # No recognized base class found
        self.logger.debug(
            f"No recognized base class in {file_path}. "
            f"Found bases: {found_bases if found_bases else 'none'}"
        )
        raise NoRecognizedBaseError(str(file_path), found_bases)

    def resolve(self, test_file: Path) -> str:
        """Resolve test type for a test file.

        This is the main API entry point for test type detection. It implements
        caching for performance and delegates to _resolve_uncached for the actual
        detection logic.

        Detection Priority:
            1. Static analysis of base class inheritance (most reliable)
            2. Directory structure (/api/ or /d2d/ in path)
            3. Default to 'api' with warning

        Args:
            test_file: Path to the test file to classify

        Returns:
            Test type string: either "api" or "d2d"

        Example:
            ```python
            resolver = TestTypeResolver(Path("/tests"))

            # First call performs detection
            test_type = resolver.resolve(Path("verify_bgp.py"))  # Takes ~5ms

            # Subsequent calls use cache
            test_type = resolver.resolve(Path("verify_bgp.py"))  # Takes <0.01ms
            ```
        """
        test_file = test_file.resolve()

        # Check cache first
        if test_file in self._cache:
            self.logger.debug(f"Cache hit for {test_file}")
            return self._cache[test_file]

        # Cache miss - perform detection and cache result
        self.logger.debug(f"Cache miss for {test_file}")
        test_type = self._resolve_uncached(test_file)
        self._cache[test_file] = test_type
        return test_type

    def _resolve_uncached(self, test_file: Path) -> str:
        """Resolve test type using three-tier detection strategy.

        This method implements the core detection logic without caching.
        It tries detection methods in priority order, falling back to the
        next method if the current one fails.

        Detection Flow:
            1. Try AST-based detection (examines base classes)
            2. If AST fails, try directory-based detection
            3. If both fail, default to 'api' with warning

        Args:
            test_file: Absolute path to the test file

        Returns:
            Test type string: either "api" or "d2d"

        Note:
            This method logs extensively for debugging. Use appropriate
            log levels to control verbosity in production.
        """
        # Priority 1: Try static analysis of base classes
        try:
            test_type = self._detect_from_base_class(test_file)
            self.logger.debug(
                f"{test_file.name}: Detected '{test_type}' from base class"
            )
            return test_type
        except NoRecognizedBaseError:
            # This is expected for tests without recognized bases
            self.logger.debug(
                f"{test_file.name}: No recognized base class, trying directory detection"
            )
        except (OSError, SyntaxError) as e:
            # File read or parse errors - try fallback methods
            self.logger.warning(
                f"Failed to parse {test_file}: {e}, trying directory detection"
            )

        # Priority 2: Fall back to directory structure detection
        path_str = test_file.as_posix()

        # Check for /d2d/ in path (Direct-to-Device tests)
        if "/d2d/" in path_str:
            self.logger.debug(
                f"{test_file.name}: Using directory-based detection (d2d)"
            )
            return "d2d"

        # Check for /api/ in path (API/Controller tests)
        if "/api/" in path_str:
            self.logger.debug(
                f"{test_file.name}: Using directory-based detection (api)"
            )
            return "api"

        # Priority 3: Default to 'api' with warning
        self.logger.warning(
            f"{test_file}: Could not detect test type from base class or directory. "
            f"Assuming 'api'. To fix: inherit from a known base class or place in /d2d/ directory."
        )
        return "api"
