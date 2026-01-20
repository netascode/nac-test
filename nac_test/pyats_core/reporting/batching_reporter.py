# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""Batching reporter for PyATS to prevent reporter server crashes.

This module implements a batching and queuing system that intercepts PyATS
reporter messages, batches them for efficiency, and handles burst conditions
gracefully. It solves the problem of reporter server crashes when processing
tests with thousands of steps (e.g., 1545 steps generating 7000+ messages).

Architecture:
    - Normal operation: Batch messages for efficient transmission
    - Burst conditions: Activate overflow queue to prevent blocking
    - Emergency scenarios: Dump to file to preserve data

Key Features:
    - Adaptive batch sizing based on load
    - Sample-based memory tracking for efficiency
    - Thread-safe operation
    - Graceful degradation under extreme load
"""

import json
import logging
import os
import pickle
import queue
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MessageMetadata:
    """Metadata for a batched message.

    Attributes:
        timestamp: When the message was received
        sequence_num: Monotonic sequence number for ordering
        context_path: Hierarchical context (e.g., "test.testcase.step")
        message_type: Type of message (e.g., "step_start", "step_stop")
        estimated_size: Estimated size in bytes (sampled)
    """

    timestamp: float
    sequence_num: int
    context_path: str
    message_type: str
    estimated_size: int = 0


class OverflowDetector:
    """Detects burst conditions using exponential moving average (EMA).

    This class monitors message rate and detects when the system should
    switch from batching mode to queue mode to handle burst conditions.
    Uses EMA for smooth detection without false positives from brief spikes.
    """

    # Burst detection threshold
    BURST_THRESHOLD = 100  # messages/second triggers queue mode

    # EMA smoothing factor (alpha)
    # Lower alpha = more smoothing, slower response
    # Higher alpha = less smoothing, faster response
    EMA_ALPHA = 0.3  # Balance between responsiveness and stability

    def __init__(self) -> None:
        """Initialize the overflow detector."""
        self.ema_rate = 0.0  # Exponential moving average of message rate
        self.last_update_time = time.time()
        self.burst_detected = False
        self.burst_start_time: float | None = None
        self.messages_since_update = 0

    def update(self, message_count: int = 1) -> bool:
        """Update rate tracking and check for burst conditions.

        Args:
            message_count: Number of messages to add (default: 1)

        Returns:
            True if burst condition detected, False otherwise
        """
        current_time = time.time()
        self.messages_since_update += message_count

        # Calculate time delta
        time_delta = current_time - self.last_update_time

        # Update rate calculation every 0.1 seconds for responsiveness
        if time_delta >= 0.1:
            # Calculate instantaneous rate
            instant_rate = self.messages_since_update / time_delta

            # Update EMA
            if self.ema_rate == 0:
                # Initialize EMA with first measurement
                self.ema_rate = instant_rate
            else:
                # Apply exponential moving average formula
                self.ema_rate = (
                    self.EMA_ALPHA * instant_rate + (1 - self.EMA_ALPHA) * self.ema_rate
                )

            # Reset counters
            self.last_update_time = current_time
            self.messages_since_update = 0

            # Check for burst condition
            if self.ema_rate > self.BURST_THRESHOLD:
                if not self.burst_detected:
                    self.burst_detected = True
                    self.burst_start_time = current_time
                    logger.info(
                        "Burst detected! EMA rate: %.1f msg/sec (threshold: %d)",
                        self.ema_rate,
                        self.BURST_THRESHOLD,
                    )
                return True
            else:
                if self.burst_detected:
                    duration = current_time - (self.burst_start_time or 0)
                    logger.info(
                        "Burst ended after %.1f seconds. Rate normalized to %.1f msg/sec",
                        duration,
                        self.ema_rate,
                    )
                    self.burst_detected = False
                    self.burst_start_time = None

        return self.burst_detected

    def get_stats(self) -> dict[str, Any]:
        """Get current detector statistics.

        Returns:
            Dictionary with current rate and burst status
        """
        return {
            "ema_rate": self.ema_rate,
            "burst_detected": self.burst_detected,
            "burst_duration": (
                time.time() - self.burst_start_time if self.burst_start_time else 0
            ),
        }


class OverflowQueue:
    """Manages overflow queue for burst message handling.

    This class handles messages when burst conditions overwhelm normal
    batching. It provides:
    - Bounded queue with configurable size limit
    - Memory tracking with configurable limit
    - Overflow-to-disk capability for extreme cases
    - Thread-safe operations
    """

    # Default configuration
    DEFAULT_MAX_SIZE = 5000  # Maximum queue size
    DEFAULT_MEMORY_LIMIT_MB = 500  # Maximum memory usage in MB

    def __init__(
        self,
        max_size: int | None = None,
        memory_limit_mb: int | None = None,
        overflow_dir: Path | None = None,
    ):
        """Initialize the overflow queue.

        Args:
            max_size: Maximum queue size (env var: NAC_TEST_QUEUE_SIZE)
            memory_limit_mb: Memory limit in MB (env var: NAC_TEST_MEMORY_LIMIT_MB)
            overflow_dir: Directory for overflow files (default: /tmp/nac_test_overflow)
        """
        # Configuration
        self.max_size = max_size or int(
            os.environ.get("NAC_TEST_QUEUE_SIZE", str(self.DEFAULT_MAX_SIZE))
        )
        self.memory_limit_mb = memory_limit_mb or int(
            os.environ.get(
                "NAC_TEST_MEMORY_LIMIT_MB", str(self.DEFAULT_MEMORY_LIMIT_MB)
            )
        )
        self.memory_limit_bytes = self.memory_limit_mb * 1024 * 1024

        # Queue and memory tracking
        self.queue: queue.Queue[tuple[Any, MessageMetadata]] = queue.Queue(
            maxsize=self.max_size
        )
        self.estimated_memory = 0
        self.message_count = 0
        self.lock = threading.Lock()  # For memory tracking

        # Overflow to disk
        default_overflow = os.path.join(tempfile.gettempdir(), "nac_test_overflow")
        self.overflow_dir = overflow_dir or Path(
            os.environ.get("NAC_TEST_OVERFLOW_DIR", default_overflow)
        )
        self.overflow_dir.mkdir(parents=True, exist_ok=True)
        self.overflow_file_count = 0
        self.overflow_active = False

        # Statistics
        self.total_enqueued = 0
        self.total_dequeued = 0
        self.total_overflowed_to_disk = 0
        self.peak_memory_usage = 0

        logger.debug(
            "OverflowQueue initialized: max_size=%d, memory_limit=%dMB",
            self.max_size,
            self.memory_limit_mb,
        )

    def enqueue(self, message: Any, metadata: MessageMetadata) -> bool:
        """Add a message to the overflow queue.

        This method handles:
        - Memory limit checking
        - Queue size checking
        - Overflow to disk if necessary

        Args:
            message: The message to enqueue
            metadata: Message metadata with size estimate

        Returns:
            True if message was queued, False if overflow to disk
        """
        # Calculate actual message size (reuse size if already calculated)
        if metadata.estimated_size == 0:
            try:
                pickled = pickle.dumps(message)
                message_size = sys.getsizeof(pickled)
                metadata.estimated_size = message_size
            except Exception as e:
                logger.warning("Failed to calculate message size: %s", e)
                message_size = 4096  # Default estimate
        else:
            message_size = metadata.estimated_size

        with self.lock:
            # Check memory limit
            if self.estimated_memory + message_size > self.memory_limit_bytes:
                logger.warning(
                    "Memory limit exceeded (%.1fMB/%.1fMB). Overflowing to disk.",
                    self.estimated_memory / (1024 * 1024),
                    self.memory_limit_mb,
                )
                self._overflow_to_disk(message, metadata)
                return False

            # Try to add to queue
            try:
                self.queue.put_nowait((message, metadata))
                self.estimated_memory += message_size
                self.message_count += 1
                self.total_enqueued += 1

                # Track peak memory
                if self.estimated_memory > self.peak_memory_usage:
                    self.peak_memory_usage = self.estimated_memory

                return True

            except queue.Full:
                logger.warning(
                    "Queue full (%d messages). Overflowing to disk.", self.max_size
                )
                self._overflow_to_disk(message, metadata)
                return False

    def dequeue(self, timeout: float = 0.1) -> tuple[Any, MessageMetadata] | None:
        """Remove and return a message from the queue.

        Args:
            timeout: Seconds to wait for a message

        Returns:
            Tuple of (message, metadata) or None if queue empty
        """
        try:
            message, metadata = self.queue.get(timeout=timeout)

            with self.lock:
                self.estimated_memory -= metadata.estimated_size
                self.message_count -= 1
                self.total_dequeued += 1

            return message, metadata

        except queue.Empty:
            return None

    def dequeue_batch(
        self, max_count: int = 100, timeout: float = 0.1
    ) -> list[tuple[Any, MessageMetadata]]:
        """Remove and return multiple messages from the queue.

        Args:
            max_count: Maximum messages to dequeue
            timeout: Seconds to wait for first message

        Returns:
            List of (message, metadata) tuples
        """
        batch = []

        # Wait for first message
        first = self.dequeue(timeout)
        if first:
            batch.append(first)

            # Get more messages without waiting
            while len(batch) < max_count:
                msg = self.dequeue(timeout=0)  # Non-blocking
                if msg:
                    batch.append(msg)
                else:
                    break

        return batch

    def _overflow_to_disk(self, message: Any, metadata: MessageMetadata) -> None:
        """Write message to disk when queue/memory limits exceeded.

        Args:
            message: Message to write
            metadata: Message metadata
        """
        self.overflow_file_count += 1
        self.total_overflowed_to_disk += 1

        # Create unique filename with timestamp and sequence
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = (
            self.overflow_dir
            / f"overflow_{timestamp}_{self.overflow_file_count:06d}.json"
        )

        try:
            # Serialize message and metadata
            data = {
                "message": str(message),  # Convert to string for JSON compatibility
                "metadata": {
                    "timestamp": metadata.timestamp,
                    "sequence_num": metadata.sequence_num,
                    "context_path": metadata.context_path,
                    "message_type": metadata.message_type,
                    "estimated_size": metadata.estimated_size,
                },
            }

            # Write to file
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug("Overflowed message %d to %s", metadata.sequence_num, filename)

            if not self.overflow_active:
                self.overflow_active = True
                logger.error(
                    "CRITICAL: Messages are being written to disk at %s. "
                    "This indicates severe overload conditions.",
                    self.overflow_dir,
                )

        except Exception as e:
            logger.error("Failed to write overflow file %s: %s", filename, e)

    def flush_to_disk(self) -> int:
        """Emergency flush of entire queue to disk.

        Used during shutdown or critical errors.

        Returns:
            Number of messages flushed to disk
        """
        count = 0
        while not self.queue.empty():
            item = self.dequeue(timeout=0)
            if item:
                message, metadata = item
                self._overflow_to_disk(message, metadata)
                count += 1

        if count > 0:
            logger.warning("Emergency flushed %d messages to disk", count)

        return count

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary with queue metrics
        """
        with self.lock:
            return {
                "current_size": self.queue.qsize(),
                "max_size": self.max_size,
                "estimated_memory_mb": self.estimated_memory / (1024 * 1024),
                "memory_limit_mb": self.memory_limit_mb,
                "peak_memory_mb": self.peak_memory_usage / (1024 * 1024),
                "total_enqueued": self.total_enqueued,
                "total_dequeued": self.total_dequeued,
                "total_overflowed": self.total_overflowed_to_disk,
                "overflow_active": self.overflow_active,
                "overflow_dir": str(self.overflow_dir),
            }


