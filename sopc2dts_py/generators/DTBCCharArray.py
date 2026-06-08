# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.generators.DTBCCharArray — DTB as a C unsigned char array."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .AbstractSopcGenerator import AbstractSopcGenerator
from .DTBGenerator2 import DTBGenerator2

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo
    from ..model.system import AvalonSystem


class DTBCCharArray(AbstractSopcGenerator):
    """
    Emits the DTB as a C unsigned char array literal.
    Port of sopc2dts.generators.DTBCCharArray.
    """

    ENTRIES_PER_LINE = 12

    def __init__(self, sys: "AvalonSystem") -> None:
        super().__init__(sys, is_text=True)
        self._dtb_gen = DTBGenerator2(sys)

    def get_text_output(self, bi: "BoardInfo") -> Optional[str]:
        dtb = self._dtb_gen.get_binary_output(bi)
        if dtb is None:
            return None

        epl = self.ENTRIES_PER_LINE
        res = "unsigned char dtbData[] = {\n"
        for i, byte in enumerate(dtb):
            res += "\t" if (i % epl == 0) else " "
            res += f"0x{byte:02X},"
            if i % epl == (epl - 1):
                res += "\n"
        if len(dtb) % epl != 0:
            res += "\n"
        res += "};\n"
        return res
