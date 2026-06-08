# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2012 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.generators.DTBHex8Generator — Intel I8Hex DTB output."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .DTBGenerator2 import DTBGenerator2
from ..lib.bin2ihex import to_hex, HexType, ByteOrder, AddressingMode

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo
    from ..model.system import AvalonSystem


class DTBHex8Generator(DTBGenerator2):
    """
    Encodes the DTB as an Intel I8Hex file.
    Port of sopc2dts.generators.DTBHex8Generator.
    """

    def __init__(self, sys: "AvalonSystem") -> None:
        super().__init__(sys)
        self.generate_text_output = True

    def get_text_output(self, bi: "BoardInfo") -> Optional[str]:
        dtb = self.get_binary_output(bi)
        if dtb is None:
            return None
        return to_hex(dtb, HexType.I8Hex)

    def get_binary_output(self, bi: "BoardInfo") -> Optional[bytes]:  # type: ignore[override]
        return DTBGenerator2.get_binary_output(self, bi)
