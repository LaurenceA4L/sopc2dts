# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Logging subsystem — replaces Logger / LogListener / LogEntry from the Java tool.

The Java tool used a custom listener pattern. Here we wrap Python's stdlib
logging so the rest of the codebase calls the same simple API, but the GUI
can attach its own handler (e.g. an SSE queue) alongside stderr output.
"""

import logging
import sys
from typing import Optional

# Mirror Java log levels onto Python logging levels
LEVEL_MAP = {
    "ERROR":   logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO":    logging.INFO,
    "DEBUG":   logging.DEBUG,
}

# Module-level logger — all sopc2dts code uses this
logger = logging.getLogger("sopc2dts")


def setup_logging(verbose_count: int = 0, stream=sys.stderr) -> None:
    """Configure root handler based on -v count (0=WARNING, 1=INFO, 2+=DEBUG)."""
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[min(verbose_count, len(levels) - 1)]
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)


def add_handler(handler: logging.Handler) -> None:
    """Attach an extra handler (e.g. GUI SSE queue) to the sopc2dts logger."""
    logger.addHandler(handler)


def remove_handler(handler: logging.Handler) -> None:
    logger.removeHandler(handler)
