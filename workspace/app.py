"""Proof-of-concept: Typer CLI with standard Python log levels."""

import logging
from enum import Enum

import typer


# StrEnum (str + Enum) makes Typer show the names (DEBUG, INFO, …) in --help.
# We add comparison helpers so the rest of the code can use <= and == naturally.
class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def _int(self) -> int:
        return logging._nameToLevel[self.value]

    # Ordering: current_loglevel <= LogLevel.DEBUG
    def __le__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        return self._int <= other._int

    def __lt__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        return self._int < other._int

    def __ge__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        return self._int >= other._int

    def __gt__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        return self._int > other._int

    # Equality already works via Enum (same member identity / same .value).


DEFAULT_LOGLEVEL: LogLevel = LogLevel.INFO

app = typer.Typer()


@app.command()
def main(
    loglevel: LogLevel = typer.Option(
        DEFAULT_LOGLEVEL,
        "--loglevel",
        help="Log level for the application.",
        show_default=True,
    ),
    verbosity: LogLevel = typer.Option(
        None,
        "--verbosity",
        hidden=True,  # omitted from --help
    ),
) -> None:
    """Demo application showing log level comparisons."""
    if verbosity is not None:
        typer.echo("Warning: --verbosity is deprecated, use --loglevel instead.", err=True)
        loglevel = verbosity
    logging.basicConfig(level=logging._nameToLevel[loglevel.value])
    logger = logging.getLogger(__name__)

    logger.info("Application started with loglevel=%s", loglevel.value)

    # Comparison: <= works via overridden __le__
    if loglevel <= LogLevel.DEBUG:
        print(f"Verbose debug mode active (loglevel={loglevel.value})")

    # Equality via standard Enum identity
    if loglevel == LogLevel.INFO:
        print("Running at default INFO level.")

    if loglevel != DEFAULT_LOGLEVEL:
        print(f"Non-default loglevel selected: {loglevel.value}")
    else:
        print(f"Using default loglevel: {loglevel.value}")


if __name__ == "__main__":
    app()
