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
Parser facade for boardinfo XML files.

The actual parsing logic lives in :mod:`sopc2dts_py.model.boardinfo`
(:class:`~sopc2dts_py.model.boardinfo.BoardInfo`).  This module exposes a
``load_boardinfo`` function so the parsers package presents a uniform
interface regardless of format.

Mirrors ``sopc2dts.lib.BoardInfo.load`` / ``BoardInfo.fromFile`` from the
Java tool, accessed through the parsers layer.
"""

from __future__ import annotations

from pathlib import Path

from ..model.boardinfo import BoardInfo


def load_boardinfo(source: "str | Path") -> BoardInfo:
    """
    Parse a boardinfo XML file and return a populated
    :class:`~sopc2dts_py.model.boardinfo.BoardInfo` instance.

    Parameters
    ----------
    source:
        Path to the boardinfo XML file (e.g. ``boardinfo_neek.xml``).

    Returns
    -------
    BoardInfo
        Fully populated board-overlay model.

    Raises
    ------
    xml.etree.ElementTree.ParseError
        If the file is not valid XML.
    OSError
        If the file cannot be read.
    """
    return BoardInfo.from_file(Path(source))
