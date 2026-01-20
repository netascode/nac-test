# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import importlib.util
import json
import logging
import os
import pathlib
import re
import shutil
import sys
from pathlib import Path
from typing import Any, cast

from jinja2 import (  # type: ignore
    ChainableUndefined,
    Environment,
    FileSystemLoader,
    Undefined,
)

from nac_test.data_merger import DataMerger

logger = logging.getLogger(__name__)


class StrictChainableUndefined(ChainableUndefined):
    __iter__ = __str__ = __len__ = Undefined._fail_with_undefined_error  # type: ignore
    __eq__ = __ne__ = __bool__ = __hash__ = Undefined._fail_with_undefined_error  # type: ignore
    __contains__ = Undefined._fail_with_undefined_error  # type: ignore


class RobotWriter:
    def __init__(
        self,
        data_paths: list[Path],
        filters_path: Path | None,
        tests_path: Path | None,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
    ) -> None:
        self.data = DataMerger.merge_data_files(data_paths)
        # Convert OrderedDict to dict once during initialization instead of per-template
        # This eliminates expensive JSON round-trip serialization for each template render
        self.template_data = self._convert_data_model_for_templates(self.data)
        self.filters: dict[str, Any] = {}
        self.include_tags = include_tags if include_tags is not None else []
        self.exclude_tags = exclude_tags if exclude_tags is not None else []
        if filters_path:
            logger.info("Loading filters")
            for filename in os.listdir(filters_path):
                if Path(filename).suffix == ".py":
                    file_path = Path(filters_path, filename)
                    spec = importlib.util.spec_from_file_location(
                        "nac_test.filters", file_path
                    )
                    if spec is not None:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules["nac_test.filters"] = mod
                        if spec.loader is not None:
                            spec.loader.exec_module(mod)
                            self.filters[mod.Filter.name] = mod.Filter
        self.tests: dict[str, Any] = {}
        if tests_path:
            logger.info("Loading tests")
            for filename in os.listdir(tests_path):
                if Path(filename).suffix == ".py":
                    file_path = Path(tests_path, filename)
                    spec = importlib.util.spec_from_file_location(
                        "nac_test.tests", file_path
                    )
                    if spec is not None:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules["nac_test.tests"] = mod
                        if spec.loader is not None:
                            spec.loader.exec_module(mod)
                            self.tests[mod.Test.name] = mod.Test

    def _convert_data_model_for_templates(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert nested OrderedDict to dict to avoid duplicate dict keys.

        This method performs the same conversion that was previously done per-template,
        but centralizes it during initialization for performance efficiency.

        Args:
            data: Raw data model from DataMerger (may contain OrderedDict structures)

        Returns:
            Converted data model safe for Jinja template rendering

        Note:
            JSON round-trip approach is used as it's safe for all serializable data
            and handles nested OrderedDict structures reliably.
        """
        logger.debug(
            "Converting data model for template rendering (one-time conversion)"
        )
        try:
            # JSON round-trip to convert nested OrderedDict to dict
            # This preserves all data while fixing duplicate key issues (e.g., 'tag' fields)
            converted_data = cast(dict[str, Any], json.loads(json.dumps(data)))
            logger.debug("Data model conversion completed successfully")
            return converted_data
        except Exception as e:
            logger.warning(f"Data model conversion failed: {e}. Using original data.")
            # Fallback to original data if conversion fails
            return data

    def render_template(
        self, template_path: Path, output_path: Path, env: Environment, **kwargs: Any
    ) -> None:
        """Render single robot jinja template"""
        logger.info("Render robot template: %s", template_path)
        # add robot tags to kwargs
        kwargs["robot_include_tags"] = self.include_tags
        kwargs["robot_exclude_tags"] = self.exclude_tags
        # create output directory if it does not exist yet
        pathlib.Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)

        template = env.get_template(str(template_path))
        # Use pre-converted data model (converted once during initialization)
        result = template.render(self.template_data, **kwargs)

        # remove extra empty lines
        lines = result.splitlines()
        cleaned_lines = []
        for index, line in enumerate(lines):
            if len(line.strip()):
                cleaned_lines.append(line)
            else:
                if index + 1 < len(lines):
                    next_line = lines[index + 1]
                    if len(next_line) and not next_line[0].isspace():
                        cleaned_lines.append(line)
        result = os.linesep.join(cleaned_lines)

        with open(output_path, "w") as file:
            file.write(result)

    def _fix_duplicate_path(self, *paths: str) -> Path:
        """Helper function to detect existing paths with non-matching case. Returns a unique path to work with case-insensitve filesystems."""
        directory = os.path.join(*paths[:-1])
        if os.path.exists(directory):
            entries = os.listdir(directory)
            lower_case_entries = [path.lower() for path in entries]
            if paths[-1].lower() in lower_case_entries and paths[-1] not in entries:
                return Path(*paths[:-1], "_" + paths[-1])
        return Path(os.path.join(*paths))

    def write(self, templates_path: Path, output_path: Path) -> None:
        """Render Robot test suites."""
        env = Environment(
            loader=FileSystemLoader(templates_path),
            undefined=StrictChainableUndefined,
            lstrip_blocks=True,
            trim_blocks=True,
        )
        for name, filter in self.filters.items():
            env.filters[name] = filter.filter
        for name, test in self.tests.items():
            env.tests[name] = test.test

        for dir, _, files in os.walk(templates_path):
            for filename in files:
                if Path(filename).suffix not in [".robot", ".resource", ".j2"]:
                    logger.info(
                        "Skip file with unknown file extension (not one of .robot, .resource or .j2): %s",
                        Path(dir, filename),
                    )
                    out = Path(output_path, os.path.relpath(dir, templates_path))
                    pathlib.Path(out).mkdir(parents=True, exist_ok=True)
                    shutil.copy(Path(dir, filename), out)
                    continue
                rel = os.path.relpath(dir, templates_path)
                t_path = Path(rel, filename)

                # search for directives
                pattern = re.compile("{#(.+?)#}")
                content = ""
                next_template = False
                try:
                    with open(Path(dir, filename)) as file:
                        content = file.read()
                except:  # noqa: E722
                    logger.warning("Could not open/read file: %s", Path(dir, filename))
                    continue
                for match in re.finditer(pattern, content):
                    params = match.group().split(" ")
                    if len(params) == 6 and params[1] in [
                        "iterate_list",
                        "iterate_list_folder",
                    ]:
                        next_template = True
                        path = params[2].split(".")
                        attr = params[3]
                        elem: Any = self.template_data
                        for p in path:
                            elem = elem.get(p, {})
                        if not isinstance(elem, list):
                            continue
                        for item in elem:
                            value = str(item.get(attr))
                            if value is None:  # type: ignore[unreachable]
                                continue  # type: ignore[unreachable]
                            extra: dict[str, Any] = {}
                            if "[" in params[4]:
                                index = params[4].split("[")[1].split("]")[0]
                                extra_list: list[Any] = [None] * (int(index) + 1)
                                extra_list[int(index)] = value
                                extra = {params[4].split("[")[0]: extra_list}
                            else:
                                extra = {params[4]: value}
                            if params[1] == "iterate_list":
                                o_dir = self._fix_duplicate_path(
                                    str(output_path), rel, value
                                )
                                o_path = Path(o_dir, filename)
                            else:
                                foldername = os.path.splitext(filename)[0]
                                new_filename = (
                                    value + "." + os.path.splitext(filename)[1][1:]
                                )
                                o_path = self._fix_duplicate_path(
                                    str(output_path), rel, foldername, new_filename
                                )
                            self.render_template(t_path, Path(o_path), env, **extra)
                if next_template:
                    continue

                o_path = Path(output_path, rel, filename)
                self.render_template(t_path, o_path, env)

    def write_merged_data_model(
        self,
        output_directory: Path,
        filename: str = "merged_data_model_test_variables.yaml",
    ) -> None:
        """Writes the merged data model to a specified YAML file.

        This method takes the internal, merged data dictionary (`self.data`)
        and writes it to a YAML file in the specified output directory.

        Args:
            output_directory: The directory where the YAML file will be saved.
            filename: The name of the output YAML file.
        """
        DataMerger.write_merged_data_model(self.data, output_directory, filename)
