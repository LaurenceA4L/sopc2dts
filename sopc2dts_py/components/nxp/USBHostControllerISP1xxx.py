# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2012 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.nxp.USBHostControllerISP1xxx."""

from __future__ import annotations

from typing import List, Optional

from ...model.component import BasicComponent, SopcComponentDescription


class USBHostControllerISP1xxx(BasicComponent):
    """
    NXP ISP1xxx USB host controller.
    Overrides reg computation to emit two (addr, size=4) pairs per
    memory-slave interface — one for data, one for the +4 offset address register.
    Port of sopc2dts.lib.components.nxp.USBHostControllerISP1xxx.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: Optional[str],
        scd: Optional[SopcComponentDescription],
    ) -> None:
        super().__init__(class_name, instance_name, version or "", scd)

    # ------------------------------------------------------------------
    # Override reg generation (Phase 2)
    # Java overrides getReg() to produce two addr/size pairs per slave intf
    # ------------------------------------------------------------------

    # Phase 1: no DT output needed yet

    def to_dt_node(self, board_info: object, conn: object) -> object:
        raise NotImplementedError("USBHostControllerISP1xxx.to_dt_node — Phase 2")
