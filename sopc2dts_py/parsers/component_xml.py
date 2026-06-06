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
Parser facade for component library XML files (``sopc_components_*.xml``).

The actual parsing logic lives in
:mod:`sopc2dts_py.model.component_lib`
(:class:`~sopc2dts_py.model.component_lib.SopcComponentLib`).  This module
exposes ``load_component_lib`` and ``load_component_libs_in_dir`` so callers
can load extra component libraries without touching the singleton directly.

Mirrors ``sopc2dts.lib.SopcComponentLib.loadComponentLib`` /
``loadComponentLibsInWorkDir`` from the Java tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..model.component_lib import SopcComponentLib


def load_component_lib(
    path: "str | Path",
    lib: Optional[SopcComponentLib] = None,
) -> SopcComponentLib:
    """
    Load one ``sopc_components_*.xml`` file into a component library.

    Parameters
    ----------
    path:
        Path to the component library XML file.
    lib:
        Library instance to load into.  Defaults to the process-wide
        singleton (:meth:`SopcComponentLib.get_instance`).

    Returns
    -------
    SopcComponentLib
        The (now-populated) library that was passed in or the singleton.
    """
    target = lib if lib is not None else SopcComponentLib.get_instance()
    target.load_component_lib(Path(path))
    return target


def load_component_libs_in_dir(
    directory: "str | Path",
    lib: Optional[SopcComponentLib] = None,
) -> SopcComponentLib:
    """
    Scan *directory* for ``sopc_components_*.xml`` files and load each one.

    Parameters
    ----------
    directory:
        Directory to scan.
    lib:
        Library instance to load into.  Defaults to the process-wide
        singleton (:meth:`SopcComponentLib.get_instance`).

    Returns
    -------
    SopcComponentLib
        The (now-populated) library.
    """
    target = lib if lib is not None else SopcComponentLib.get_instance()
    target.load_component_libs_in_dir(Path(directory))
    return target
