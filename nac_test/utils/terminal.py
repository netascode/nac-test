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
        """Format a nice error message for missing environment variables.

        Args:
            missing_vars: List of missing environment variable names
            controller_type: Type of controller (ACI, SSH, etc.)

        Returns:
            Formatted error message with ANSI color codes for terminal display
        """
        lines = []
        lines.append(
            cls.header(f"ERROR: Missing {controller_type} environment variable(s)")
        )

        for var in missing_vars:
            lines.append(f"  {cls.warning('•')} {cls.warning(var)}")

        lines.append("")
        lines.append(
            cls.info(
                f"Please set the required {controller_type} environment variables before running tests."
            )
        )
        lines.append(cls.info("Example:"))

        # Provide helpful examples based on variable names and controller type
        for var in missing_vars:
            if var.endswith("_URL"):
                if controller_type == "ACI":
                    example = f"export {var}='https://your-apic-controller.example.com'"
                # elif controller_type == "SSH":
                #     example = f"export {var}='ssh://device.example.com:22'"
                else:
                    example = f"export {var}='https://your-controller-url'"
            elif var.endswith("_USERNAME"):
                example = f"export {var}='your-username'"
            elif var.endswith("_PASSWORD"):
                example = f"export {var}='your-password'"
            # elif var.endswith("_KEY_FILE"):
            #     example = f"export {var}='/path/to/ssh/key'"
            # elif var.endswith("_PORT"):
            #     example = f"export {var}='22'"
            else:
                example = f"export {var}='your-value'"

            lines.append(f"  {cls.success(example)}")

        lines.append(cls.error("=" * 70))

        return "\n".join(lines)


# Single instance for use across the codebase
terminal = TerminalColors()
