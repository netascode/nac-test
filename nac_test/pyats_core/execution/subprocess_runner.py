# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""PyATS subprocess execution functionality."""

import asyncio
import json
import logging
import os
import sys
import tempfile
import textwrap
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from nac_test.pyats_core.constants import (
    DEFAULT_BUFFER_LIMIT,
    PIPE_DRAIN_DELAY_SECONDS,
    PIPE_DRAIN_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


class SubprocessRunner:
    """Executes PyATS jobs as subprocesses and handles their output."""

    def __init__(
        self,
        output_dir: Path,
        output_handler: Callable[[str], None],
        plugin_config_path: Path | None = None,
    ):
        """Initialize the subprocess runner.

        Args:
            output_dir: Directory for test output
            output_handler: Function to process each line of stdout
            plugin_config_path: Path to the PyATS plugin configuration file
        """
        self.output_dir = output_dir
        self.output_handler = output_handler
        self.plugin_config_path = plugin_config_path

    async def execute_job(
        self, job_file_path: Path, env: dict[str, str]
    ) -> Path | None:
        """Execute a PyATS job file using subprocess.

        Args:
            job_file_path: Path to the job file
            env: Environment variables for the subprocess

        Returns:
            Path to the archive file if successful, None otherwise
        """
        # Create plugin configuration for progress reporting
        plugin_config_file = None
        try:
            plugin_config = textwrap.dedent("""
            plugins:
                ProgressReporterPlugin:
                    enabled: True
                    module: nac_test.pyats_core.progress.plugin
                    order: 1.0
            """)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix="_plugin_config.yaml", delete=False
            ) as f:
                f.write(plugin_config)
                plugin_config_file = f.name
            logger.debug(
                f"Created plugin_config {plugin_config_file} with content\n{plugin_config}"
            )

        except Exception as e:
            logger.warning(f"Failed to create plugin config: {e}")
            # If we can't create plugin config, we should probably fail
            return None

        # Generate archive name with timestamp
        job_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        archive_name = f"nac_test_job_{job_timestamp}.zip"

        # Use pyats script from the same directory as the current Python interpreter
        # to ensure we use the correct virtual environment rather than whatever
        # 'pyats' is found in PATH (which may be from a different environment)
        python_dir = Path(sys.executable).parent
        pyats_script = python_dir / "pyats"

        cmd = [
            str(pyats_script),
            "run",
            "job",
            str(job_file_path),
            "--configuration",
            plugin_config_file,
            "--archive-dir",
            str(self.output_dir),
            "--archive-name",
            archive_name,
            "--no-archive-subdir",
            "--no-mail",
            "--no-xml-report",
        ]

        # Add verbose flag if logging level is DEBUG
        if logger.isEnabledFor(logging.DEBUG):
            cmd.append("--verbose")

        logger.info(f"Executing command: {' '.join(cmd)}")
        print(f"\nExecuting PyATS with command: {' '.join(cmd)}")

        try:
            # Get buffer limit from environment or use default
            buffer_limit = int(
                os.environ.get("PYATS_OUTPUT_BUFFER_LIMIT", DEFAULT_BUFFER_LIMIT)
            )
            logger.debug(
                f"Using output buffer limit: {buffer_limit / 1024 / 1024:.2f}MB"
            )

            # Increase the buffer limit to handle large output lines (default 10MB instead of asyncio's 64KB)
            # otherwise this may trigger a `chunk exceeded` error nad nac-test WILL hang
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, **env},
                cwd=str(self.output_dir),
                limit=buffer_limit,
            )

            # Process output in real-time if we have a handler
            return_code: int | None
            if self.output_handler is not None and process.stdout is not None:
                return_code = await self._process_output_realtime(process)
            else:
                await process.communicate()
                return_code = process.returncode

            if return_code is None:
                logger.error("PyATS job did not terminate as expected.")
                return None

            if return_code != 0:
                # Return code 1 = some tests failed (expected)
                # Return code > 1 = execution error (unexpected)
                if return_code == 1:
                    logger.info(
                        f"PyATS job completed with test failures (return code: {return_code})"
                    )
                elif return_code > 1:
                    logger.error(f"PyATS job failed with return code: {return_code}")
                    return None

            # Return the expected archive path
            return self.output_dir / archive_name

        except Exception as e:
            logger.error(f"Error executing PyATS job: {e}", exc_info=True)
            return None

    async def execute_job_with_testbed(
        self, job_file_path: Path, testbed_file_path: Path, env: dict[str, Any]
    ) -> Path | None:
        """Execute a PyATS job file with a testbed using subprocess.

        This is used for device-centric execution where we need to pass a testbed file.

        Args:
            job_file_path: Path to the job file
            testbed_file_path: Path to the testbed YAML file
            env: Environment variables for the subprocess

        Returns:
            Path to the archive file if successful, None otherwise
        """
        # Create plugin configuration for progress reporting
        plugin_config_file = None
        try:
            plugin_config = textwrap.dedent("""
            plugins:
                ProgressReporterPlugin:
                    enabled: True
                    module: nac_test.pyats_core.progress.plugin
                    order: 1.0
            """)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix="_plugin_config.yaml", delete=False
            ) as f:
                f.write(plugin_config)
                plugin_config_file = f.name
        except Exception as e:
            logger.warning(f"Failed to create plugin config: {e}")
            # If we can't create plugin config, we should probably fail
            return None

        # Get device ID from environment for archive naming
        hostname = env.get("HOSTNAME", "unknown")
        archive_name = f"pyats_archive_device_{hostname}"

        # Use pyats script from the same directory as the current Python interpreter
        # to ensure we use the correct virtual environment rather than whatever
        # 'pyats' is found in PATH (which may be from a different environment)
        python_dir = Path(sys.executable).parent
        pyats_script = python_dir / "pyats"

        cmd = [
            str(pyats_script),
            "run",
            "job",
            str(job_file_path),
            "--testbed-file",
            str(testbed_file_path),
            "--configuration",
            plugin_config_file,
            "--archive-dir",
            str(self.output_dir),
            "--archive-name",
            archive_name,
            "--no-archive-subdir",
            "--no-mail",
            "--no-xml-report",
        ]

        # Add verbose flag if logging level is DEBUG, otherwise use quiet
        if logger.isEnabledFor(logging.DEBUG):
            cmd.append("--verbose")
        else:
            cmd.append("--quiet")

        logger.info(f"Executing command: {' '.join(cmd)}")
        print(f"\nExecuting PyATS with command: {' '.join(cmd)}")

        try:
            # Get buffer limit from environment or use default
            buffer_limit = int(
                os.environ.get("PYATS_OUTPUT_BUFFER_LIMIT", DEFAULT_BUFFER_LIMIT)
            )
            logger.debug(
                f"Using output buffer limit: {buffer_limit / 1024 / 1024:.2f}MB"
            )

            # Increase the buffer limit to handle large output lines (default 10MB instead of asyncio's 64KB)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, **env},
                cwd=str(self.output_dir),
                limit=buffer_limit,
            )

            # Process output in real-time
            return_code = await self._process_output_realtime(process)

            if return_code != 0:
                if return_code == 1:
                    logger.info(
                        f"PyATS job completed with test failures (return code: {return_code})"
                    )
                    # Return code 1 is normal when tests fail - archive is still valid
                elif return_code is not None:
                    logger.error(f"PyATS job failed with return code: {return_code}")
                    return None

            # Return the expected archive path
            return self.output_dir / f"{archive_name}.zip"

        except Exception as e:
            logger.error(f"Error executing PyATS job with testbed: {e}", exc_info=True)
            return None

    def _parse_progress_event(self, line: str) -> dict[str, Any] | None:
        """Parse NAC_PROGRESS line and return event dict, or None if not a progress event.

        Args:
            line: Output line to parse.

        Returns:
            Parsed event dict if line is NAC_PROGRESS event, None otherwise.
        """
        if not line.startswith("NAC_PROGRESS:"):
            return None
        try:
            result: dict[str, Any] = json.loads(
                line[13:]
            )  # Remove "NAC_PROGRESS:" prefix
            return result
        except json.JSONDecodeError:
            return None

    async def _drain_remaining_buffer_safe(self, stdout: asyncio.StreamReader) -> None:
        """Fallback drain for plugins without sentinel-based synchronization.

        This method addresses a macOS-specific race condition where the kernel pipe
        closes before asyncio's event loop reads all buffered data from the pipe.
        It is used as a fallback when the subprocess does not emit a stream_complete
        sentinel (e.g., older plugins or non-nac-test processes).

        Race condition sequence on macOS:
            1. Subprocess writes final progress events (e.g., task_end)
            2. Subprocess exits and kernel closes pipe (EOF signaled to reader)
            3. asyncio's StreamReader detects EOF and stops normal read loop
            4. Buffered data in kernel pipe buffer may not yet be transferred
            5. Normal read loop exits, leaving progress events unread

        Mitigation:
            - Sleep briefly (100ms on macOS, 1ms on Linux) to allow kernel flush
            - Explicitly drain any remaining data with timeout protection
            - Log warnings if data is lost due to timeouts

        Environment variables for CI tuning:
            - NAC_TEST_PIPE_DRAIN_DELAY: Seconds to wait before drain (default: 0.1 on macOS)
            - NAC_TEST_PIPE_DRAIN_TIMEOUT: Max seconds to wait for drain (default: 2.0)

        Args:
            stdout: The subprocess stdout stream reader.
        """
        drain_start = time.perf_counter()
        bytes_recovered = 0

        try:
            # Give kernel time to flush any remaining pipe buffers
            # This is primarily needed on macOS due to different pipe semantics
            await asyncio.sleep(PIPE_DRAIN_DELAY_SECONDS)

            remaining = await asyncio.wait_for(
                stdout.read(), timeout=PIPE_DRAIN_TIMEOUT_SECONDS
            )

            drain_duration = time.perf_counter() - drain_start

            if remaining:
                bytes_recovered = len(remaining)
                logger.debug(
                    "Recovered %d bytes from subprocess buffer after %.3fs "
                    "(delay=%.3fs, read=%.3fs)",
                    bytes_recovered,
                    drain_duration,
                    PIPE_DRAIN_DELAY_SECONDS,
                    drain_duration - PIPE_DRAIN_DELAY_SECONDS,
                )

                for line in remaining.decode("utf-8", errors="replace").splitlines():
                    line = line.rstrip()
                    if line:
                        self.output_handler(line)
            else:
                logger.debug(
                    "No buffered data recovered after %.3fs drain delay",
                    drain_duration,
                )

        except asyncio.TimeoutError:
            logger.warning(
                "Timeout after %.2fs draining subprocess buffer - some test output "
                "may be lost. Consider increasing NAC_TEST_PIPE_DRAIN_TIMEOUT.",
                PIPE_DRAIN_TIMEOUT_SECONDS,
            )
        except Exception as drain_error:
            logger.warning(
                "Failed to drain remaining subprocess buffer: %s - test results may be incomplete",
                drain_error,
            )

    async def _process_output_realtime(
        self, process: asyncio.subprocess.Process
    ) -> int:
        """Process subprocess output in real-time with sentinel-based synchronization.

        Uses stream_complete sentinel from progress plugin for reliable synchronization.
        Falls back to legacy buffer drain if sentinel is not received (backward
        compatibility with plugins that don't emit sentinels).

        Args:
            process: The subprocess to monitor.

        Returns:
            Return code of the process.
        """
        if not process.stdout:
            return await process.wait()

        try:
            consecutive_errors = 0
            max_consecutive_errors = 5
            sentinel_received = False

            while True:
                try:
                    line_bytes = await process.stdout.readline()
                    if not line_bytes:
                        # EOF - use legacy drain only if no sentinel was received
                        if not sentinel_received:
                            logger.debug(
                                "EOF without stream_complete sentinel - using legacy drain"
                            )
                            await self._drain_remaining_buffer_safe(process.stdout)
                        break

                    line = line_bytes.decode("utf-8", errors="replace").rstrip()

                    # Check for sentinel (parse once)
                    event = self._parse_progress_event(line)
                    if event is not None and event.get("event") == "stream_complete":
                        sentinel_received = True

                    # Always pass to output handler
                    self.output_handler(line)

                    # Reset error counter on successful read
                    consecutive_errors = 0

                except asyncio.LimitOverrunError as e:
                    # Handle lines that exceed the buffer limit
                    consecutive_errors += 1
                    logger.warning(
                        f"Output line exceeded buffer limit: {e}. Attempting to clear buffer..."
                    )

                    # Try to consume the oversized data in chunks
                    try:
                        # Read and discard data until we find a newline or EOF
                        while True:
                            chunk = await process.stdout.read(8192)  # Read 8KB chunks
                            if not chunk or b"\n" in chunk:
                                break
                        logger.info("Successfully cleared oversized output buffer")
                    except Exception as clear_error:
                        logger.error(f"Failed to clear buffer: {clear_error}")

                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(
                            f"Too many consecutive buffer overrun errors ({consecutive_errors}). Stopping output processing."
                        )
                        # Continue running the process but stop processing output
                        break

            # Wait for process to complete
            return await process.wait()

        except Exception as e:
            logger.error(f"Error processing output: {e}", exc_info=True)
            # Try to terminate the process
            try:
                process.terminate()
                await process.wait()
            except Exception:
                pass
            return 1
