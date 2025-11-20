# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import asyncio
import logging
import os
from pathlib import Path
from typing import Callable, Dict, Any, Optional

logger = logging.getLogger(__name__)


async def run_pabot_async(
    path: Path,
    include: list[str] = [],
    exclude: list[str] = [],
    dry_run: bool = False,
    verbose: bool = False,
    event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
    processes: Optional[int] = None,
) -> int:
    """Run pabot as async subprocess with optional progress event collection.

    Args:
        path: Path to test directory
        include: List of tags to include
        exclude: List of tags to exclude
        dry_run: Run in dry-run mode
        verbose: Enable verbose output
        event_handler: Optional callback for progress events
        processes: Number of parallel processes (auto if None)

    Returns:
        Exit code from pabot execution
    """
    from nac_test.robot.progress_event_server import ProgressEventServer

    # Build pabot command
    args = ["pabot", "--pabotlib", "--pabotlibport", "0"]

    if processes:
        args.extend(["--processes", str(processes)])

    if verbose:
        args.append("--verbose")

    if dry_run:
        args.append("--dryrun")

    for i in include:
        args.extend(["--include", i])

    for e in exclude:
        args.extend(["--exclude", e])

    # Get absolute path to socket listener
    listener_path = Path(__file__).parent / "NacProgressListenerSocket.py"
    if listener_path.exists() and event_handler:
        args.extend(["--listener", str(listener_path)])

    args.extend(
        [
            "-d",
            str(path),
            "--skiponfailure",
            "non-critical",
            "-x",
            "xunit.xml",
            str(path),
        ]
    )

    # Start event server if handler provided
    server = None
    env = os.environ.copy()

    if event_handler and listener_path.exists():
        server = ProgressEventServer(event_handler=event_handler)
        await server.start()
        env["NAC_TEST_EVENT_SOCKET"] = str(server.socket_path)
        logger.info(f"Progress event server started: {server.socket_path}")

    try:
        # Run pabot as subprocess
        logger.info(f"Executing: {' '.join(args)}")
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
            cwd=str(path.parent) if path.parent else None,
        )

        # Stream output (for logging/display)
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            # Print Robot's output (not event data, that goes via socket)
            line_str = line.decode("utf-8", errors="replace").rstrip()
            if line_str:
                print(line_str)

        # Wait for completion
        return_code = await process.wait()

        # Give server time to process any final events
        if server:
            await asyncio.sleep(0.1)

        return return_code

    finally:
        # Stop event server
        if server:
            await server.stop()
            logger.info("Progress event server stopped")


def run_pabot(
    path: Path,
    include: list[str] = [],
    exclude: list[str] = [],
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Run pabot (synchronous wrapper for backward compatibility).

    This is the legacy synchronous interface. New code should use run_pabot_async.

    Args:
        path: Path to test directory
        include: List of tags to include
        exclude: List of tags to exclude
        dry_run: Run in dry-run mode
        verbose: Enable verbose output
    """
    # Run async version without event handler
    return_code = asyncio.run(
        run_pabot_async(
            path=path,
            include=include,
            exclude=exclude,
            dry_run=dry_run,
            verbose=verbose,
            event_handler=None,
        )
    )

    # Maintain backward compatibility with SystemExit behavior
    if return_code != 0:
        raise SystemExit(return_code)
