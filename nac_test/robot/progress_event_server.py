# -*- coding: utf-8 -*-

"""Progress event server for collecting Robot Framework test events via socket.

This server runs alongside Robot/pabot execution and collects progress events
from Robot listener instances running in parallel subprocess workers. Using a
Unix socket ensures events from parallel processes don't get interleaved like
they would with stdout.
"""

import asyncio
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)


class ProgressEventServer:
    """Socket server that collects progress events from Robot Framework listeners."""

    def __init__(
        self,
        socket_path: Optional[Path] = None,
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """Initialize the progress event server.

        Args:
            socket_path: Path for Unix domain socket (auto-generated if None)
            event_handler: Callback function to process each event
        """
        self.socket_path = socket_path or self._generate_socket_path()
        self.event_handler = event_handler

        # Socket server
        self.server: Optional[asyncio.Server] = None
        self.active_clients: Set[asyncio.StreamWriter] = set()

        # Event tracking
        self.events_received = 0
        self.events_processed = 0

        # Shutdown flag
        self._shutdown_event = asyncio.Event()

    def _generate_socket_path(self) -> Path:
        """Generate a unique socket path in temp directory."""
        temp_dir = Path(tempfile.gettempdir())
        return temp_dir / f"nac_test_robot_events_{os.getpid()}.sock"

    async def start(self) -> None:
        """Start the event server."""
        logger.info(f"Starting progress event server with socket: {self.socket_path}")

        # Remove stale socket if exists
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Start Unix socket server
        self.server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self.socket_path),
        )

        logger.info(f"Progress event server listening on: {self.socket_path}")

    async def stop(self) -> None:
        """Stop the event server and clean up."""
        logger.info("Stopping progress event server")

        # Signal shutdown
        self._shutdown_event.set()

        # Close all active client connections
        for writer in list(self.active_clients):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                logger.debug(f"Error closing client connection: {e}")

        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Clean up socket file
        try:
            if self.socket_path.exists():
                self.socket_path.unlink()
        except Exception as e:
            logger.debug(f"Error removing socket file: {e}")

        logger.info(
            f"Progress event server stopped. Received {self.events_received} events, "
            f"processed {self.events_processed}"
        )

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a client connection from a Robot listener.

        Args:
            reader: Stream reader for incoming data
            writer: Stream writer for responses
        """
        client_addr = writer.get_extra_info("peername", "unknown")
        logger.debug(f"Client connected: {client_addr}")
        self.active_clients.add(writer)

        try:
            while not self._shutdown_event.is_set():
                # Read line-delimited JSON events
                line = await reader.readline()

                if not line:
                    # Client disconnected
                    break

                try:
                    # Parse JSON event
                    event_json = line.decode("utf-8").strip()
                    if not event_json:
                        continue

                    event = json.loads(event_json)
                    self.events_received += 1

                    # Process event through handler
                    if self.event_handler:
                        try:
                            self.event_handler(event)
                            self.events_processed += 1
                        except Exception as e:
                            logger.error(
                                f"Error processing event: {e}",
                                exc_info=True,
                                extra={"event": event},
                            )

                    # No acknowledgment needed - fire and forget for better throughput

                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Failed to parse event JSON: {e}",
                        extra={"line": line.decode("utf-8", errors="replace")},
                    )
                    # Skip bad events, no response needed

                except Exception as e:
                    logger.error(f"Error handling event: {e}", exc_info=True)
                    # Log error but continue processing other events

        except asyncio.CancelledError:
            logger.debug(f"Client connection cancelled: {client_addr}")
        except Exception as e:
            logger.error(f"Error in client handler: {e}", exc_info=True)
        finally:
            # Clean up client connection
            self.active_clients.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.debug(f"Client disconnected: {client_addr}")

    @asynccontextmanager
    async def run_context(self):
        """Context manager for running the event server.

        Usage:
            async with server.run_context():
                # Server is running
                # Run Robot tests here
                pass
            # Server automatically stopped and cleaned up
        """
        await self.start()
        try:
            yield self
        finally:
            await self.stop()
