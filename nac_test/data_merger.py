# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared data merging utilities for both Robot and PyATS test execution."""

import logging
import os
from pathlib import Path
from typing import Any, TypeVar, cast

from nac_yaml import yaml
from ruamel.yaml import CommentedMap, CommentedSeq

from nac_test.core.constants import (
    IS_WINDOWS,
    MERGED_DATA_FILE_MODE,
    MERGED_DATA_FILENAME,
)

T = TypeVar("T")


def _to_builtin_types(value: T) -> T:
    """Recursively convert ruamel CommentedMap/CommentedSeq to plain dict/list.

    This strips all ruamel-specific metadata (tag, anchor, ca, etc.) so that
    downstream consumers (Jinja2 templates) see only standard Python types
    and never encounter ruamel-internal attributes via dot-notation.
    """
    v: Any = value
    if isinstance(v, CommentedMap):
        v = dict(v)
    elif isinstance(v, CommentedSeq):
        v = list(v)

    if isinstance(v, dict):
        v = {k: _to_builtin_types(vv) for k, vv in v.items()}
    elif isinstance(v, list):
        v = [_to_builtin_types(vv) for vv in v]

    return cast(T, v)


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
        if not isinstance(data, dict):
            return {}
        # Strip ruamel metadata (CommentedMap/CommentedSeq → dict/list) so
        # Jinja2 templates never see ruamel-internal attributes via dot-notation.
        return _to_builtin_types(data)

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
