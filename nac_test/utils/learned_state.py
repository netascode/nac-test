# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Utilities for reading and writing learned state files.

Learned state files capture live operational state from network devices,
enabling a two-phase test workflow:
1. Learn: Capture live state and write to YAML files
2. Verify: Load captured state via the standard -d merge mechanism

Files are written in a structure compatible with nac_yaml.merge_dict(),
so they can be passed as an additional -d path during verification.
"""

import logging
from pathlib import Path
from typing import Any

from nac_yaml import yaml

logger = logging.getLogger(__name__)


def save_learned_state(
    data: dict[str, Any],
    output_dir: Path,
    test_name: str,
    hostname: str | None = None,
) -> Path:
    """Write learned state to a YAML file.

    The output file is named by test class and optionally hostname,
    allowing per-device learned state for D2D tests.

    Args:
        data: The captured state dictionary to persist. Should be structured
            to merge cleanly with the data model when loaded via -d.
        output_dir: Directory where learned state files are written.
        test_name: Test class name (used in filename).
        hostname: Optional device hostname for D2D tests (included in filename).

    Returns:
        Path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if hostname:
        safe_hostname = hostname.replace("/", "_").replace("\\", "_")
        filename = f"{test_name}_{safe_hostname}.yaml"
    else:
        filename = f"{test_name}.yaml"

    output_path = output_dir / filename

    logger.info("Writing learned state to %s", output_path)
    yaml.write_yaml_file(data, output_path)

    return output_path


def load_learned_state(file_path: Path) -> dict[str, Any]:
    """Load learned state from a YAML file.

    Args:
        file_path: Path to the YAML file containing learned state.

    Returns:
        Dictionary containing the learned state data,
        or empty dict if the file doesn't exist or can't be loaded.
    """
    if not file_path.exists():
        logger.warning("Learned state file not found: %s", file_path)
        return {}

    try:
        data = yaml.load_yaml_files([file_path])
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error("Failed to load learned state from %s: %s", file_path, e)
        return {}
