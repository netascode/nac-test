# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Generic connection pooling for HTTP connections.

Note on Fork Safety:
    PyATS uses fork() to create task subprocesses. After fork(), the child
    process inherits class variables from the parent, but threading.Lock
    and other threading primitives are NOT fork-safe on macOS.

    This module detects fork by tracking the PID at instance creation time.
    If the current PID differs from the creation PID, we're in a forked
    child process and must reset the singleton to avoid corrupted state.

    Additionally, on macOS after fork(), creating httpx.AsyncClient crashes
    silently due to OpenSSL threading primitives that are not fork-safe.
    To handle this, we provide SubprocessHttpClient which makes HTTP requests
    via subprocess using urllib (which is fork-safe).
"""

import base64
import json
import logging
import os
import platform
import stat
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx

# Named constants for subprocess HTTP operations
SUBPROCESS_HTTP_TIMEOUT_SECONDS: float = 30.0
SUBPROCESS_BUFFER_TIMEOUT_SECONDS: float = 10.0

logger = logging.getLogger(__name__)


# HTTP status code range boundaries
HTTP_STATUS_SUCCESS_MIN: int = 200
HTTP_STATUS_SUCCESS_MAX: int = 299
HTTP_STATUS_REDIRECT_MIN: int = 300
HTTP_STATUS_REDIRECT_MAX: int = 399
HTTP_STATUS_CLIENT_ERROR_MIN: int = 400
HTTP_STATUS_CLIENT_ERROR_MAX: int = 499
HTTP_STATUS_SERVER_ERROR_MIN: int = 500
HTTP_STATUS_SERVER_ERROR_MAX: int = 599


@dataclass
class SubprocessResponse:
    """Response object compatible with httpx.Response interface.

    This dataclass wraps subprocess HTTP response data in a format that is
    compatible with httpx.Response, allowing the SubprocessHttpClient to be
    used as a drop-in replacement for httpx.AsyncClient.

    Attributes:
        status_code: HTTP status code from the response.
        _content: Raw response body as bytes (internal storage).
        _headers_dict: Response headers as a dictionary (internal storage).
        url: The URL that was requested (for error messages).
    """

    status_code: int
    _content: bytes
    _headers_dict: dict[str, str]
    url: str

    @property
    def text(self) -> str:
        """Decode response content as UTF-8 text.

        Returns:
            The response body decoded as a UTF-8 string.
        """
        return self._content.decode("utf-8")

    @property
    def content(self) -> bytes:
        """Get raw response content as bytes.

        Returns:
            The raw response body as bytes.
        """
        return self._content

    def json(self) -> Any:
        """Parse response content as JSON.

        Returns:
            The parsed JSON data.

        Raises:
            json.JSONDecodeError: If the response body is not valid JSON.
        """
        return json.loads(self._content)

    @property
    def headers(self) -> httpx.Headers:
        """Get response headers as httpx.Headers for compatibility.

        Returns:
            An httpx.Headers object containing the response headers.
        """
        return httpx.Headers(self._headers_dict)

    @property
    def is_success(self) -> bool:
        """Check if the response indicates success (2xx status code).

        Returns:
            True if status code is between 200-299, False otherwise.
        """
        return HTTP_STATUS_SUCCESS_MIN <= self.status_code <= HTTP_STATUS_SUCCESS_MAX

    @property
    def is_redirect(self) -> bool:
        """Check if the response indicates a redirect (3xx status code).

        Returns:
            True if status code is between 300-399, False otherwise.
        """
        return HTTP_STATUS_REDIRECT_MIN <= self.status_code <= HTTP_STATUS_REDIRECT_MAX

    @property
    def is_client_error(self) -> bool:
        """Check if the response indicates a client error (4xx status code).

        Returns:
            True if status code is between 400-499, False otherwise.
        """
        return (
            HTTP_STATUS_CLIENT_ERROR_MIN
            <= self.status_code
            <= HTTP_STATUS_CLIENT_ERROR_MAX
        )

    @property
    def is_server_error(self) -> bool:
        """Check if the response indicates a server error (5xx status code).

        Returns:
            True if status code is between 500-599, False otherwise.
        """
        return (
            HTTP_STATUS_SERVER_ERROR_MIN
            <= self.status_code
            <= HTTP_STATUS_SERVER_ERROR_MAX
        )

    @property
    def is_error(self) -> bool:
        """Check if the response indicates an error (4xx or 5xx status code).

        Returns:
            True if status code is between 400-599, False otherwise.
        """
        return self.is_client_error or self.is_server_error

    def raise_for_status(self) -> None:
        """Raise httpx.HTTPStatusError if the response indicates an error.

        Raises:
            httpx.HTTPStatusError: If the status code indicates an error (4xx or 5xx).
        """
        if self.is_error:
            # Create a minimal httpx.Request for the error
            request = httpx.Request("GET", self.url)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code} error for URL: {self.url}",
                request=request,
                response=self,  # type: ignore[arg-type]
            )


class SubprocessHttpClient:
    """Fork-safe HTTP client that executes requests via subprocess.

    This client is designed for macOS environments where httpx.AsyncClient
    cannot be safely created after fork() due to OpenSSL threading issues.
    Instead of using httpx directly, this client spawns a subprocess for
    each HTTP request, using urllib which is fork-safe.

    The client implements the same async interface as httpx.AsyncClient,
    allowing it to be used as a drop-in replacement in code that expects
    an async HTTP client.

    Performance Note:
        This client is slower than httpx.AsyncClient due to subprocess
        overhead. It should only be used when fork-safety is required
        (i.e., on macOS after fork()). On Linux and other platforms,
        httpx.AsyncClient should be used for better performance.

    Example:
        async with SubprocessHttpClient(
            base_url="https://api.example.com",
            headers={"Authorization": "Bearer token"},
            timeout=httpx.Timeout(30.0),
            verify=False
        ) as client:
            response = await client.get("/endpoint")
            data = response.json()
    """

    def __init__(
        self,
        base_url: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        verify: bool = True,
    ) -> None:
        """Initialize the subprocess HTTP client.

        Args:
            base_url: Optional base URL for resolving relative URLs.
            headers: Optional default headers to include in all requests.
            timeout: Optional timeout settings (httpx.Timeout object).
            verify: SSL verification flag. Set to False to skip verification.
        """
        self._base_url = base_url.rstrip("/") if base_url else None
        self._headers = headers or {}
        self._verify = verify

        # Extract timeout value from httpx.Timeout object
        if timeout is not None:
            # Use the connect timeout or default
            if timeout.connect is not None:
                self._timeout = float(timeout.connect)
            elif timeout.read is not None:
                self._timeout = float(timeout.read)
            else:
                self._timeout = SUBPROCESS_HTTP_TIMEOUT_SECONDS
        else:
            self._timeout = SUBPROCESS_HTTP_TIMEOUT_SECONDS

        logger.debug(
            f"[SubprocessHttpClient] Initialized with base_url={self._base_url}, "
            f"verify={self._verify}, timeout={self._timeout}"
        )

    async def __aenter__(self) -> "SubprocessHttpClient":
        """Enter async context manager.

        Returns:
            Self for use in async with statements.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager.

        No cleanup is needed since each request spawns its own subprocess.
        """
        pass

    def _resolve_url(self, url: str) -> str:
        """Resolve a potentially relative URL against the base URL.

        Args:
            url: The URL to resolve (may be relative or absolute).

        Returns:
            The fully resolved absolute URL.
        """
        if url.startswith(("http://", "https://")):
            return url
        if self._base_url:
            return f"{self._base_url}{url}"
        return url

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | None = None,
    ) -> SubprocessResponse:
        """Execute an HTTP request via subprocess.

        This method spawns a subprocess that uses urllib to make the actual
        HTTP request. This approach avoids OpenSSL fork-safety issues on macOS.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH).
            url: The URL to request (may be relative).
            headers: Optional request-specific headers to merge with defaults.
            json_data: Optional JSON-serializable data for request body.
            data: Optional raw bytes for request body.

        Returns:
            SubprocessResponse containing the response data.

        Raises:
            RuntimeError: If the subprocess fails or returns invalid data.
            json.JSONDecodeError: If JSON serialization fails.
        """
        resolved_url = self._resolve_url(url)

        # Merge headers
        merged_headers = dict(self._headers)
        if headers:
            merged_headers.update(headers)

        # Prepare request body
        body_b64: str | None = None
        if json_data is not None:
            try:
                body_bytes = json.dumps(json_data).encode("utf-8")
                body_b64 = base64.b64encode(body_bytes).decode("ascii")
                if "Content-Type" not in merged_headers:
                    merged_headers["Content-Type"] = "application/json"
            except (TypeError, ValueError) as e:
                raise RuntimeError(f"Failed to serialize JSON data: {e}") from e
        elif data is not None:
            body_b64 = base64.b64encode(data).decode("ascii")

        # Prepare subprocess input
        request_data = {
            "method": method,
            "url": resolved_url,
            "headers": merged_headers,
            "body_b64": body_b64,
            "timeout": self._timeout,
            "verify": self._verify,
        }

        start_time = time.time()
        logger.debug(
            f"[SubprocessHttpClient] {method} {resolved_url} - spawning subprocess"
        )

        # =============================================================================
        # macOS Fork Safety: Use os.system() + temp files - NOT subprocess.run()
        # =============================================================================
        # CRITICAL: On macOS, after PyATS forks child processes:
        #   - subprocess.run() crashes due to pipe creation issues after fork
        #   - asyncio.to_thread() uses ThreadPoolExecutor which breaks after fork
        #   - asyncio.create_subprocess_exec() child watcher breaks after fork
        #   - os.popen() also crashes (uses pipes internally)
        #
        # The ONLY reliable approach is os.system() which uses the system() syscall
        # that doesn't create pipes. To exchange data, we use temp files:
        #   1. Write request data to input temp file
        #   2. Script reads from input file, makes request, writes to output file
        #   3. We read result from output temp file
        #
        # This is slower but 100% fork-safe on macOS.
        # =============================================================================
        import tempfile

        # Create temp files for input/output (avoid pipes)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_req.json", delete=False
        ) as f_in:
            json.dump(request_data, f_in)
            input_path = f_in.name
        # Restrict permissions since file may contain auth headers
        os.chmod(input_path, stat.S_IRUSR | stat.S_IWUSR)

        # Use NamedTemporaryFile instead of deprecated mktemp() to avoid race conditions
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_resp.json", delete=False
        ) as f_out:
            output_path = f_out.name
        # Restrict permissions for output file
        os.chmod(output_path, stat.S_IRUSR | stat.S_IWUSR)

        # Create a shell-executable script that reads/writes via files
        http_script_file = f'''
import base64
import json
import ssl
import urllib.request

# Read request from input file
with open("{input_path}") as f:
    request_data = json.load(f)

method = request_data["method"]
url = request_data["url"]
headers = request_data["headers"]
body_b64 = request_data.get("body_b64")
timeout = request_data["timeout"]
verify = request_data["verify"]

try:
    if verify:
        ssl_context = ssl.create_default_context()
    else:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    body = None
    if body_b64:
        body = base64.b64decode(body_b64)

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    https_handler = urllib.request.HTTPSHandler(context=ssl_context)
    opener = urllib.request.build_opener(https_handler)

    try:
        response = opener.open(request, timeout=timeout)
        status_code = response.status
        content = response.read()
        response_headers = dict(response.headers)
    except urllib.error.HTTPError as e:
        status_code = e.code
        content = e.read()
        response_headers = dict(e.headers)

    result = {{
        "status_code": status_code,
        "content_b64": base64.b64encode(content).decode("ascii"),
        "headers": response_headers
    }}

except Exception as e:
    import traceback
    result = {{"error": str(e), "traceback": traceback.format_exc()}}

# Write result to output file
with open("{output_path}", "w") as f:
    json.dump(result, f)
'''

        # Write the script to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f_script:
            f_script.write(http_script_file)
            script_path = f_script.name

        try:
            # Run via os.system() - the ONLY fork-safe method on macOS
            # Quote paths to handle spaces in file paths (cross-platform)
            # Security: sys.executable and script_path are trusted internal values
            # (script_path is a temp file we just created), not user input.
            if os.name == "nt":
                # Windows: use double quotes
                cmd = f'"{sys.executable}" "{script_path}"'
            else:
                # Unix/macOS: use single quotes (handles most special chars)
                cmd = f"'{sys.executable}' '{script_path}'"
            returncode = os.system(cmd)  # nosec B605

            # os.system() returns the exit status shifted on Unix; extract actual code
            # On Windows, os.system() returns the command's exit code directly
            if os.name == "nt":
                actual_returncode = returncode
            else:
                # On Unix, os.system() returns the result of waitpid() which encodes
                # the exit status. os.waitstatus_to_exitcode() (Python 3.9+) handles
                # all cases (normal exit, signal termination, etc.)
                if hasattr(os, "waitstatus_to_exitcode"):
                    actual_returncode = os.waitstatus_to_exitcode(returncode)
                else:
                    # Fallback for Python < 3.9: check if exited normally
                    if os.WIFEXITED(returncode):
                        actual_returncode = os.WEXITSTATUS(returncode)
                    else:
                        # Process was killed by signal or other abnormal termination
                        actual_returncode = -1

            if actual_returncode != 0:
                elapsed = time.time() - start_time
                logger.error(
                    f"[SubprocessHttpClient] {method} {resolved_url} - "
                    f"subprocess failed with exit code {actual_returncode}"
                )
                raise RuntimeError(
                    f"HTTP subprocess failed with exit code {actual_returncode}"
                )

            # Read result from output file
            if not os.path.exists(output_path):
                raise RuntimeError("HTTP subprocess did not produce output file")

            with open(output_path) as f:
                stdout = f.read()

        except OSError as e:
            elapsed = time.time() - start_time
            logger.error(
                f"[SubprocessHttpClient] {method} {resolved_url} - "
                f"subprocess execution failed: {e}"
            )
            raise RuntimeError(f"Failed to execute HTTP subprocess: {e}") from e

        finally:
            # Clean up temp files
            for path in [input_path, output_path, script_path]:
                try:
                    os.unlink(path)
                except (OSError, FileNotFoundError):
                    pass  # Best effort cleanup

        elapsed = time.time() - start_time
        logger.debug(
            f"[SubprocessHttpClient] {method} {resolved_url} - "
            f"subprocess completed in {elapsed:.2f}s"
        )

        try:
            response_data = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.error(
                f"[SubprocessHttpClient] {method} {resolved_url} - "
                f"invalid JSON response: {stdout[:200]}"
            )
            raise RuntimeError(
                f"Invalid JSON from HTTP subprocess: {stdout[:200]}"
            ) from e

        if "error" in response_data:
            error_msg = response_data["error"]
            traceback_str = response_data.get("traceback", "")
            logger.error(
                f"[SubprocessHttpClient] {method} {resolved_url} - "
                f"request error: {error_msg}\n{traceback_str}"
            )
            raise RuntimeError(f"HTTP request failed: {error_msg}")

        # Decode response content from base64
        content_bytes = base64.b64decode(response_data["content_b64"])

        return SubprocessResponse(
            status_code=response_data["status_code"],
            _content=content_bytes,
            _headers_dict=response_data["headers"],
            url=resolved_url,
        )

    async def get(
        self, url: str, headers: dict[str, str] | None = None
    ) -> SubprocessResponse:
        """Execute an HTTP GET request.

        Args:
            url: The URL to request (may be relative).
            headers: Optional request-specific headers.

        Returns:
            SubprocessResponse containing the response data.
        """
        return await self._make_request("GET", url, headers=headers)

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: bytes | None = None,
    ) -> SubprocessResponse:
        """Execute an HTTP POST request.

        Args:
            url: The URL to request (may be relative).
            headers: Optional request-specific headers.
            json: Optional JSON-serializable data for request body.
            data: Optional raw bytes for request body.

        Returns:
            SubprocessResponse containing the response data.
        """
        return await self._make_request(
            "POST", url, headers=headers, json_data=json, data=data
        )

    async def put(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: bytes | None = None,
    ) -> SubprocessResponse:
        """Execute an HTTP PUT request.

        Args:
            url: The URL to request (may be relative).
            headers: Optional request-specific headers.
            json: Optional JSON-serializable data for request body.
            data: Optional raw bytes for request body.

        Returns:
            SubprocessResponse containing the response data.
        """
        return await self._make_request(
            "PUT", url, headers=headers, json_data=json, data=data
        )

    async def delete(
        self, url: str, headers: dict[str, str] | None = None
    ) -> SubprocessResponse:
        """Execute an HTTP DELETE request.

        Args:
            url: The URL to request (may be relative).
            headers: Optional request-specific headers.

        Returns:
            SubprocessResponse containing the response data.
        """
        return await self._make_request("DELETE", url, headers=headers)

    async def patch(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: bytes | None = None,
    ) -> SubprocessResponse:
        """Execute an HTTP PATCH request.

        Args:
            url: The URL to request (may be relative).
            headers: Optional request-specific headers.
            json: Optional JSON-serializable data for request body.
            data: Optional raw bytes for request body.

        Returns:
            SubprocessResponse containing the response data.
        """
        return await self._make_request(
            "PATCH", url, headers=headers, json_data=json, data=data
        )

    async def aclose(self) -> None:
        """Close the client (no-op for subprocess client).

        This method exists for compatibility with httpx.AsyncClient.
        No cleanup is needed since each request spawns its own subprocess.
        """
        pass


class ConnectionPool:
    """Shared connection pool for all API tests in a process.

    Generic pool that can be used by any architecture for HTTP connections.

    Fork Safety:
        This class is fork-safe. After fork(), child processes automatically
        get a fresh instance with fresh httpx.Limits objects. This prevents
        issues with corrupted threading state or stale connections from the
        parent process.

        On macOS, when running in a forked child process, this class returns
        a SubprocessHttpClient instead of httpx.AsyncClient. This avoids
        silent crashes caused by OpenSSL threading issues after fork().
    """

    _instance: "ConnectionPool | None" = None
    _creation_pid: int | None = None

    def __new__(cls) -> "ConnectionPool":
        current_pid = os.getpid()

        # Detect fork: if PID changed, we're in a child process - reset singleton
        if cls._instance is not None and cls._creation_pid != current_pid:
            cls._instance = None
            cls._creation_pid = None

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._creation_pid = current_pid
            # Initialize limits in __new__ to ensure it's set before __init__
            cls._instance._limits_initialized = False

        return cls._instance

    def __init__(self) -> None:
        # Use flag instead of hasattr for fork-safety
        if not getattr(self, "_limits_initialized", False):
            self.limits = httpx.Limits(
                max_connections=200, max_keepalive_connections=50, keepalive_expiry=300
            )
            self._limits_initialized = True

    def get_client(
        self,
        base_url: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        verify: bool = True,
    ) -> httpx.AsyncClient | SubprocessHttpClient:
        """Get an async HTTP client with custom headers and timeout.

        On macOS after fork(), this returns a SubprocessHttpClient to avoid
        silent crashes caused by OpenSSL threading issues. On other platforms
        or when not in a forked process, returns a standard httpx.AsyncClient.

        Args:
            base_url: Optional base URL for resolving relative URLs.
            headers: Optional headers dict (architecture-specific).
            timeout: Optional timeout settings.
            verify: SSL verification flag.

        Returns:
            Configured HTTP client instance (either httpx.AsyncClient or
            SubprocessHttpClient depending on platform and fork state).
        """
        if timeout is None:
            timeout = httpx.Timeout(30.0)

        # On macOS, httpx.AsyncClient crashes after fork() due to OpenSSL threading
        # issues that are not fork-safe. PyATS uses fork() for test parallelization,
        # and we cannot reliably detect if we're in a forked child because the nac_test
        # module is imported AFTER the fork happens.
        #
        # Solution: ALWAYS use SubprocessHttpClient on macOS for fork-safety.
        # The performance overhead is acceptable compared to silent crashes.
        if platform.system() == "Darwin":
            logger.debug("macOS detected, using SubprocessHttpClient for fork-safety")
            return SubprocessHttpClient(
                base_url=base_url,
                headers=headers,
                timeout=timeout,
                verify=verify,
            )

        # Non-macOS platforms: use standard httpx.AsyncClient for best performance
        client_kwargs: dict[str, Any] = {
            "limits": self.limits,
            "headers": headers or {},
            "timeout": timeout,
            "verify": verify,
        }

        # Only add base_url if it's not None (httpx fails with base_url=None)
        if base_url is not None:
            client_kwargs["base_url"] = base_url

        return httpx.AsyncClient(**client_kwargs)
