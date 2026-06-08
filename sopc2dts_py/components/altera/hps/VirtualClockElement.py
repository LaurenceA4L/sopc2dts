# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.hps.VirtualClockElement."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from ....log import logger
from ....model.component import BasicComponent, Interface, SopcComponentDescription
from ....model.connection import Connection
from ....model.enums import SystemDataType

if TYPE_CHECKING:
    pass


class VirtualClockElement(BasicComponent):
    """
    Abstract base for HPS virtual clock components.
    Creates a MM slave interface and a clock output interface.
    Port of sopc2dts.lib.components.altera.hps.VirtualClockElement.
    """

    CLOCK_INPUT_NAME = "virtual-clk-input"
    CLOCK_OUTPUT_NAME = "virtual-clk-output"
    MM_SLAVE_NAME = "virtual-reg"
    MM_MASTER_NAME = "virtual-mm-master"

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: Optional[str],
        scd: SopcComponentDescription,
        reg: Optional[int] = None,
    ) -> None:
        super().__init__(class_name, instance_name, version or "", scd)
        self._reg_offset: Optional[int] = reg
        self._init_base_interfaces()

    def _init_base_interfaces(self) -> None:
        mm_if = Interface(
            self.MM_SLAVE_NAME,
            SystemDataType.MEMORY_MAPPED,
            False,
            self,
            secondary_width=0,
        )
        mm_if.interface_value = []
        self.add_interface(mm_if)
        clk_if = Interface(
            self.CLOCK_OUTPUT_NAME,
            SystemDataType.CLOCK,
            True,
            self,
        )
        self.add_interface(clk_if)

    # ------------------------------------------------------------------
    # Interface accessors
    # ------------------------------------------------------------------

    def get_clock_interface(self, is_master: bool) -> Optional[Interface]:
        name = self.CLOCK_OUTPUT_NAME if is_master else self.CLOCK_INPUT_NAME
        intf = self.get_interface_by_name(name)
        if intf is None:
            candidates = self.get_interfaces(SystemDataType.CLOCK, is_master)
            intf = candidates[0] if candidates else None
        return intf

    def get_reg_interface(self, is_master: bool) -> Optional[Interface]:
        name = self.MM_MASTER_NAME if is_master else self.MM_SLAVE_NAME
        intf = self.get_interface_by_name(name)
        if intf is None:
            candidates = self.get_interfaces(SystemDataType.MEMORY_MAPPED, is_master)
            intf = candidates[0] if candidates else None
        return intf

    # ------------------------------------------------------------------
    # Register offset
    # ------------------------------------------------------------------

    @property
    def reg_offset(self) -> Optional[int]:
        return self._reg_offset

    @reg_offset.setter
    def reg_offset(self, val: int) -> None:
        self._reg_offset = val

    # ------------------------------------------------------------------
    # Clock wiring helper
    # ------------------------------------------------------------------

    def add_clock_input(self, clk_master: Optional[Interface]) -> None:
        if clk_master is None:
            logger.debug("%s: add_clock_input called with None", self.instance_name)
            return
        clk_if = Interface(
            clk_master.owner.instance_name,
            SystemDataType.CLOCK,
            False,
            self,
        )
        self.add_interface(clk_if)
        Connection(clk_master, clk_if, connect=True)

    # ------------------------------------------------------------------
    # Phase 2 stub
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: object) -> object:
        raise NotImplementedError("VirtualClockElement.to_dt_node — Phase 2")
