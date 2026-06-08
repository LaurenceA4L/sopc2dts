# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.hps.SocFpgaPllClock."""

from __future__ import annotations

from typing import Optional

from ....log import logger
from ....model.component import Interface, SopcComponentDescription
from ....model.connection import Connection
from ....model.enums import SystemDataType
from .VirtualClockElement import VirtualClockElement
from .SocFpgaPeripClock import SocFpgaPeripClock


class SocFpgaPllClock(VirtualClockElement):
    """
    A PLL node in the HPS clock tree.  Owns a virtual MM master so that
    peripheral clocks can be attached as children.
    Port of sopc2dts.lib.components.altera.hps.SocFpgaPllClock.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: Optional[str],
        scd_pll: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd_pll)
        # Add a MM master interface so child pclks connect to us
        mm_master = Interface(
            self.MM_MASTER_NAME,
            SystemDataType.MEMORY_MAPPED,
            True,
            self,
            secondary_width=0,
        )
        mm_master.interface_value = []
        self.add_interface(mm_master)

    # ------------------------------------------------------------------
    # Clock output wiring
    # ------------------------------------------------------------------

    def addClockOutput(self, pclk: SocFpgaPeripClock) -> None:
        """Wire a SocFpgaPeripClock as a child of this PLL."""
        master = self.get_reg_interface(True)
        slave = pclk.get_reg_interface(False)
        if master is not None and slave is not None:
            conn = Connection(master, slave, connect=True)
            if pclk.reg_offset is not None:
                conn.conn_value = [pclk.reg_offset]
            pclk.add_clock_input(self.get_clock_interface(True))
        else:
            logger.warning(
                "%s: can't find interface to connect peripheral clock %s",
                self.instance_name, pclk.instance_name,
            )

    # ------------------------------------------------------------------
    # Phase 2 stub
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: object) -> object:
        raise NotImplementedError("SocFpgaPllClock.to_dt_node — Phase 2")
