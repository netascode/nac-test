# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for OutputProcessor test_type stamping.

OutputProcessor receives a path→type map at construction time and stamps
test_type into each test_info entry when a task_start event arrives. This
is the mechanism that lets the orchestrator split results into api_test_status
and d2d_test_status without a post-hoc path lookup.
"""

import json
import time

import pytest

from nac_test.pyats_core.common.types import DEFAULT_TEST_TYPE
from nac_test.pyats_core.execution.output_processor import OutputProcessor


def _task_start_event(test_file: str | None, taskid: str = "t1") -> str:
    """Build a minimal NAC_PROGRESS task_start line."""
    event: dict[str, object] = {
        "event": "task_start",
        "taskid": taskid,
        "test_name": "test_something",
        "timestamp": time.time(),
        "worker_id": "0",
        "pid": 1,
    }
    if test_file is not None:
        event["test_file"] = test_file
    return "NAC_PROGRESS:" + json.dumps(event)


@pytest.mark.parametrize(
    ("type_map", "test_file", "expected_type"),
    [
        ({"/tests/verify_api.py": "api"}, "/tests/verify_api.py", "api"),
        ({"/tests/verify_d2d.py": "d2d"}, "/tests/verify_d2d.py", "d2d"),
        ({}, "/tests/unknown.py", DEFAULT_TEST_TYPE),
        (None, "/tests/verify_api.py", DEFAULT_TEST_TYPE),
        ({"/tests/api.py": "api"}, None, DEFAULT_TEST_TYPE),
    ],
    ids=["known-api", "known-d2d", "unknown-path", "no-map", "missing-test-file"],
)
def test_test_type_stamped_at_task_start(
    type_map: dict[str, str] | None,
    test_file: str | None,
    expected_type: str,
) -> None:
    """test_type is stamped into test_info from test_type_by_path at task_start."""
    processor = OutputProcessor(
        test_type_by_path=type_map if type_map is not None else None
    )
    processor.process_line(_task_start_event(test_file))
    assert processor.test_status["t1"]["test_type"] == expected_type
