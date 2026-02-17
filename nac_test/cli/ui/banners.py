# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Terminal banner components for CLI error display.

This module provides styled terminal banners for displaying prominent
error messages to users. Supports both Unicode (interactive terminals)
and ASCII (NO_COLOR/CI environments) output modes.
"""

from dataclasses import dataclass

import typer

from nac_test.utils.controller import get_display_name
from nac_test.utils.terminal import TerminalColors
from nac_test.utils.url import extract_host

# Type alias for typer color values
ColorValue = str | int | tuple[int, int, int]

# Banner display settings
BANNER_CONTENT_WIDTH: int = (
    78  # Leaves room for 2-char border within 80-column terminal
)
EMOJI_DISPLAY_WIDTH_ADJUSTMENT: int = (
    2  # Emojis display as 2 chars wide but len() returns 1
)


@dataclass(frozen=True)
class BoxStyle:
    """Terminal box-drawing style configuration.

    Attributes:
        top_left: Top-left corner character.
        top_right: Top-right corner character.
        bottom_left: Bottom-left corner character.
        bottom_right: Bottom-right corner character.
        horizontal: Horizontal line character.
        vertical: Vertical line character.
        mid_left: Middle-left junction character.
        mid_right: Middle-right junction character.
        emoji_adjustment: Width adjustment for emoji characters (0 for ASCII, 2 for Unicode).
    """

    top_left: str
    top_right: str
    bottom_left: str
    bottom_right: str
    horizontal: str
    vertical: str
    mid_left: str
    mid_right: str
    emoji_adjustment: int


# Pre-defined box styles
ASCII_BOX_STYLE = BoxStyle(
    top_left="+",
    top_right="+",
    bottom_left="+",
    bottom_right="+",
    horizontal="=",
    vertical="|",
    mid_left="+",
    mid_right="+",
    emoji_adjustment=0,
)

UNICODE_BOX_STYLE = BoxStyle(
    top_left="╔",
    top_right="╗",
    bottom_left="╚",
    bottom_right="╝",
    horizontal="═",
    vertical="║",
    mid_left="╠",
    mid_right="╣",
    emoji_adjustment=EMOJI_DISPLAY_WIDTH_ADJUSTMENT,
)


def _get_box_style(no_color: bool) -> BoxStyle:
    """Return ASCII or Unicode box style based on color mode."""
    return ASCII_BOX_STYLE if no_color else UNICODE_BOX_STYLE


def _build_bordered_line(content: str, width: int, style: BoxStyle) -> str:
    """Wrap content string with vertical border characters.

    Args:
        content: The text content to wrap.
        width: The inner width (content area).
        style: The box style to use.

    Returns:
        A string with the content padded and wrapped in vertical borders.
    """
    padded = content + " " * (width - len(content))
    return style.vertical + padded + style.vertical


def _build_title_line(title: str, width: int, style: BoxStyle) -> str:
    """Center title accounting for emoji display width adjustment.

    Args:
        title: The title text.
        width: The inner width (content area).
        style: The box style to use (for emoji adjustment).

    Returns:
        A string with the title centered and wrapped in vertical borders.
    """
    title_display_width = len(title) + style.emoji_adjustment
    title_padding = (width - title_display_width) // 2
    remaining = width - title_padding - title_display_width
    return (
        style.vertical + " " * title_padding + title + " " * remaining + style.vertical
    )


def _render_banner(
    title: str,
    content_lines: list[str],
    border_color: ColorValue = typer.colors.RED,
    text_color: ColorValue = typer.colors.WHITE,
) -> None:
    """Render a styled terminal banner with box borders.

    Handles both Unicode (colored) and ASCII (NO_COLOR) rendering modes.
    All public banner functions should delegate to this to avoid duplication.

    Args:
        title: The banner title text. For Unicode mode, can include emoji.
        content_lines: List of content strings (one per line inside the box).
        border_color: Typer color for borders in color mode.
        text_color: Typer color for content text in color mode.
    """
    width = BANNER_CONTENT_WIDTH
    no_color = TerminalColors.NO_COLOR
    style = _get_box_style(no_color)

    # Build borders
    h_border = style.horizontal * width
    top_border = style.top_left + h_border + style.top_right
    separator = style.mid_left + h_border + style.mid_right
    bottom_border = style.bottom_left + h_border + style.bottom_right
    title_line = _build_title_line(title, width, style)

    bordered_content = [
        _build_bordered_line(line, width, style) for line in content_lines
    ]

    if no_color:
        typer.echo(top_border)
        typer.echo(title_line)
        typer.echo(separator)
        for line in bordered_content:
            typer.echo(line)
        typer.echo(bottom_border)
    else:
        typer.echo(typer.style(top_border, fg=border_color))
        typer.echo(typer.style(title_line, fg=border_color))
        typer.echo(typer.style(separator, fg=border_color))
        for line in bordered_content:
            typer.echo(
                typer.style(style.vertical, fg=border_color)
                + typer.style(line[1:-1], fg=text_color)
                + typer.style(style.vertical, fg=border_color)
            )
        typer.echo(typer.style(bottom_border, fg=border_color))


def display_aci_defaults_banner() -> None:
    """Display a prominent banner when ACI defaults file is missing.

    Uses Unicode box-drawing characters and ANSI colors by default for a
    visually prominent error display. Falls back to ASCII characters and
    plain text when NO_COLOR environment variable is set, ensuring
    compatibility with CI/CD environments and accessibility tools.

    Note:
        Requires UTF-8 terminal support for Unicode box-drawing characters.
        Set NO_COLOR=1 environment variable to use ASCII fallback.
    """
    no_color = TerminalColors.NO_COLOR
    title = (
        "!!! DEFAULTS FILE REQUIRED FOR ACI !!!"
        if no_color
        else "🛑 DEFAULTS FILE REQUIRED FOR ACI 🛑"
    )
    content_lines = [
        "",
        "Cisco's ACI as Code (AaC) requires the defaults file for proper test",
        "execution. The defaults file contains required configuration values.",
        "",
        "Please add the defaults directory to your command. Example:",
        "",
        "  nac-test -d ./data -d ./defaults/ -t ./tests/ -o ./output",
        "",
    ]
    _render_banner(title, content_lines)


def display_auth_failure_banner(
    controller_type: str,
    controller_url: str,
    detail: str,
    env_var_prefix: str,
) -> None:
    """Display a prominent banner when controller authentication fails.

    This banner is shown when the pre-flight auth check fails due to invalid
    credentials (HTTP 401/403). It provides remediation steps including the
    environment variable names to check.

    Args:
        controller_type: The controller type string (e.g., "ACI", "SDWAN", "CC").
        controller_url: The URL that was attempted.
        detail: Human-readable error detail (e.g., "HTTP 401: Unauthorized").
        env_var_prefix: The environment variable prefix (e.g., "ACI", "SDWAN", "CC").

    Note:
        Uses the same box style and color handling as display_aci_defaults_banner.
    """
    display_name = get_display_name(controller_type)
    no_color = TerminalColors.NO_COLOR
    title = (
        "!!! CONTROLLER AUTHENTICATION FAILED !!!"
        if no_color
        else "⛔ CONTROLLER AUTHENTICATION FAILED"
    )
    content_lines = [
        "",
        f"Could not authenticate to {display_name} at {controller_url}",
        f"{detail}",
        "",
        "Verify your credentials:",
        f"  export {env_var_prefix}_USERNAME=<username>",
        f"  export {env_var_prefix}_PASSWORD=<password>",
        "",
    ]
    _render_banner(title, content_lines)


def display_unreachable_banner(
    controller_type: str,
    controller_url: str,
    detail: str,
) -> None:
    """Display a prominent banner when controller is unreachable.

    This banner is shown when the pre-flight auth check fails due to the
    controller being unreachable (connection timeout, connection refused, etc.).
    It provides connectivity debugging steps.

    Args:
        controller_type: The controller type string (e.g., "ACI", "SDWAN", "CC").
        controller_url: The URL that was attempted.
        detail: Human-readable error detail (e.g., "Connection timed out").

    Note:
        Uses the same box style and color handling as display_aci_defaults_banner.
    """
    display_name = get_display_name(controller_type)
    host = extract_host(controller_url)
    no_color = TerminalColors.NO_COLOR
    title = (
        "!!! CONTROLLER UNREACHABLE !!!" if no_color else "⛔ CONTROLLER UNREACHABLE"
    )
    content_lines = [
        "",
        f"Could not connect to {display_name} at {controller_url}",
        f"{detail}",
        "",
        "Verify the controller is reachable and the URL is correct:",
        f"  curl -k {controller_url}",
        f"  ping {host}",
        "",
    ]
    _render_banner(title, content_lines)
