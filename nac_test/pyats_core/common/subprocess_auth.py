# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Fork-safe subprocess authentication executor for macOS compatibility.

This module provides a subprocess-based authentication mechanism that avoids
the macOS fork+SSL crash issue. On macOS, after PyATS uses fork() to create
task subprocesses, SSL/TLS operations can crash silently due to OpenSSL
threading primitives that are not fork-safe.

Problem:
    After fork() on macOS:
    - httpx/aiohttp/requests crash due to SSL context issues
    - subprocess.run() crashes due to pipe creation issues
    - asyncio.to_thread() uses ThreadPoolExecutor which breaks
    - os.popen() also crashes (uses pipes internally)

Solution:
    Use os.system() with temp files to execute authentication in a clean
    subprocess. This approach:
    1. Writes auth parameters to an input temp file
    2. Spawns a subprocess via os.system() (the ONLY fork-safe method)
    3. The subprocess reads params, performs auth, writes result to output file
    4. We read the result from the output temp file

Usage:
    The caller provides:
    - auth_params: Dict containing authentication parameters (URL, credentials, etc.)
    - auth_script_body: Python code body that performs the actual authentication

    The auth_script_body should:
    - Assume a `params` dict is already loaded (done by the executor)
    - Set a `result` dict with either:
      - Success data: {"token": "...", "expires_in": 1800, ...}
      - Error: {"error": "error message"}

Example:
    auth_params = {
        "url": "https://api.example.com",
        "username": "admin",
        "password": "secret"
    }

    auth_script_body = '''
    import urllib.request
    import json

    url = params["url"]
    username = params["username"]
    password = params["password"]

    # Perform authentication...
    request = urllib.request.Request(f"{url}/auth", method="POST")
    # ... authentication logic ...

    result = {"token": token, "expires_in": 3600}
    '''

    auth_data = execute_auth_subprocess(auth_params, auth_script_body)
"""

import json
import logging
import os
import shlex
import stat
import sys
import tempfile
from typing import Any

logger = logging.getLogger(__name__)


class SubprocessAuthError(RuntimeError):
    """Raised when subprocess authentication fails.

    This exception indicates that the authentication subprocess either:
    - Failed to execute (non-zero exit code)
    - Produced invalid output (not valid JSON)
    - Returned an error from the authentication logic
    """

    pass


def _parse_exit_code(returncode: int) -> int:
    """Parse the exit code from os.system() return value.

    On Windows, os.system() returns the command's exit code directly.
    On Unix/macOS, os.system() returns the result of waitpid() which encodes
    the exit status in a platform-specific way.

    Args:
        returncode: The raw return value from os.system().

    Returns:
        The actual exit code of the subprocess.
    """
    if os.name == "nt":
        # Windows returns exit code directly
        return returncode

    # Unix/macOS: os.system() returns waitpid() result
    # os.waitstatus_to_exitcode() (Python 3.9+) handles all cases
    if hasattr(os, "waitstatus_to_exitcode"):
        return os.waitstatus_to_exitcode(returncode)

    # Fallback for Python < 3.9: check if exited normally
    if os.WIFEXITED(returncode):
        return os.WEXITSTATUS(returncode)

    # Process was killed by signal or other abnormal termination
    return -1


def _quote_path_for_shell(path: str) -> str:
    """Quote a file path for safe shell command execution.

    Args:
        path: The file path to quote.

    Returns:
        The quoted path appropriate for the current platform's shell.
    """
    if os.name == "nt":
        # Windows: use double quotes
        return f'"{path}"'

    # Unix/macOS: use shlex.quote() for proper escaping
    return shlex.quote(path)


def _escape_path_for_python(path: str) -> str:
    """Escape a file path for embedding in Python source code as a string literal.

    Args:
        path: The file path to escape.

    Returns:
        A properly escaped Python string literal (with quotes).
    """
    # Use repr() to get a properly escaped Python string literal
    return repr(path)


def _set_secure_permissions(path: str) -> None:
    """Set secure file permissions (owner read/write only).

    On Unix/macOS, sets explicit chmod 0600.
    On Windows, relies on the secure temp directory permissions.

    Args:
        path: The file path to secure.
    """
    if os.name != "nt":
        # Unix/macOS: explicit chmod 0600
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    # Windows: temp directory is already user-private by default


def execute_auth_subprocess(
    auth_params: dict[str, Any],
    auth_script_body: str,
) -> dict[str, Any]:
    """Execute authentication logic in a subprocess to avoid fork+SSL crashes.

    This function spawns a clean Python subprocess to perform authentication,
    avoiding the macOS fork+SSL issue where SSL operations crash after fork().

    The function handles all temp file management internally:
    1. Creates input temp file with auth_params
    2. Creates output temp file for the result
    3. Creates script temp file with wrapper code
    4. Executes via os.system() (the only fork-safe method on macOS)
    5. Reads and returns the result
    6. Cleans up all temp files

    Args:
        auth_params: Dictionary containing authentication parameters.
            This dict is serialized to JSON and made available to the
            auth_script_body as the `params` variable.

        auth_script_body: Python code that performs the authentication.
            This code should:
            - Assume `params` dict is already loaded from the input file
            - Set a `result` dict with either success data or {"error": "..."}

            The executor wraps this code with file I/O boilerplate:
            - Reads params from input file before executing auth_script_body
            - Writes result to output file after auth_script_body completes

    Returns:
        Dictionary containing the authentication result.
        On success, this is whatever the auth_script_body set as `result`.
        The caller should check for an "error" key to detect failures.

    Raises:
        SubprocessAuthError: If the subprocess fails to execute, produces
            invalid output, or returns an error in the result.

    Example:
        >>> auth_params = {"url": "https://api.example.com", "user": "admin"}
        >>> auth_script_body = '''
        ... # params dict is already available
        ... import urllib.request
        ... # ... perform authentication ...
        ... result = {"token": "abc123", "expires_in": 3600}
        ... '''
        >>> auth_data = execute_auth_subprocess(auth_params, auth_script_body)
        >>> print(auth_data["token"])
        abc123
    """
    # Initialize paths to None for safe cleanup in finally block
    input_path: str | None = None
    output_path: str | None = None
    script_path: str | None = None

    try:
        # Create input temp file with auth parameters
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_auth_input.json", delete=False
        ) as f_in:
            json.dump(auth_params, f_in)
            input_path = f_in.name
        _set_secure_permissions(input_path)

        # Create output temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_auth_output.json", delete=False
        ) as f_out:
            output_path = f_out.name
        _set_secure_permissions(output_path)

        # Build the full script with file I/O wrapper
        # The wrapper handles reading params and writing result
        # Use _escape_path_for_python for paths inside the Python script
        input_path_escaped = _escape_path_for_python(input_path)
        output_path_escaped = _escape_path_for_python(output_path)

        full_script = f"""
