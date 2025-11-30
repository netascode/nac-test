# -*- coding: utf-8 -*-

"""PyATS subprocess execution functionality."""

import asyncio
import logging
import os
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from nac_test.pyats_core.constants import DEFAULT_BUFFER_LIMIT

logger = logging.getLogger(__name__)


class SubprocessRunner:
    """Executes PyATS jobs as subprocesses and handles their output."""

    def __init__(
        self,
        output_dir: Path,
        output_handler: Callable[[str], None],
        plugin_config_path: Optional[Path] = None,
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
        self, job_file_path: Path, env: Dict[str, str]
    ) -> Optional[Path]:
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

        cmd = [
            "pyats",
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
        print(f"Executing PyATS with command: {' '.join(cmd)}")

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
            return_code: Optional[int]
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
        # finally:  -- UNCOMMENT ME
        #     # Clean up the temporary plugin config file
        #     if plugin_config_file and os.path.exists(plugin_config_file):
        #         try:
        #             os.unlink(plugin_config_file)
        #         except Exception:
        #             pass

    async def execute_job_with_testbed(
        self, job_file_path: Path, testbed_file_path: Path, env: Dict[str, Any]
    ) -> Optional[Path]:
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

        cmd = [
            "pyats",
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
        print(f"Executing PyATS with command: {' '.join(cmd)}")

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
        # finally:
        #     # Clean up the temporary plugin config file
        #     if plugin_config_file and os.path.exists(plugin_config_file):
        #         try:
        #             os.unlink(plugin_config_file)
        #         except Exception:
        #             pass

    async def _process_output_realtime(
        self, process: asyncio.subprocess.Process
    ) -> int:
        """Process subprocess output in real-time.

        Args:
            process: The subprocess to monitor

        Returns:
            Return code of the process
        """
        if not process.stdout:
            return await process.wait()

        try:
            consecutive_errors = 0
            max_consecutive_errors = 5

            while True:
                try:
                    line_bytes = await process.stdout.readline()
                    if not line_bytes:
                        break

                    line = line_bytes.decode("utf-8", errors="replace").rstrip()

                    # # Log raw output in DEBUG mode
                    # logger.debug(line)

                    # Process the line if we have a handler
                    if self.output_handler is not None:
                        self.output_handler(line)
                    else:
                        # Default: just print it
                        print(line)

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
