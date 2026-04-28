"""
Centralized logging configuration for ECS/CloudWatch-compatible output.

Provides two modes:
- JSON (production): Single-line JSON per log record, parseable by ECS/CloudWatch/Datadog.
- Text (local dev): Human-readable single-line format.

All log sources (app, FastMCP, uvicorn, httpx, MCP SDK) are unified
under one format by configuring the root logger and overriding uvicorn's log config.
"""

import logging
import re
import sys
import time
import traceback
from typing import Any

import orjson

from . import __version__

SERVICE_NAME = "readonly-mcp-akamai"

# Pre-compiled regex to strip ANSI escape codes (e.g. Rich color output).
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

# ESC character for fast pre-check before running regex.
_ESC = "\x1b"


def _format_timestamp(created: float) -> str:
    """Format epoch timestamp as ISO 8601 UTC string.

    Uses time.gmtime() to avoid datetime object allocation.
    """
    t = time.gmtime(created)
    ms = int((created % 1) * 1000)
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{ms:03d}Z"


def _sanitize_message(message: str) -> str:
    """Strip ANSI codes and newlines from a log message.

    Skips expensive operations when the message doesn't need them.
    """
    if _ESC in message:
        message = _ANSI_ESCAPE_RE.sub("", message)
    if "\n" in message:
        message = message.replace("\n", "\\n")
    return message


class JsonFormatter(logging.Formatter):
    """Single-line JSON log formatter for structured log aggregation.

    Fast path (no exception): builds JSON via f-string with orjson.dumps()
    only for the message field (the only value that needs escaping).
    Slow path (exception present): falls back to orjson.dumps(dict).
    """

    def format(self, record: logging.LogRecord) -> str:
        message = _sanitize_message(record.getMessage())
        ts = _format_timestamp(record.created)

        # Fast path: no exception (vast majority of log lines)
        if not (record.exc_info and record.exc_info[1] is not None):
            return (
                f'{{"timestamp":"{ts}"'
                f',"level":"{record.levelname}"'
                f',"logger":"{record.name}"'
                f',"message":{orjson.dumps(message).decode()}'
                f',"service":"{SERVICE_NAME}"'
                f',"version":"{__version__}"}}'
            )

        # Slow path: exception present
        exc_lines = traceback.format_exception(*record.exc_info)
        log_entry: dict[str, Any] = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "service": SERVICE_NAME,
            "version": __version__,
            "exception": exc_lines[-1].strip(),
            "traceback": "\\n".join(exc_lines).replace("\n", "\\n"),
        }
        return orjson.dumps(log_entry, default=str).decode()


class TextFormatter(logging.Formatter):
    """Human-readable single-line formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        message = _sanitize_message(record.getMessage())
        ts = _format_timestamp(record.created)

        line = f"{ts} [{record.levelname}] {record.name}: {message}"

        if record.exc_info and record.exc_info[1] is not None:
            exc_text = "".join(traceback.format_exception(*record.exc_info))
            line += " | " + exc_text.replace("\n", "\\n")

        return line


def configure_logging(
    log_format: str = "text",
    log_level: str = "INFO",
) -> dict[str, Any]:
    """Configure all logging for the application.

    Sets up the root logger so all libraries (httpx, mcp, fastmcp)
    use the same format. Disables FastMCP's Rich logging and returns a uvicorn
    log config dict for passing to mcp.run().

    Args:
        log_format: "json" for structured output, "text" for human-readable.
        log_level: Standard Python log level name.

    Returns:
        A uvicorn-compatible log_config dict to pass via uvicorn_config.
    """
    # Disable FastMCP's Rich logging before it gets configured
    import fastmcp

    fastmcp.settings.log_enabled = False

    # Choose formatter
    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter()

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(log_level.upper())

    # Remove any existing handlers (including basicConfig defaults)
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Single handler on root, writing to stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Reconfigure fastmcp logger: remove Rich handlers, propagate to root
    fastmcp_logger = logging.getLogger("fastmcp")
    for h in fastmcp_logger.handlers[:]:
        fastmcp_logger.removeHandler(h)
    fastmcp_logger.propagate = True

    # Build uvicorn log config that uses our formatter class
    formatter_class = (
        "mcp_akamai.logging_config.JsonFormatter" if log_format == "json" else "mcp_akamai.logging_config.TextFormatter"
    )
    uvicorn_log_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"()": formatter_class},
            "access": {"()": formatter_class},
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": log_level.upper(),
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": log_level.upper(),
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": log_level.upper(),
                "propagate": False,
            },
        },
    }

    return uvicorn_log_config