import json
import sys

# Read auth params from input file (handled by executor)
try:
    with open({input_path_escaped}) as f:
        params = json.load(f)
except Exception as e:
    result = {{"error": f"Failed to read input params: {{e}}"}}
    with open({output_path_escaped}, "w") as f:
        json.dump(result, f)
    sys.exit(0)

# Initialize result to error state in case auth_script_body doesn't set it
result = {{"error": "auth_script_body did not set result"}}

try:
    # === BEGIN AUTH SCRIPT BODY ===
{_indent_script_body(auth_script_body, indent=4)}
    # === END AUTH SCRIPT BODY ===
except Exception as e:
    import traceback
    result = {{"error": str(e), "traceback": traceback.format_exc()}}

# Write result to output file (handled by executor)
with open({output_path_escaped}, "w") as f:
    json.dump(result, f)
"""

        # Create script temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_auth_script.py", delete=False
        ) as f_script:
            f_script.write(full_script)
            script_path = f_script.name
        _set_secure_permissions(script_path)

        # Execute via os.system() - the ONLY fork-safe method on macOS
        # Use shell quoting for command line execution
        python_quoted = _quote_path_for_shell(sys.executable)
        script_quoted = _quote_path_for_shell(script_path)
        cmd = f"{python_quoted} {script_quoted}"

        logger.debug("[SubprocessAuth] Executing authentication subprocess")
        returncode = os.system(cmd)  # nosec B605 - paths are controlled internal values

        # Parse exit code
        actual_exit_code = _parse_exit_code(returncode)
        if actual_exit_code != 0:
            logger.error(
                "[SubprocessAuth] Subprocess failed with exit code %d",
                actual_exit_code,
            )
            raise SubprocessAuthError(
                f"Authentication subprocess failed with exit code {actual_exit_code}"
            )

        # Read result from output file
        if output_path is None or not os.path.exists(output_path):
            raise SubprocessAuthError(
                "Authentication subprocess did not produce output file"
            )

        with open(output_path) as f:
            output_content = f.read()

        # Parse JSON result
        try:
            result: dict[str, Any] = json.loads(output_content)
        except json.JSONDecodeError as e:
            logger.error(
                "[SubprocessAuth] Invalid JSON in output: %s",
                output_content[:200],
            )
            raise SubprocessAuthError(
                f"Invalid JSON from authentication subprocess: {output_content[:200]}"
            ) from e

        # Check for error in result
        if "error" in result:
            error_msg = result["error"]
            traceback_str = result.get("traceback", "")
            logger.error(
                "[SubprocessAuth] Authentication failed: %s\n%s",
                error_msg,
                traceback_str,
            )
            raise SubprocessAuthError(f"Authentication failed: {error_msg}")

        logger.debug("[SubprocessAuth] Authentication completed successfully")
        return result

    finally:
        # Clean up temp files
        for path in [input_path, output_path, script_path]:
            if path is not None:
                try:
                    os.unlink(path)
                except (OSError, FileNotFoundError):
                    pass  # Best effort cleanup


def _indent_script_body(script_body: str, indent: int = 4) -> str:
    """Indent each line of the script body for embedding in wrapper.

    Args:
        script_body: The Python code to indent.
        indent: Number of spaces to indent each line.

    Returns:
        The indented script body.
    """
    indent_str = " " * indent
    lines = script_body.split("\n")
    return "\n".join(indent_str + line if line.strip() else line for line in lines)
