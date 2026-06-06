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
sopc2dts_py.parsers — input file parsers.

Dispatch helper
---------------
Use :func:`load_system` to parse any supported input file; it inspects the
file extension and routes to the appropriate parser.

Supported formats
-----------------
- ``.sopcinfo`` / ``.jdi`` — Altera SOPC Builder / Qsys platform report
- ``.qsys``                — Platform Designer hierarchical design file
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..model.system import AvalonSystem


def load_system(path: "str | Path") -> "AvalonSystem":
    """
    Parse *path* and return an :class:`~sopc2dts_py.model.system.AvalonSystem`.

    Dispatches by file extension:

    - ``.sopcinfo`` / ``.jdi`` → :func:`sopc2dts_py.parsers.sopcinfo.load_system`
    - ``.qsys``                → :func:`sopc2dts_py.parsers.qsys.load_system`

    Mirrors ``BasicSystemLoader.getSystemFromFile`` in the Java tool.
    """
    path = Path(path)
    ext = path.suffix.lower()

    if ext in (".sopcinfo", ".jdi"):
        from .sopcinfo import load_system as _load
        return _load(path)
    elif ext == ".qsys":
        from .qsys import load_system as _load
        return _load(path)
    else:
        raise ValueError(
            f"Unrecognised input format '{ext}'. "
            "Expected .sopcinfo, .jdi, or .qsys."
        )
