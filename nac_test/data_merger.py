# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared data merging utilities for both Robot and PyATS test execution."""

import logging
from pathlib import Path
from typing import Any

from nac_yaml import yaml

from nac_test.core.constants import DEFAULT_MERGED_DATA_FILENAME

logger = logging.getLogger(__name__)


class DataMerger:
    """Handles merging of YAML data files for both Robot and PyATS test execution."""

    @staticmethod
    def merge_data_files(data_paths: list[Path]) -> dict[str, Any]:
        """Load and merge YAML files from provided paths.

        Args:
            data_paths: List of paths to YAML files to merge

        Returns:
            Merged dictionary containing all data from the YAML files
        """
        logger.info(
            "Loading yaml files from %s", ", ".join([str(path) for path in data_paths])
        )
        data = yaml.load_yaml_files(data_paths)
        # Ensure we always return a dict, even if yaml returns None
        return data if isinstance(data, dict) else {}

    @staticmethod
    def write_merged_data_model(
        data: dict[str, Any],
        output_directory: Path,
    ) -> None:
        """Write merged data model to YAML file.

        The output filename is always DEFAULT_MERGED_DATA_FILENAME — the single
        fixed location used by all consumers (Robot, PyATS subprocesses, cleanup).

        Args:
            data: The merged data dictionary to write
            output_directory: Directory where the YAML file will be saved
        """
        full_output_path = output_directory / DEFAULT_MERGED_DATA_FILENAME
        logger.info("Writing merged data model to %s", full_output_path)
        yaml.write_yaml_file(data, full_output_path)
