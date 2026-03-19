# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import copy
import importlib.util
import json
import logging
import os
import pathlib
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from jinja2 import (  # type: ignore
    ChainableUndefined,
    Environment,
    FileSystemLoader,
    Undefined,
)
from nac_yaml import yaml
from robot.api import SuiteVisitor, TestSuite  # type: ignore
from robot.utils import is_truthy

logger = logging.getLogger(__name__)


class StrictChainableUndefined(ChainableUndefined):
    __iter__ = __str__ = __len__ = Undefined._fail_with_undefined_error  # type: ignore
    __eq__ = __ne__ = __bool__ = __hash__ = Undefined._fail_with_undefined_error  # type: ignore
    __contains__ = Undefined._fail_with_undefined_error  # type: ignore


class TestCollector(SuiteVisitor):
    """Visitor to collect test or suite names to construct the pabot ordering file."""

    def __init__(self, full_suite_name: str) -> None:
        self.test_names: list[str] = []
        self.full_suite_name = full_suite_name
        self.test_concurrency: bool = False

    def start_suite(self, suite: Any) -> None:
        # Check for "Test Concurrency" metadata (case-insensitive)
        for key, value in suite.metadata.items():
            if key.lower() == "test concurrency" and is_truthy(value):
                self.test_concurrency = True
                break

    def start_test(self, test: Any) -> None:
        """Visit a test case."""
        test_name = self.full_suite_name + "." + test.name
        self.test_names.append(test_name)


