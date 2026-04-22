# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared data merging utilities for both Robot and PyATS test execution."""

import logging
import os
from pathlib import Path
from typing import Any

from nac_yaml import yaml

from nac_test.core.constants import (
    IS_WINDOWS,
    MERGED_DATA_FILE_MODE,
    MERGED_DATA_FILENAME,
)

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
        data = yaml.load_yaml_files(data_paths, typ="safe")
        # Ensure we always return a dict, even if yaml returns None
        return data if isinstance(data, dict) else {}

    @staticmethod
    def merged_data_path(output_directory: Path) -> Path:
        """Return the path where the merged data model file will be written.

        Single source of truth for locating the merged data file — use this
        instead of constructing the path manually from the constant.

        Args:
            output_directory: Base output directory passed to write_merged_data_model()

        Returns:
            Full path to the merged data model YAML file
        """
        return output_directory / MERGED_DATA_FILENAME

    @staticmethod
    def write_merged_data_model(
        data: dict[str, Any],
        output_directory: Path,
    ) -> Path:
        """Write merged data model to YAML file.

        The output filename is always MERGED_DATA_FILENAME — the single fixed
        location used by all consumers (Robot, PyATS subprocesses, cleanup).

        Args:
            data: The merged data dictionary to write
            output_directory: Directory where the YAML file will be saved

        Returns:
            Path to the written file (use this instead of reconstructing the path)
        """
        full_output_path = DataMerger.merged_data_path(output_directory)
        logger.info("Writing merged data model to %s", full_output_path)
        yaml.write_yaml_file(data, full_output_path)
        if not IS_WINDOWS:
            os.chmod(full_output_path, MERGED_DATA_FILE_MODE)
        return full_output_path
