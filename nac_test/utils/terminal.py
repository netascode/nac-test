"""Centralized terminal formatting utilities for nac-test."""

from colorama import Fore, Style, init
import os
import re

# autoreset=True means colors reset after each print
init(autoreset=True)


class TerminalColors:
    """Centralized color scheme for consistent terminal output.

    This class provides semantic color mappings and formatting methods
    to ensure consistent terminal output across the nac-test codebase.
    """

    # Semantic color mapping for different message types
    ERROR = Fore.RED
    WARNING = Fore.YELLOW
    SUCCESS = Fore.GREEN
    INFO = Fore.CYAN
    HIGHLIGHT = Fore.MAGENTA
    RESET = Style.RESET_ALL

    # Semantic styles
    BOLD = Style.BRIGHT
    DIM = Style.DIM

    # Check if colors should be disabled (for CI/CD environments)
    NO_COLOR = os.environ.get("NO_COLOR") is not None

    # Regex pattern to match ANSI escape sequences
    ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

    @classmethod
    def strip_ansi(cls, text: str) -> str:
        """Remove all ANSI escape sequences from text.

        Args:
            text: Text potentially containing ANSI color codes

        Returns:
            Clean text without any ANSI escape sequences
        """
        return cls.ANSI_ESCAPE_PATTERN.sub("", text)

    @classmethod
    def error(cls, text: str) -> str:
        """Format error text in red."""
        if cls.NO_COLOR:
            return text
        return f"{cls.ERROR}{text}{cls.RESET}"

    @classmethod
    def warning(cls, text: str) -> str:
        """Format warning text in yellow."""
        if cls.NO_COLOR:
            return text
        return f"{cls.WARNING}{text}{cls.RESET}"

    @classmethod
    def success(cls, text: str) -> str:
        """Format success text in green."""
        if cls.NO_COLOR:
            return text
        return f"{cls.SUCCESS}{text}{cls.RESET}"

    @classmethod
    def info(cls, text: str) -> str:
        """Format info text in cyan."""
        if cls.NO_COLOR:
            return text
        return f"{cls.INFO}{text}{cls.RESET}"

    @classmethod
    def highlight(cls, text: str) -> str:
        """Format highlighted text in magenta."""
        if cls.NO_COLOR:
            return text
        return f"{cls.HIGHLIGHT}{text}{cls.RESET}"

    @classmethod
    def bold(cls, text: str) -> str:
        """Format text in bold."""
        if cls.NO_COLOR:
            return text
        return f"{cls.BOLD}{text}{cls.RESET}"

    @classmethod
    def header(cls, text: str, width: int = 70, char: str = "=") -> str:
        """Format a header with separators.

        Args:
            text: Header text to display
            width: Width of separator line
            char: Character to use for separator

        Returns:
            Formatted header string with separators
        """
        if cls.NO_COLOR:
            separator = char * width
            return f"{separator}\n{text}\n{separator}"

        separator = char * width
        return f"{cls.ERROR}{separator}{cls.RESET}\n{cls.ERROR}{text}{cls.RESET}\n{cls.ERROR}{separator}{cls.RESET}"

    @classmethod
    def format_env_var_error(
        cls, missing_vars: list[str], controller_type: str = "ACI"
    ) -> str:
        """Format an informative error message for missing environment variables.

        Generates a generic, architecture-agnostic error message that educates
        users about the CONTROLLER_TYPE mechanism and provides examples for all
        supported architectures.

        Args:
            missing_vars: List of missing environment variable names
            controller_type: Current controller type being validated

        Returns:
            Formatted error message with ANSI color codes for terminal display
        """
        # Determine if this is the default value or explicitly set
        is_default = os.environ.get("CONTROLLER_TYPE") is None

        lines = []
        lines.append(cls.header("ERROR: Missing required environment variable(s)"))

        # Show the missing variables
        for var in missing_vars:
            lines.append(f"  {cls.warning('•')} {cls.warning(var)}")

        lines.append("")

        # Explain CONTROLLER_TYPE mechanism
        if is_default:
            lines.append(
                cls.info(
                    "The CONTROLLER_TYPE environment variable determines which credentials"
                )
            )
            lines.append(
                cls.info(f'are required. Current value: "{controller_type}" (default)')
            )
        else:
            lines.append(
                cls.info(
                    f'The CONTROLLER_TYPE environment variable is set to: "{controller_type}"'
                )
            )

        lines.append("")
        lines.append(
            cls.info("To use a different architecture, set CONTROLLER_TYPE first:")
        )
        lines.append(
            f"  {cls.success('export CONTROLLER_TYPE=ACI')}     {cls.info('# for ACI (APIC)')}"
        )
        lines.append(
            f"  {cls.success('export CONTROLLER_TYPE=SDWAN')}   {cls.info('# for SD-WAN (vManage)')}"
        )
        lines.append(
            f"  {cls.success('export CONTROLLER_TYPE=CC')}      {cls.info('# for Catalyst Center')}"
        )
        lines.append(
            f"  {cls.success('export CONTROLLER_TYPE=MERAKI')}  {cls.info('# for Meraki Dashboard')}"
        )
        lines.append(
            f"  {cls.success('export CONTROLLER_TYPE=FMC')}     {cls.info('# for Firepower Management Center')}"
        )
        lines.append(
            f"  {cls.success('export CONTROLLER_TYPE=ISE')}     {cls.info('# for Identity Services Engine')}"
        )

        lines.append("")
        lines.append(cls.info("Then set the corresponding credentials:"))
        lines.append("")

        # Architecture-specific examples with helpful URLs
        architecture_examples = [
            ("ACI", "apic.example.com", "ACI (APIC)"),
            ("SDWAN", "vmanage.example.com", "SD-WAN (vManage)"),
            ("CC", "cc.example.com", "Catalyst Center"),
            ("MERAKI", "api.meraki.com/api/v1", "Meraki"),
            ("FMC", "fmc.example.com", "Firepower MC"),
            ("ISE", "ise.example.com", "ISE"),
        ]

        for arch, url, friendly_name in architecture_examples:
            # Pre-compute strings to avoid nested f-string backslash limitation
            url_cmd = f"export {arch}_URL='https://{url}'"
            user_cmd = f"export {arch}_USERNAME='admin'"
            pass_cmd = f"export {arch}_PASSWORD='your-password'"
            lines.append(f"  {cls.highlight(friendly_name + ':')}")
            lines.append(f"    {cls.success(url_cmd)}")
            lines.append(f"    {cls.success(user_cmd)}")
            lines.append(f"    {cls.success(pass_cmd)}")
            lines.append("")

        lines.append(cls.error("=" * 70))

        return "\n".join(lines)


# Single instance for use across the codebase
terminal = TerminalColors()