class RobotWriter:
    def __init__(
        self,
        data_paths: list[Path],
        filters_path: Path | None,
        tests_path: Path | None,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
    ) -> None:
        logger.info("Loading yaml files from %s", data_paths)
        self.data = yaml.load_yaml_files(data_paths)
        self.filters: dict[str, Any] = {}
        self.include_tags = include_tags or []
        self.exclude_tags = exclude_tags or []
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
        self.ordering_entries: list[str] = []

    def render_template(
        self,
        template_path: Path,
        output_path: Path,
        env: Environment,
        custom_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Render single robot jinja template"""
        logger.info("Render robot template: %s", template_path)
        # add robot tags to kwargs
        kwargs["robot_include_tags"] = self.include_tags
        kwargs["robot_exclude_tags"] = self.exclude_tags
        # create output directory if it does not exist yet
        pathlib.Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)

        template = env.get_template(template_path.as_posix())
        # hack to convert nested ordereddict to dict, to avoid duplicate dict keys
        # json roundtrip should be safe as everything should be serializable
        data_source = custom_data if custom_data is not None else self.data
        data = json.loads(json.dumps(data_source))
        result = template.render(data, **kwargs)

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
        """Helper function to detect existing paths with non-matching case.

        Returns a unique path to work with case-insensitive filesystems.
        """
        directory = os.path.join(*paths[:-1])
        if os.path.exists(directory):
            entries = os.listdir(directory)
            lower_case_entries = [path.lower() for path in entries]
            if paths[-1].lower() in lower_case_entries and paths[-1] not in entries:
                return Path(*paths[:-1], "_" + paths[-1])
        return Path(os.path.join(*paths))

    def _chunk_nested_objects(
        self, data: dict[str, Any], object_path: str, chunk_size: int
    ) -> list[dict[str, Any]]:
        """Split nested objects into chunks.

        Args:
            data: The data structure to chunk
            object_path: Dot-separated path to objects to chunk (e.g., "services.endpoints")
            chunk_size: Number of objects per chunk

        Returns:
            List of modified data structures, each containing a subset of objects
        """
        path_parts = object_path.split(".")

        # Handle simple path (single level) vs nested path
        if len(path_parts) == 1:
            # Simple case: chunk objects directly from the data
            objects = data.get(path_parts[0], [])
            if not isinstance(objects, list):
                return [data]  # Return original if not a list

            # Split objects into chunks
            chunks = []
            for i in range(0, len(objects), chunk_size):
                chunks.append(objects[i : i + chunk_size])

            # Create modified data for each chunk
            chunked_data = []
            for chunk in chunks:
                chunked_item = copy.deepcopy(data)
                chunked_item[path_parts[0]] = chunk
                chunked_data.append(chunked_item)

            return chunked_data

        elif len(path_parts) == 2:
            # Nested case: collect objects from nested structure
            parent_key, child_key = path_parts
            all_objects = []

            # Collect all nested objects with their parent context
            for parent in data.get(parent_key, []):
                parent_name = parent.get("name", "")
                for obj in parent.get(child_key, []):
                    all_objects.append((parent_name, obj))

            # Split into chunks
            object_chunks = []
            for i in range(0, len(all_objects), chunk_size):
                object_chunks.append(all_objects[i : i + chunk_size])

            # Create modified data for each chunk
            chunked_data = []
            for chunk in object_chunks:
                chunked_item = copy.deepcopy(data)

                # Group objects by parent for this chunk
                parent_objects: dict[str, list[Any]] = {}
                for parent_name, obj in chunk:
                    if parent_name not in parent_objects:
                        parent_objects[parent_name] = []
                    parent_objects[parent_name].append(obj)

                # Update parent objects to only include objects from this chunk
                if parent_key in chunked_item:
                    for parent in chunked_item[parent_key]:
                        parent_name = parent.get("name", "")
                        if parent_name in parent_objects:
                            parent[child_key] = parent_objects[parent_name]
                        else:
                            parent[child_key] = []

                    # Remove parents that have no objects in this chunk
                    chunked_item[parent_key] = [
                        parent
                        for parent in chunked_item[parent_key]
                        if parent.get(child_key, [])
                    ]

                chunked_data.append(chunked_item)

            return chunked_data

        else:
            # More complex nesting not supported yet
            raise ValueError(
                f"Object path with more than 2 levels not supported: {object_path}"
            )

    @staticmethod
    def _calculate_full_suite_name(output_path: Path, robot_file: Path) -> str:
        """
        We need to collect the final robot suite name (ex. Output.Config.Tenants.L3Out)
        and note this in the ordering file. The suite name is derived from
        1. the output path (the last part of it if the path is an absolute path)
        2. the path of the robot file relative the the output path
        Each part of 1 and 2 is passed through a robot API to (ex: config -> Config) and
        joined with a dot (.) to form the suite name.
        Example 1:
            Input:  output_path = /tmp/foo/output
                    filename = /tmp/foo/output/config/tenants/ABC/L3Out.robot
            Result: suite_dirname = Output.Config.Tenants.ABC.L3Out
        Example 2:
            Input:  output_path = foobar
                    filename = foobar/integration_tests/whatever.robot
            Result: suite_dirname = Foobar.Integration Tests.Whatever
        """
        relative_path = robot_file.parent.relative_to(output_path)
        path_parts = [output_path.name] + list(relative_path.parts) + [robot_file.stem]
        return ".".join([TestSuite.name_from_source(p) for p in path_parts if p])

    def _update_ordering_entries(self, output_path: Path, robot_file: Path) -> None:
        """
        parse the resulting files and check if a) has at least one test case
        and b) if it has the "Test Concurrency" metadata set indicating that it
        the individual tests can be run in parallel (helps for large suites with many test cases,
        like epg or l3out). Empty rendered suites without any test cases will be removed here.
        """
        if robot_file.suffix != ".robot":
            # if resource files are stored as .robot they would be parsed and possibly removed!! need to think..
            return

        suite = TestSuite.from_file_system(str(robot_file), allow_empty_suite=True)
        full_suite_name = self._calculate_full_suite_name(output_path, robot_file)
        collector = TestCollector(full_suite_name)
        suite.visit(collector)

        logger.debug("Parsed test names: %s", collector.test_names)
        if collector.test_concurrency and len(collector.test_names) > 0:
            logger.info(
                "%s has been marked to be suitable for test concurrency, will run the tests in parallel",
                robot_file,
            )
            for testcase in collector.test_names:
                self.ordering_entries.append(f"--test {testcase}")
        else:
            # non-refactored suites are run in a single pabot run
            self.ordering_entries.append(f"--suite {collector.full_suite_name}")

    def write(
        self, templates_path: Path, output_path: Path, ordering_file: Path | None = None
    ) -> None:
        """Render Robot test suites."""
        env = Environment(  # nosec B701
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
                        "Skip file with unknown file extension: %s",
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
                except OSError as e:
                    logger.warning(
                        "Could not open/read file: %s - %s", Path(dir, filename), e
                    )
                    continue
                for match in re.finditer(pattern, content):
                    params = match.group().split(" ")
                    if (
                        len(params) == 6
                        and params[1]
                        in [
                            "iterate_list",
                            "iterate_list_folder",
                        ]
                    ) or (len(params) == 8 and params[1] == "iterate_list_chunked"):
                        next_template = True
                        path = params[2].split(".")
                        attr = params[3]
                        elem = self.data
                        for p in path:
                            try:
                                elem = elem.get(p, {})
                            except AttributeError:
                                # corner case with empty data model ('NoneType' object has no attribute 'get')
                                break
                        if not isinstance(elem, list):
                            continue
                        if params[1] == "iterate_list_chunked":
                            # Handle chunked iteration
                            object_path = params[5]
                            chunk_size = int(params[6].rstrip("#}"))
                            for item in elem:
                                attr_value = item.get(attr)
                                if attr_value is None:
                                    continue
                                value = str(attr_value)

                                # Get chunked data using generic method
                                chunked_items = self._chunk_nested_objects(
                                    item, object_path, chunk_size
                                )

                                # Render multiple files for each chunk
                                for chunk_index, chunked_item in enumerate(
                                    chunked_items
                                ):
                                    # Create modified data structure for template
                                    modified_data = copy.deepcopy(self.data)

                                    # Replace the original item with chunked version in the data
                                    item_path = (
                                        path  # This is the path to the items list
                                    )
                                    current_elem = modified_data
                                    for p in item_path[
                                        :-1
                                    ]:  # Navigate to parent of items
                                        current_elem = current_elem.get(p, {})

                                    if item_path[-1] in current_elem and isinstance(
                                        current_elem[item_path[-1]], list
                                    ):
                                        # Find and replace the specific item
                                        items_list = current_elem[item_path[-1]]
                                        for i, item_obj in enumerate(items_list):
                                            if item_obj.get(attr) == attr_value:
                                                items_list[i] = chunked_item
                                                break

                                    # Pass the item name as item[2] (preserving template interface)
                                    extra: dict[str, Any] = {}
                                    if "[" in params[4]:
                                        index = params[4].split("[")[1].split("]")[0]
                                        extra_list: list[Any] = [None] * (
                                            int(index) + 1
                                        )
                                        extra_list[int(index)] = (
                                            value  # Keep as item name string
                                        )
                                        extra = {params[4].split("[")[0]: extra_list}
                                    else:
                                        extra = {
                                            params[4]: value
                                        }  # Keep as item name string

                                    # Generate directory structure like iterate_list (item subdirectories)
                                    o_dir = self._fix_duplicate_path(
                                        str(output_path), rel, value
                                    )

                                    # Generate sequential filenames without item prefix
                                    base_name = os.path.splitext(filename)[0]
                                    extension = os.path.splitext(filename)[1][1:]

                                    # Generate zero-padded sequential filenames: endpoint_group_001.robot, endpoint_group_002.robot
                                    chunk_number = chunk_index + 1
                                    new_filename = (
                                        f"{base_name}_{chunk_number:03d}.{extension}"
                                    )

                                    o_path = Path(o_dir, new_filename)

                                    self.render_template(
                                        t_path,
                                        Path(o_path),
                                        env,
                                        custom_data=modified_data,
                                        **extra,
                                    )
                                    if ordering_file:
                                        self._update_ordering_entries(
                                            output_path, o_path
                                        )
                        else:
                            # Handle regular iteration (existing logic)
                            for item in elem:
                                attr_value = item.get(attr)
                                if attr_value is None:
                                    continue
                                value = str(attr_value)
                                template_extra: dict[str, Any] = {}
                                if "[" in params[4]:
                                    index = params[4].split("[")[1].split("]")[0]
                                    template_extra_list: list[Any] = [None] * (
                                        int(index) + 1
                                    )
                                    template_extra_list[int(index)] = value
                                    template_extra = {
                                        params[4].split("[")[0]: template_extra_list
                                    }
                                else:
                                    template_extra = {params[4]: value}
                                if params[1] == "iterate_list":
                                    o_dir = self._fix_duplicate_path(
                                        str(output_path), rel, value
                                    )
                                    o_path = Path(o_dir, filename)
                                else:  # iterate_list_folder
                                    foldername = os.path.splitext(filename)[0]
                                    new_filename = (
                                        value + "." + os.path.splitext(filename)[1][1:]
                                    )
                                    o_path = self._fix_duplicate_path(
                                        str(output_path), rel, foldername, new_filename
                                    )
                                self.render_template(
                                    t_path, Path(o_path), env, **template_extra
                                )
                                if ordering_file:
                                    self._update_ordering_entries(
                                        output_path, Path(o_path)
                                    )
                if next_template:
                    continue

                o_path = Path(output_path, rel, filename)
                self.render_template(t_path, o_path, env)
                if ordering_file:
                    self._update_ordering_entries(output_path, o_path)

        if ordering_file is None:
            return
        if (
            len(self.ordering_entries) > 0
            # only create ordering file if there is a need for test concurrency
            and any(o.startswith("--test") for o in self.ordering_entries)
        ):
            # sort the entries to keep the order by suite in the same way as robot/pabot would
            self.ordering_entries.sort(key=lambda x: x.split(" ")[1])

            logger.info(f"Creating ordering file: {ordering_file}")
            with open(ordering_file, "w") as file:
                for entry in self.ordering_entries:
                    file.write(f"{entry}\n")
        else:
            # ensure we clean out a leftover ordering file if we don't want testlevelsplit
            ordering_file.unlink(missing_ok=True)
