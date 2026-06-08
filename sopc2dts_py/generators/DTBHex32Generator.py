# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2012 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.generators.DTBHex32Generator — Intel I32Hex DTB output."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .AbstractSopcGenerator import AbstractSopcGenerator
from .DTBGenerator2 import DTBGenerator2
from ..lib.bin2ihex import to_hex, HexType, ByteOrder, AddressingMode

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo
    from ..model.system import AvalonSystem


class DTBHex32Generator(AbstractSopcGenerator):
    """
    Encodes the DTB as an Intel I32Hex file (32-bit addressing, little-endian words).
    Port of sopc2dts.generators.DTBHex32Generator.
    """

    def __init__(self, sys: "AvalonSystem") -> None:
        super().__init__(sys, is_text=True)
        self._dtb_gen = DTBGenerator2(sys)

    def get_text_output(self, bi: "BoardInfo") -> Optional[str]:
        dtb = self._dtb_gen.get_binary_output(bi)
        if dtb is None:
            return None
        return to_hex(
            dtb,
            HexType.I32Hex,
            ByteOrder.LE,
            addr_mode=AddressingMode.AddrMode32,
        )
