"""PyATS plugin for emitting structured progress events.

This plugin integrates with PyATS's official plugin system to provide
real-time progress updates in a format `nac-test` can control.
"""

import json
import os
import time
import logging
import ast
from pathlib import Path
from typing import Dict, Any
from pyats.easypy.plugins.bases import BasePlugin

# Event schema version for future compatibility
EVENT_SCHEMA_VERSION = "1.0"

logger = logging.getLogger(__name__)


class ProgressReporterPlugin(BasePlugin):
    """
    PyATS plugin that emits structured progress events.

    Events are emitted as JSON with a 'NAC_PROGRESS:' prefix for easy parsing.
    This gives `nac-test` complete control over the format while using PyATS's
    official extension points.

    Note: Test IDs are assigned by the orchestrator, not the plugin, to ensure
    global uniqueness across parallel workers.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Get worker ID from environment or runtime
        self.worker_id = self._get_worker_id()
        # Track task start times for duration calculation
        self.task_start_times: Dict[str, float] = {}

    def _emit_event(self, event: Dict[str, Any]) -> None:
        """Emit a progress event in the standard format."""
        print(f"NAC_PROGRESS:{json.dumps(event)}", flush=True)

    def _get_worker_id(self) -> str:
        """Get the worker ID from PyATS runtime or environment."""
        # First try environment variable
        if "PYATS_TASK_WORKER_ID" in os.environ:
            return os.environ["PYATS_TASK_WORKER_ID"]

        # Try to get from runtime if available
        try:
            if hasattr(self, "runtime") and hasattr(self.runtime, "job"):
                return str(self.runtime.job.uid)
        except Exception:
            pass

        # Default to process ID as last resort
        return str(os.getpid())

    def pre_job(self, job: Any) -> None:
        """Called when the job starts."""
        try:
            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "job_start",
                "name": job.name if hasattr(job, "name") else "unknown",
                "timestamp": time.time(),
                "pid": os.getpid(),
                "worker_id": self.worker_id,
            }
            self._emit_event(event)
        except Exception as e:
            logger.error(f"Failed to emit job_start event: {e}")

    def post_job(self, job: Any) -> None:
        """Called when the job completes."""
        try:
            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "job_end",
                "name": job.name if hasattr(job, "name") else "unknown",
                "timestamp": time.time(),
                "pid": os.getpid(),
                "worker_id": self.worker_id,
            }
            self._emit_event(event)
        except Exception as e:
            logger.error(f"Failed to emit job_end event: {e}")

    def pre_task(self, task: Any) -> None:
        """Called before each test file executes."""
        try:
            # Extract clean test name from path
            test_name = self._get_test_name(task.testscript)

            # Extract TITLE from the test file using AST parsing
            title = None
            try:
                with open(task.testscript, "r") as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == "TITLE":
                                if isinstance(node.value, ast.Str):  # Python < 3.8
                                    title = node.value.s
                                elif isinstance(
                                    node.value, ast.Constant
                                ) and isinstance(
                                    node.value.value, str
                                ):  # Python >= 3.8
                                    title = node.value.value
                                break
                        if title:
                            break

            except Exception:
                # If AST parsing fails, title will remain None
                pass

            # If no TITLE found, create a descriptive name from the path
            if not title:
                # Convert path like "templates/apic/test/operational/tenants/l3out.py"
                # to "apic.test.operational.tenants.l3out"
                test_path = Path(task.testscript)

                # Start from after 'templates' if it exists
                if "templates" in test_path.parts:
                    start_idx = test_path.parts.index("templates") + 1
                    title = ".".join(test_path.parts[start_idx:])
                    if title.endswith(".py"):
                        title = title[:-3]
                else:
                    title = test_name  # Fall back to existing test_name

            # Get actual worker ID from task runtime
            worker_id = self._get_task_worker_id(task)

            # Store task start time for duration calculation
            self.task_start_times[task.taskid] = time.time()

            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "task_start",
                "taskid": task.taskid,
                "test_name": test_name,
                "test_file": str(task.testscript),
                "worker_id": worker_id,
                "pid": os.getpid(),
                "timestamp": time.time(),
                "test_title": title,
            }

            self._emit_event(event)

        except Exception as e:
            logger.error(f"Error in pre_task: {e}")

    def post_task(self, task: Any) -> None:
        """Called after each test file completes."""
        try:
            test_name = self._get_test_name(task.testscript)
            worker_id = self._get_task_worker_id(task)

            # Calculate actual duration
            start_time = self.task_start_times.get(task.taskid, time.time())
            duration = time.time() - start_time

            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "task_end",
                "taskid": task.taskid,
                "test_name": test_name,
                "test_file": str(task.testscript),
                "worker_id": worker_id,
                "result": task.result.name
                if hasattr(task.result, "name")
                else str(task.result),
                "duration": duration,  # Use calculated duration
                "timestamp": time.time(),
                "pid": os.getpid(),
            }
            self._emit_event(event)

            # Clean up start time
            self.task_start_times.pop(task.taskid, None)
        except Exception as e:
            logger.error(f"Failed to emit task_end event: {e}")

    def pre_section(self, section: Any) -> None:
        """Called before each test section (setup/test/cleanup)."""
        try:
            # Only emit for actual test sections, not internal ones
            if hasattr(section, "uid") and hasattr(section.uid, "name"):
                if section.uid.name in ["setup", "test", "cleanup"]:
                    event = {
                        "version": EVENT_SCHEMA_VERSION,
                        "event": "section_start",
                        "section": section.uid.name,
                        "parent_task": str(section.parent.uid)
                        if hasattr(section, "parent")
                        else None,
                        "timestamp": time.time(),
                        "worker_id": self.worker_id,
                    }
                    self._emit_event(event)
        except Exception as e:
            logger.error(f"Failed to emit section_start event: {e}")

    def post_section(self, section: Any) -> None:
        """Called after each test section completes."""
        try:
            if hasattr(section, "uid") and hasattr(section.uid, "name"):
                if section.uid.name in ["setup", "test", "cleanup"]:
                    event = {
                        "version": EVENT_SCHEMA_VERSION,
                        "event": "section_end",
                        "section": section.uid.name,
                        "parent_task": str(section.parent.uid)
                        if hasattr(section, "parent")
                        else None,
                        "result": section.result.name
                        if hasattr(section.result, "name")
                        else str(section.result),
                        "timestamp": time.time(),
                        "worker_id": self.worker_id,
                    }
                    self._emit_event(event)
        except Exception as e:
            logger.error(f"Failed to emit section_end event: {e}")

    def _get_task_worker_id(self, task: Any) -> str:
        """Get worker ID for a specific task."""
        # Try to get from task's runtime
        try:
            if hasattr(task, "runtime") and hasattr(task.runtime, "worker"):
                return str(task.runtime.worker)
        except Exception:
            pass

        # Fall back to general worker ID
        return self.worker_id

    def _get_test_name(self, testscript: str) -> str:
        """Extract a clean test name from the test file path."""
        try:
            # Convert path to dot notation like Robot does
            # /path/to/tests/operational/tenants/l3out.py -> operational.tenants.l3out
            path = Path(testscript)
            parts = path.parts

            # Find where 'tests' directory starts
            try:
                test_idx = parts.index("tests")
                relevant_parts = parts[test_idx + 1 :]
            except ValueError:
                # If no 'tests' dir, use the whole path
                relevant_parts = parts

            # Remove .py extension and join with dots
            name_parts = list(relevant_parts[:-1]) + [path.stem]
            return ".".join(name_parts)
        except Exception as e:
            logger.error(f"Failed to extract test name from {testscript}: {e}")
            # Fallback to just the filename
            return Path(testscript).stem
