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
Port of sopc2dts.generators.DTSGenerator2 — produces a .dts text file.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .DTGenerator import DTGenerator

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo


class DTSGenerator2(DTGenerator):
    """
    DTS text generator.
    Port of sopc2dts.generators.DTSGenerator2.
    """

    def __init__(self, sys) -> None:
        super().__init__(sys, is_text=True)

    def get_text_output(self, bi: "BoardInfo") -> Optional[str]:
        """Port of DTSGenerator2.getTextOutput."""
        return (
            self.get_small_copyright_notice("devicetree", bi.is_include_time())
            + "/dts-v1/;\n"
            + self.get_dt_output(bi).to_string(0)
        )