class WorkerThread:
    """Manages worker thread for draining overflow queue.

    This class handles asynchronous processing of queued messages during
    burst conditions. The worker thread:
    - Runs as a daemon thread (auto-cleanup on process exit)
    - Drains messages from overflow queue
    - Sends batches to reporter (Phase 2)
    - Implements backpressure handling
    """

    def __init__(
        self,
        overflow_queue: OverflowQueue,
        drain_callback: Callable[[list[tuple[Any, MessageMetadata]]], None]
        | None = None,
        batch_size: int = 100,
    ):
        """Initialize the worker thread manager.

        Args:
            overflow_queue: The queue to drain messages from
            drain_callback: Callback to process drained messages
            batch_size: Number of messages to drain at once
        """
        self.overflow_queue = overflow_queue
        self.drain_callback = drain_callback
        self.batch_size = batch_size

        # Thread management
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.is_running = False

        # Statistics
        self.total_processed = 0
        self.total_batches = 0
        self.last_drain_time: float = 0.0

        logger.debug("WorkerThread manager initialized with batch_size=%d", batch_size)

    def start(self) -> bool:
        """Start the worker thread if not already running.

        Returns:
            True if thread started, False if already running
        """
        if self.is_running and self.thread and self.thread.is_alive():
            logger.debug("Worker thread already running")
            return False

        # Reset stop event
        self.stop_event.clear()

        # Create and start daemon thread
        self.thread = threading.Thread(
            target=self._drain_loop,
            name="BatchingReporter-Worker",
            daemon=True,  # Dies with process
        )
        self.thread.start()
        self.is_running = True

        logger.info("Started worker thread for queue draining")
        return True

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop the worker thread gracefully.

        Args:
            timeout: Seconds to wait for thread to stop

        Returns:
            True if thread stopped, False if timeout
        """
        if not self.is_running:
            return True

        logger.debug("Stopping worker thread...")

        # Signal thread to stop
        self.stop_event.set()

        # Wait for thread to finish
        if self.thread:
            self.thread.join(timeout)

            if self.thread.is_alive():
                logger.warning("Worker thread did not stop within %s seconds", timeout)
                return False

        self.is_running = False
        logger.info("Worker thread stopped")
        return True

    def _drain_loop(self) -> None:
        """Main drain loop running in worker thread.

        Continuously drains messages from queue until stop signal.
        Implements exponential backoff when queue is empty.
        """
        logger.debug("Worker thread drain loop started")
        empty_cycles = 0

        try:
            while not self.stop_event.is_set():
                # Drain a batch from queue
                batch = self.overflow_queue.dequeue_batch(
                    max_count=self.batch_size,
                    timeout=0.1,  # Short timeout for responsiveness
                )

                if batch:
                    # Process the batch
                    self._process_batch(batch)
                    empty_cycles = 0  # Reset backoff
                    self.last_drain_time = int(time.time())
                else:
                    # Queue empty - implement exponential backoff
                    empty_cycles += 1

                    # Cap backoff at 1 second
                    sleep_time = min(0.01 * (2**empty_cycles), 1.0)

                    # Use stop_event.wait() for interruptible sleep
                    if self.stop_event.wait(sleep_time):
                        break  # Stop signal received

        except Exception as e:
            logger.error("Worker thread crashed: %s", e, exc_info=True)
            self.is_running = False

        logger.debug("Worker thread drain loop ended")

    def _process_batch(self, batch: list[tuple[Any, MessageMetadata]]) -> None:
        """Process a batch of drained messages.

        Args:
            batch: List of (message, metadata) tuples
        """
        self.total_processed += len(batch)
        self.total_batches += 1

        if self.drain_callback:
            try:
                # In Phase 2, this will send to PyATS reporter
                self.drain_callback(batch)
            except Exception as e:
                logger.error("Failed to process batch: %s", e)
        else:
            # Phase 1: Just log for now
            logger.debug(
                "Drained batch of %d messages (sequences %d-%d)",
                len(batch),
                batch[0][1].sequence_num if batch else 0,
                batch[-1][1].sequence_num if batch else 0,
            )

    def get_stats(self) -> dict[str, Any]:
        """Get worker thread statistics.

        Returns:
            Dictionary with worker metrics
        """
        return {
            "is_running": self.is_running,
            "thread_alive": self.thread.is_alive() if self.thread else False,
            "total_processed": self.total_processed,
            "total_batches": self.total_batches,
            "time_since_drain": (
                time.time() - self.last_drain_time if self.last_drain_time else 0
            ),
        }


class BatchAccumulator:
    """Accumulates messages into batches with size and time limits.

    This class implements the core batching logic with:
    - Adaptive batch sizing based on message rate
    - Time-based auto-flush to prevent message staleness
    - Sample-based memory tracking for efficiency
    - Thread-safe operations using locks
    - Overflow detection for burst conditions
    """

    # Batch size thresholds based on message rate
    BATCH_SIZE_LIGHT = 50  # < 50 msg/sec
    BATCH_SIZE_MEDIUM = 200  # 50-200 msg/sec (default)
    BATCH_SIZE_HEAVY = 500  # > 200 msg/sec

    # Rate thresholds (messages per second)
    RATE_THRESHOLD_MEDIUM = 50
    RATE_THRESHOLD_HEAVY = 200

    # Memory sampling configuration
    MEMORY_SAMPLE_INTERVAL = 10  # Sample every Nth message

    def __init__(
        self,
        default_batch_size: int = 200,
        flush_timeout: float = 0.5,
        debug_mode: bool = False,
    ):
        """Initialize the batch accumulator.

        Args:
            default_batch_size: Initial batch size (default: 200)
            flush_timeout: Seconds before auto-flush (default: 0.5)
            debug_mode: If True, track memory for every message
        """
        self.default_batch_size = default_batch_size
        self.current_batch_size = default_batch_size
        self.flush_timeout = flush_timeout
        self.debug_mode = (
            debug_mode or os.environ.get("NAC_TEST_DEBUG", "").lower() == "true"
        )

        # Thread safety
        self.lock = threading.Lock()

        # Batch storage
        self.messages: list[tuple[Any, MessageMetadata]] = []
        self.last_flush_time = time.time()

        # Message tracking
        self.sequence_counter = 0
        self.message_count = 0
        self.total_messages_processed = 0

        # Rate tracking for adaptive sizing
        self.rate_window_start = time.time()
        self.rate_window_messages = 0

        # Overflow detection
        self.overflow_detector = OverflowDetector()
        self.queue_mode_active = False

        # Memory tracking
        self.estimated_batch_memory = 0
        self.last_sampled_size = 4096  # Default estimate: 4KB per message

        # Callbacks (will be set by BatchingReporter)
        self.flush_callback: Callable[[dict[str, Any]], None] | None = None
        self.overflow_callback: Callable[[], None] | None = (
            None  # Called when burst detected
        )

        logger.debug(
            "BatchAccumulator initialized with batch_size=%d, timeout=%.2fs, debug=%s",
            self.default_batch_size,
            self.flush_timeout,
            self.debug_mode,
        )

    def add_message(
        self, message: Any, message_type: str = "unknown", context_path: str = ""
    ) -> bool:
        """Add a message to the batch.

        This method is thread-safe and handles:
        - Sequence number assignment
        - Memory tracking (sampled or full based on debug mode)
        - Rate calculation for adaptive sizing
        - Auto-flush on size or time limits

        Args:
            message: The message object to batch
            message_type: Type of message (e.g., "step_start")
            context_path: Hierarchical context (e.g., "test.testcase.step")

        Returns:
            True if batch was flushed, False otherwise
        """
        with self.lock:
            # Create metadata
            self.sequence_counter += 1
            self.message_count += 1
            self.total_messages_processed += 1

            metadata = MessageMetadata(
                timestamp=time.time(),
                sequence_num=self.sequence_counter,
                context_path=context_path,
                message_type=message_type,
            )

            # Track memory usage
            self._track_memory(message, metadata)

            # Add to batch
            self.messages.append((message, metadata))

            # Update rate tracking and check for overflow
            self._update_rate_tracking()

            # Check for burst condition
            burst_detected = self.overflow_detector.update()
            if burst_detected and not self.queue_mode_active:
                self.queue_mode_active = True
                if self.overflow_callback:
                    self.overflow_callback()
                logger.warning("Switching to queue mode due to burst condition")
            elif not burst_detected and self.queue_mode_active:
                self.queue_mode_active = False
                logger.info("Returning to normal batching mode")

            # Check if flush needed
            should_flush = self._should_flush()

            if should_flush:
                self._flush_internal()
                return True

            return False

    def _track_memory(self, message: Any, metadata: MessageMetadata) -> None:
        """Track memory usage of messages.

        Uses sampling in production (every 10th message) or full tracking
        in debug mode for accurate memory limits.

        Args:
            message: The message to track
            metadata: Message metadata to update with size estimate
        """
        # Sample-based tracking in production, full tracking in debug
        if self.debug_mode or (self.message_count % self.MEMORY_SAMPLE_INTERVAL == 0):
            try:
                # Pickle and measure the actual size
                pickled = pickle.dumps(message)
                message_size = sys.getsizeof(pickled)

                # Update last sampled size for estimation
                self.last_sampled_size = message_size

                # In debug mode, track exactly; otherwise estimate
                if self.debug_mode:
                    metadata.estimated_size = message_size
                else:
                    # Apply sample to all recent messages
                    metadata.estimated_size = message_size

                logger.debug("Sampled message size: %d bytes", message_size)

            except Exception as e:
                # If pickling fails, use last known size
                logger.warning("Failed to measure message size: %s", e)
                metadata.estimated_size = self.last_sampled_size
        else:
            # Use last sampled size for estimation
            metadata.estimated_size = self.last_sampled_size

        # Update batch memory estimate
        self.estimated_batch_memory += metadata.estimated_size

    def _update_rate_tracking(self) -> None:
        """Update message rate tracking for adaptive batch sizing.

        Calculates messages per second over a rolling window and adjusts
        batch size accordingly.
        """
        current_time = time.time()
        self.rate_window_messages += 1

        # Check if we should update the rate calculation (every second)
        window_duration = current_time - self.rate_window_start
        if window_duration >= 1.0:
            # Calculate rate
            rate = self.rate_window_messages / window_duration

            # Adjust batch size based on rate
            if rate < self.RATE_THRESHOLD_MEDIUM:
                self.current_batch_size = self.BATCH_SIZE_LIGHT
            elif rate < self.RATE_THRESHOLD_HEAVY:
                self.current_batch_size = self.BATCH_SIZE_MEDIUM
            else:
                self.current_batch_size = self.BATCH_SIZE_HEAVY

            logger.debug(
                "Message rate: %.1f msg/sec, batch size adjusted to %d",
                rate,
                self.current_batch_size,
            )

            # Reset window
            self.rate_window_start = current_time
            self.rate_window_messages = 0

    def _should_flush(self) -> bool:
        """Determine if the batch should be flushed.

        Flushes when:
        - Batch size limit reached (adaptive)
        - Time limit exceeded
        - Explicit flush requested

        Returns:
            True if flush needed, False otherwise
        """
        # Check size limit
        if len(self.messages) >= self.current_batch_size:
            logger.debug("Batch size limit reached (%d messages)", len(self.messages))
            return True

        # Check time limit
        time_since_flush = time.time() - self.last_flush_time
        if time_since_flush >= self.flush_timeout and self.messages:
            logger.debug("Batch timeout reached (%.2f seconds)", time_since_flush)
            return True

        return False

    def _flush_internal(self) -> None:
        """Internal flush implementation (must be called with lock held).

        Sends the batch to the flush callback and resets internal state.
        """
        if not self.messages:
            return

        if self.flush_callback:
            try:
                # Create batch info for callback
                batch_info = {
                    "messages": self.messages.copy(),
                    "count": len(self.messages),
                    "estimated_memory": self.estimated_batch_memory,
                    "sequence_range": (
                        self.messages[0][1].sequence_num,
                        self.messages[-1][1].sequence_num,
                    ),
                }

                # Call flush callback
                self.flush_callback(batch_info)

                logger.debug(
                    "Flushed batch of %d messages (%.1f KB)",
                    len(self.messages),
                    self.estimated_batch_memory / 1024,
                )

            except Exception as e:
                logger.error("Failed to flush batch: %s", e)
                # Don't clear messages on error - let them accumulate for retry
                return

        # Reset batch state
        self.messages.clear()
        self.estimated_batch_memory = 0
        self.last_flush_time = time.time()
        self.message_count = 0

    def flush(self) -> int:
        """Explicitly flush the current batch.

        Thread-safe method to force flush of accumulated messages.

        Returns:
            Number of messages flushed
        """
        with self.lock:
            count = len(self.messages)
            if count > 0:
                self._flush_internal()
            return count

    def get_stats(self) -> dict[str, Any]:
        """Get current accumulator statistics.

        Returns:
            Dictionary with current stats including message count,
            memory usage, and configuration.
        """
        with self.lock:
            return {
                "current_batch_size": len(self.messages),
                "estimated_memory_kb": self.estimated_batch_memory / 1024,
                "total_processed": self.total_messages_processed,
                "current_size_limit": self.current_batch_size,
                "time_since_flush": time.time() - self.last_flush_time,
                "queue_mode_active": self.queue_mode_active,
                "overflow_detector": self.overflow_detector.get_stats(),
                "debug_mode": self.debug_mode,
            }


class BatchingReporter:
    """Main batching reporter that coordinates message batching and queuing.

    This class will be extended in subsequent phases to include:
    - Overflow queue for burst handling
    - Worker thread for async processing
    - Emergency file dump for crash scenarios
    """

    def __init__(
        self,
        send_callback: Callable[[list[Any]], bool] | None = None,
        error_callback: Callable[[Exception, list[Any]], None] | None = None,
        batch_size: int | None = None,
        flush_timeout: float | None = None,
        debug_mode: bool | None = None,
    ):
        """Initialize the batching reporter.

        Args:
            send_callback: Function to call when batch is ready to send
            error_callback: Function to call on errors
            batch_size: Override default batch size (env var: NAC_TEST_BATCH_SIZE)
            flush_timeout: Override flush timeout (env var: NAC_TEST_BATCH_TIMEOUT)
            debug_mode: Override debug mode (env var: NAC_TEST_DEBUG)
        """
        # Store callbacks
        self.send_callback = send_callback
        self.error_callback = error_callback

        # Load configuration from environment with overrides
        self.batch_size = batch_size or int(
            os.environ.get("NAC_TEST_BATCH_SIZE", "200")
        )
        self.flush_timeout = flush_timeout or float(
            os.environ.get("NAC_TEST_BATCH_TIMEOUT", "0.5")
        )
        self.debug_mode = (
            debug_mode
            if debug_mode is not None
            else (os.environ.get("NAC_TEST_DEBUG", "").lower() == "true")
        )

        # Initialize batch accumulator
        self.accumulator = BatchAccumulator(
            default_batch_size=self.batch_size,
            flush_timeout=self.flush_timeout,
            debug_mode=self.debug_mode,
        )

        # Set callbacks
        self.accumulator.flush_callback = self._handle_batch_flush
        self.accumulator.overflow_callback = self._handle_overflow_detected

        # Overflow queue and worker (created lazily when needed)
        self.overflow_queue: OverflowQueue | None = None
        self.worker_thread: WorkerThread | None = None
        self.overflow_mode_active = False

        logger.info(
            "BatchingReporter initialized: batch_size=%d, timeout=%.2fs, debug=%s",
            self.batch_size,
            self.flush_timeout,
            self.debug_mode,
        )

    def _handle_batch_flush(self, batch_info: dict[str, Any]) -> None:
        """Handle a batch flush from the accumulator.

        Routes messages based on current mode:
        - Normal mode: Will send to PyATS reporter (Phase 2)
        - Overflow mode: Adds to overflow queue

        Args:
            batch_info: Information about the flushed batch
        """
        if self.overflow_mode_active and self.overflow_queue:
            # In overflow mode, add messages to queue
            messages_queued = 0
            messages_overflowed = 0

            for message, metadata in batch_info["messages"]:
                if self.overflow_queue.enqueue(message, metadata):
                    messages_queued += 1
                else:
                    messages_overflowed += 1

            logger.info(
                "Overflow mode: %d messages queued, %d overflowed to disk",
                messages_queued,
                messages_overflowed,
            )
        else:
            # Normal mode - send directly to PyATS reporter
            if self.send_callback:
                try:
                    # Send the batch via callback
                    success = self.send_callback(batch_info["messages"])
                    if success:
                        logger.info(
                            "Batch sent: %d messages, sequences %d-%d, %.1f KB",
                            batch_info["count"],
                            batch_info["sequence_range"][0],
                            batch_info["sequence_range"][1],
                            batch_info["estimated_memory"] / 1024,
                        )
                    else:
                        logger.warning(
                            "Failed to send batch: %d messages", batch_info["count"]
                        )
                        # Could fall back to queueing here if needed
                except Exception as e:
                    logger.error("Error sending batch: %s", e)
                    if self.error_callback:
                        # Extract just messages from the tuples
                        messages = [msg for msg, _ in batch_info["messages"]]
                        self.error_callback(e, messages)
            else:
                # No send callback configured yet
                logger.debug(
                    "No send callback - batch ready: %d messages, sequences %d-%d",
                    batch_info["count"],
                    batch_info["sequence_range"][0],
                    batch_info["sequence_range"][1],
                )

    def _handle_overflow_detected(self) -> None:
        """Handle overflow detection from the accumulator.

        Creates overflow queue and worker thread if not exists, activates queue mode.
        """
        if not self.overflow_queue:
            # Create overflow queue lazily on first overflow
            self.overflow_queue = OverflowQueue()
            logger.info("Created overflow queue for burst handling")

        if not self.worker_thread:
            # Create worker thread lazily on first overflow
            self.worker_thread = WorkerThread(
                overflow_queue=self.overflow_queue,
                drain_callback=self._process_drained_batch,
                batch_size=self.batch_size,  # Use same batch size for consistency
            )
            # Start the worker thread
            self.worker_thread.start()
            logger.info("Started worker thread for queue processing")
        elif not self.worker_thread.is_running:
            # Restart worker if it crashed
            self.worker_thread.start()
            logger.warning("Restarted worker thread after crash")

        self.overflow_mode_active = True
        logger.warning(
            "Overflow detected! Switched to queue mode. "
            "Messages will be queued and processed asynchronously."
        )

    def _process_drained_batch(self, batch: list[tuple[Any, MessageMetadata]]) -> None:
        """Process messages drained from overflow queue by worker thread.

        Args:
            batch: List of (message, metadata) tuples from queue
        """
        if self.send_callback:
            try:
                # Send batch to PyATS reporter via callback
                # The callback expects the batch format (list of tuples)
                success = self.send_callback(batch)
                if success:
                    logger.debug(
                        "Successfully sent drained batch: %d messages from queue",
                        len(batch),
                    )
                else:
                    logger.warning(
                        "Failed to send drained batch of %d messages", len(batch)
                    )
            except Exception as e:
                logger.error("Error processing drained batch: %s", e)
                if self.error_callback:
                    self.error_callback(e, batch)
        else:
            # No send callback configured
            logger.debug(
                "No send callback - dropped batch: %d messages from queue", len(batch)
            )

    def buffer_message(
        self, message_type: str, message_content: Any, context_path: str = ""
    ) -> None:
        """Buffer a message for batching.

        Main entry point for intercepted PyATS messages.

        Args:
            message_type: Type of message (e.g., "step_start", "step_stop")
            message_content: The actual message content
            context_path: Hierarchical context path
        """
        self.accumulator.add_message(
            message=message_content,
            message_type=message_type,
            context_path=context_path,
        )

    def flush(self) -> int:
        """Force flush of all pending messages.

        Flushes both accumulator and queue if present.

        Returns:
            Total number of messages flushed
        """
        count = self.accumulator.flush()

        # If overflow queue exists, drain it too
        if self.overflow_queue:
            # In Phase 1.2, worker thread will process these
            # For now, just log the queue size
            queue_size = self.overflow_queue.queue.qsize()
            if queue_size > 0:
                logger.warning(
                    "Overflow queue contains %d messages pending processing", queue_size
                )

        return count

    def shutdown(self, timeout: float = 10.0) -> dict[str, Any]:
        """Graceful shutdown - ensure all messages are processed.

        Args:
            timeout: Maximum time to wait for worker to finish

        Returns:
            Dictionary with shutdown statistics
        """
        logger.info("Graceful shutdown initiated")

        # Get stats before shutdown for reporting
        stats = self.get_stats()

        # Flush accumulator first
        self.flush()

        # Stop worker thread gracefully
        if self.worker_thread:
            # Give worker time to process remaining messages
            logger.debug("Waiting for worker to finish processing...")

            # Wait for queue to empty (up to timeout)
            start_time = time.time()
            while self.overflow_queue and not self.overflow_queue.queue.empty():
                if time.time() - start_time > timeout:
                    logger.warning("Timeout waiting for queue to empty")
                    break
                time.sleep(0.1)

            # Now stop the worker
            self.worker_thread.stop(timeout=5.0)

        logger.info("Graceful shutdown complete")

        # Return final stats
        return {
            "total_messages": stats["accumulator"].get("total_messages", 0),
            "total_batches": stats["accumulator"].get("total_batches", 0),
            "final_stats": stats,
        }

    def emergency_shutdown(self) -> None:
        """Emergency shutdown - flush everything to disk if necessary.

        Called during crash scenarios to preserve data.
        """
        logger.warning("Emergency shutdown initiated")

        # Stop worker thread first (if exists)
        if self.worker_thread:
            logger.debug("Stopping worker thread...")
            self.worker_thread.stop(timeout=2.0)  # Quick timeout for emergency

        # Flush accumulator
        self.flush()

        # If overflow queue exists, dump to disk
        if self.overflow_queue:
            count = self.overflow_queue.flush_to_disk()
            if count > 0:
                logger.error(
                    "Emergency: Flushed %d messages from queue to disk at %s",
                    count,
                    self.overflow_queue.overflow_dir,
                )

    def get_stats(self) -> dict[str, Any]:
        """Get current reporter statistics.

        Returns:
            Combined statistics from all components
        """
        stats = {
            "accumulator": self.accumulator.get_stats(),
            "overflow_mode_active": self.overflow_mode_active,
        }

        # Add queue stats if queue exists
        if self.overflow_queue:
            stats["overflow_queue"] = self.overflow_queue.get_stats()

        # Add worker stats if worker exists
        if self.worker_thread:
            stats["worker_thread"] = self.worker_thread.get_stats()

        return stats
