# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Validation for extra Robot Framework arguments passed via -- separator.

This module validates arguments passed after the -- separator to ensure they are
valid Robot Framework options that don't conflict with nac-test's controlled options.
"""

import functools
import logging
import uuid
from collections.abc import Callable
from typing import Any

from robot.errors import DataError

from nac_test.core.types import ValidatedRobotArgs
from nac_test.utils.strings import parse_cli_option_name

logger = logging.getLogger(__name__)

# Import pabot's parse_args if available. Aliased with a leading underscore to
# prevent it leaking as a re-exportable name from this module's namespace.
# If pabot's parse_args API changes, validation is skipped gracefully.
_pabot_parse_args: Callable[..., tuple[Any, ...]] | None = None
try:
    from pabot.arguments import parse_args

    _pabot_parse_args = parse_args
except ImportError:
    logger.warning(
        "pabot.arguments.parse_args not available, skipping pabot argument validation"
    )

# Robot Framework options controlled by nac-test: (long_option, short_option, hint)
# Each tuple is the single source of truth — the lookup below is derived from this.
_CONTROLLED_ROBOT_OPTIONS: list[tuple[str, str | None, str]] = [
    ("include", "i", "nac-test -i/--include"),
    ("exclude", "e", "nac-test -e/--exclude"),
    ("outputdir", "d", "nac-test -o/--output"),
    ("output", "o", "controlled internally by nac-test"),
    ("log", "l", "controlled internally by nac-test"),
    ("report", "r", "controlled internally by nac-test"),
    ("xunit", "x", "controlled internally by nac-test"),
    ("dryrun", None, "nac-test --dry-run"),
    # --loglevel / -L is intentionally absent: users may override it via extra_args
    # (e.g. "-- --loglevel TRACE"). nac-test sets a default but does not own the option.
]

_CONTROLLED_OPTIONS_LOOKUP: dict[str, str] = {
    k: hint
    for long, short, hint in _CONTROLLED_ROBOT_OPTIONS
    for k in ([long, short] if short else [long])
}

# pabot's parse_args requires at least one datasource argument. Using a UUID-based
# name ensures this sentinel can never collide with a real user test file.
_DUMMY_DATASOURCE = f"__nac_test_{uuid.uuid4().hex}__.robot"


@functools.cache
def _get_pabot_option_names() -> frozenset[str]:
    """Return pabot option names derived from pabot's own parser (computed once, cached).

    Deferred to first call so the pabot parser is never invoked when extra args
    are not used (the common case).  result[2] of parse_args is the pabot args
    dict; its keys are the canonical option names.
    """
    if _pabot_parse_args is None:
        return frozenset()
    return frozenset(_pabot_parse_args([_DUMMY_DATASOURCE])[2].keys())


def _raise_if_controlled_robot_options(extra_args: list[str]) -> None:
    """Raise ValueError if any nac-test controlled Robot options are in extra_args.

    Raises:
        ValueError: If any controlled options are found in extra_args.
    """
    controlled = []

    for arg in extra_args:
        if arg.startswith("--"):
            key = parse_cli_option_name(arg).lower()
        elif arg.startswith("-") and len(arg) == 2:
            key = arg[1]  # short options are case-sensitive (-i != -I)
        else:
            continue

        hint = _CONTROLLED_OPTIONS_LOOKUP.get(key)
        if hint:
            controlled.append((arg, hint))

    if controlled:
        options_with_hints = [f"{opt} (use {hint})" for opt, hint in controlled]
        error_msg = (
            f"Robot Framework options controlled by nac-test cannot be passed via "
            f"extra arguments: {', '.join(options_with_hints)}"
        )
        logger.debug(error_msg)
        raise ValueError(error_msg)


def _raise_if_pabot_options(extra_args: list[str]) -> None:
    """Raise ValueError if any pabot-specific options are in extra_args.

    Raises:
        ValueError: If any pabot-specific options are found.
    """
    pabot_options_found = [
        arg
        for arg in extra_args
        if arg.startswith("--")
        and parse_cli_option_name(arg).lower() in _get_pabot_option_names()
    ]

    if pabot_options_found:
        error_msg = (
            f"Pabot-specific arguments are not allowed in extra arguments: "
            f"{', '.join(pabot_options_found)}. Only Robot Framework options are accepted."
        )
        logger.debug(error_msg)
        raise ValueError(error_msg)


def _raise_if_datasources(datasources: list[str]) -> None:
    """Raise ValueError if any datasources (test files/directories) were provided.

    Raises:
        ValueError: If any actual datasources are found (excludes dummy).
    """
    actual_datasources = [ds for ds in datasources if ds != _DUMMY_DATASOURCE]
    if actual_datasources:
        error_msg = (
            f"Datasources/files are not allowed in extra arguments: "
            f"{', '.join(actual_datasources)}"
        )
        logger.debug(error_msg)
        raise ValueError(error_msg)


def validate_extra_args(extra_args: list[str]) -> ValidatedRobotArgs:
    """Validate extra Robot Framework arguments passed after the -- separator.

    Returns a ValidatedRobotArgs with the raw arg list and the parsed Robot opts
    dict from pabot's parser. Callers should pass this object through the
    orchestration chain instead of the raw string list, so that downstream
    consumers (e.g. run_pabot) can inspect parsed option values without
    re-parsing.

    Raises:
        ValueError: If extra_args contain datasources/files, pabot options, or
            Robot options controlled by nac-test.
        DataError: If extra_args contain invalid Robot Framework arguments.
    """
    if not extra_args:
        return ValidatedRobotArgs(args=[], robot_opts={})

    _raise_if_controlled_robot_options(extra_args)
    _raise_if_pabot_options(extra_args)

    if _pabot_parse_args is None:
        return ValidatedRobotArgs(args=extra_args, robot_opts={})

    # Use pabot's parse_args as the authoritative Robot argument validator.
    try:
        robot_opts, datasources, _, _ = _pabot_parse_args(
            extra_args + [_DUMMY_DATASOURCE]
        )
    except DataError:
        # Unknown robotframework arguments
        raise
    except (IndexError, TypeError) as e:
        logger.warning(f"pabot API may have changed, skipping validation: {e}")
        return ValidatedRobotArgs(args=extra_args, robot_opts={})

    _raise_if_datasources(datasources)
    return ValidatedRobotArgs(args=extra_args, robot_opts=robot_opts)
