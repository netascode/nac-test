"""PyATS plugin for emitting structured progress events.

This plugin integrates with PyATS's official plugin system to provide
real-time progress updates in a format `nac-test` can control.
"""

import json
import os
import time
import logging
from pathlib import Path
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get worker ID from environment or runtime
        self.worker_id = self._get_worker_id()
    
    def _get_worker_id(self):
        """Get the worker ID from PyATS runtime or environment."""
        # First try environment variable
        if 'PYATS_TASK_WORKER_ID' in os.environ:
            return os.environ['PYATS_TASK_WORKER_ID']
        
        # Try to get from runtime if available
        try:
            if hasattr(self, 'runtime') and hasattr(self.runtime, 'job'):
                return str(self.runtime.job.uid)
        except Exception:
            pass
        
        # Default to process ID as last resort
        return str(os.getpid())
    
    def pre_job(self, job):
        """Called when the job starts."""
        try:
            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "job_start",
                "name": job.name if hasattr(job, 'name') else 'unknown',
                "timestamp": time.time(),
                "pid": os.getpid(),
                "worker_id": self.worker_id
            }
            print(f"NAC_PROGRESS:{json.dumps(event)}", flush=True)
        except Exception as e:
            logger.error(f"Failed to emit job_start event: {e}")
    
    def post_job(self, job):
        """Called when the job completes."""
        try:
            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "job_end",
                "name": job.name if hasattr(job, 'name') else 'unknown',
                "timestamp": time.time(),
                "pid": os.getpid(),
                "worker_id": self.worker_id
            }
            print(f"NAC_PROGRESS:{json.dumps(event)}", flush=True)
        except Exception as e:
            logger.error(f"Failed to emit job_end event: {e}")
    
    def pre_task(self, task):
        """Called before each test file executes."""
        try:
            # Extract clean test name from path
            test_name = self._get_test_name(task.testscript)
            
            # Get actual worker ID from task runtime
            worker_id = self._get_task_worker_id(task)
            
            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "task_start",
                "taskid": task.taskid,
                "test_name": test_name,
                "test_file": str(task.testscript),
                "worker_id": worker_id,
                "timestamp": time.time(),
                "pid": os.getpid()
            }
            print(f"NAC_PROGRESS:{json.dumps(event)}", flush=True)
        except Exception as e:
            logger.error(f"Failed to emit task_start event: {e}")
    
    def post_task(self, task):
        """Called after each test file completes."""
        try:
            test_name = self._get_test_name(task.testscript)
            worker_id = self._get_task_worker_id(task)
            
            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "task_end",
                "taskid": task.taskid,
                "test_name": test_name,
                "test_file": str(task.testscript),
                "worker_id": worker_id,
                "result": task.result.name if hasattr(task.result, 'name') else str(task.result),
                "duration": task.runtime.duration if hasattr(task.runtime, 'duration') else 0,
                "timestamp": time.time(),
                "pid": os.getpid()
            }
            print(f"NAC_PROGRESS:{json.dumps(event)}", flush=True)
        except Exception as e:
            logger.error(f"Failed to emit task_end event: {e}")
    
    def pre_section(self, section):
        """Called before each test section (setup/test/cleanup)."""
        try:
            # Only emit for actual test sections, not internal ones
            if hasattr(section, 'uid') and hasattr(section.uid, 'name'):
                if section.uid.name in ['setup', 'test', 'cleanup']:
                    event = {
                        "version": EVENT_SCHEMA_VERSION,
                        "event": "section_start",
                        "section": section.uid.name,
                        "parent_task": str(section.parent.uid) if hasattr(section, 'parent') else None,
                        "timestamp": time.time(),
                        "worker_id": self.worker_id
                    }
                    print(f"NAC_PROGRESS:{json.dumps(event)}", flush=True)
        except Exception as e:
            logger.error(f"Failed to emit section_start event: {e}")
    
    def post_section(self, section):
        """Called after each test section completes."""
        try:
            if hasattr(section, 'uid') and hasattr(section.uid, 'name'):
                if section.uid.name in ['setup', 'test', 'cleanup']:
                    event = {
                        "version": EVENT_SCHEMA_VERSION,
                        "event": "section_end",
                        "section": section.uid.name,
                        "parent_task": str(section.parent.uid) if hasattr(section, 'parent') else None,
                        "result": section.result.name if hasattr(section.result, 'name') else str(section.result),
                        "timestamp": time.time(),
                        "worker_id": self.worker_id
                    }
                    print(f"NAC_PROGRESS:{json.dumps(event)}", flush=True)
        except Exception as e:
            logger.error(f"Failed to emit section_end event: {e}")
    
    def _get_task_worker_id(self, task):
        """Get worker ID for a specific task."""
        # Try to get from task's runtime
        try:
            if hasattr(task, 'runtime') and hasattr(task.runtime, 'worker'):
                return str(task.runtime.worker)
        except Exception:
            pass
        
        # Fall back to general worker ID
        return self.worker_id
    
    def _get_test_name(self, testscript):
        """Extract a clean test name from the test file path."""
        try:
            # Convert path to dot notation like Robot does
            # /path/to/tests/operational/tenants/l3out.py -> operational.tenants.l3out
            path = Path(testscript)
            parts = path.parts
            
            # Find where 'tests' directory starts
            try:
                test_idx = parts.index('tests')
                relevant_parts = parts[test_idx + 1:]
            except ValueError:
                # If no 'tests' dir, use the whole path
                relevant_parts = parts
            
            # Remove .py extension and join with dots
            name_parts = list(relevant_parts[:-1]) + [path.stem]
            return '.'.join(name_parts)
        except Exception as e:
            logger.error(f"Failed to extract test name from {testscript}: {e}")
            # Fallback to just the filename
            return Path(testscript).stem 