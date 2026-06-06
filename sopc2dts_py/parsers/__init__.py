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

Public API
----------
:func:`load_system`
    Parse a ``.sopcinfo`` or ``.qsys`` file → :class:`AvalonSystem`.

:func:`load_boardinfo`
    Parse a boardinfo XML file → :class:`BoardInfo`.

:func:`load_component_lib`
    Load one ``sopc_components_*.xml`` into a :class:`SopcComponentLib`.

:func:`load_component_libs_in_dir`
    Load all ``sopc_components_*.xml`` files in a directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo
    from ..model.component_lib import SopcComponentLib
    from ..model.system import AvalonSystem


def load_system(path: "str | Path") -> "AvalonSystem":
    """
    Parse *path* and return an :class:`~sopc2dts_py.model.system.AvalonSystem`.

    Dispatches by file extension:

    - ``.sopcinfo`` / ``.jdi`` → :mod:`sopc2dts_py.parsers.sopcinfo`
    - ``.qsys``                → :mod:`sopc2dts_py.parsers.qsys`

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


def load_boardinfo(source: "str | Path") -> "BoardInfo":
    """
    Parse a boardinfo XML file and return a
    :class:`~sopc2dts_py.model.boardinfo.BoardInfo`.

    Delegates to :func:`sopc2dts_py.parsers.boardinfo_xml.load_boardinfo`.
    """
    from .boardinfo_xml import load_boardinfo as _load
    return _load(source)


def load_component_lib(
    path: "str | Path",
    lib: "Optional[SopcComponentLib]" = None,
) -> "SopcComponentLib":
    """
    Load one ``sopc_components_*.xml`` file into a component library.

    Delegates to :func:`sopc2dts_py.parsers.component_xml.load_component_lib`.
    """
    from .component_xml import load_component_lib as _load
    return _load(path, lib)


def load_component_libs_in_dir(
    directory: "str | Path",
    lib: "Optional[SopcComponentLib]" = None,
) -> "SopcComponentLib":
    """
    Load all ``sopc_components_*.xml`` files in *directory*.

    Delegates to
    :func:`sopc2dts_py.parsers.component_xml.load_component_libs_in_dir`.
    """
    from .component_xml import load_component_libs_in_dir as _load
    return _load(directory, lib)
