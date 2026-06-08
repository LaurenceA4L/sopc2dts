# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.hps.SocFpgaPeripClock."""

from __future__ import annotations

from typing import List, Optional

from ....model.component import SopcComponentDescription
from .VirtualClockElement import VirtualClockElement


class SocFpgaPeripClock(VirtualClockElement):
    """
    A peripheral clock node in the HPS clock tree.
    Port of sopc2dts.lib.components.altera.hps.SocFpgaPeripClock.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: Optional[str],
        scd: SopcComponentDescription,
        reg: Optional[int] = None,
        fixed_divider: Optional[int] = None,
        div_reg: Optional[List[int]] = None,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd, reg)
        self._fixed_divider: Optional[int] = fixed_divider
        self._div_reg: Optional[List[int]] = div_reg

    # ------------------------------------------------------------------
    # Phase 2 stub
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: object) -> object:
        raise NotImplementedError("SocFpgaPeripClock.to_dt_node — Phase 2")
