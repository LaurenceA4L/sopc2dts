# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.hps.ClockManager."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from ....log import logger
from ....model.component import BasicComponent, Interface, SopcComponentDescription
from ....model.connection import Connection
from ....model.enums import SystemDataType
from .VirtualClockElement import VirtualClockElement
from .SocFpgaGateClock import SocFpgaGateClock, _GateClkData
from .SocFpgaPeripClock import SocFpgaPeripClock
from .SocFpgaPllClock import SocFpgaPllClock

if TYPE_CHECKING:
    from ....model.system import AvalonSystem


# ---------------------------------------------------------------------------
# Data structures (inner classes from Java ported as dataclasses)
# ---------------------------------------------------------------------------

@dataclass
class ClockManagerGateClk:
    name: str
    has_gate: bool
    div_reg: Optional[List[int]]
    fixed_divider: Optional[int]
    clk_parents: List[str]


@dataclass
class ClockManagerGateGroup:
    reg: int
    clks: List[ClockManagerGateClk]


@dataclass
class ClockManagerPClk:
    name: str
    addr: Optional[int]
    fixed_divider: Optional[int]
    div_reg: Optional[List[int]]
    clk_parents: List[str]


@dataclass
class ClockManagerPll:
    name: str
    addr: int
    clk_parents: List[str]
    pclks: List[ClockManagerPClk]


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class ClockManager(BasicComponent):
    """
    Abstract base for HPS clock manager components.
    Port of sopc2dts.lib.components.altera.hps.ClockManager.
    """

    def __init__(self, bc: BasicComponent) -> None:
        super().__init__(bc.class_name, bc.instance_name, bc.version, bc.scd)
        self._parameters = bc._parameters
        self._interfaces = bc._interfaces
        for intf in self._interfaces:
            intf.owner = self

        self._virtual_components_created = False

        # Subclass must populate these before removeFromSystemIfPossible runs
        self.cmPLLs: Optional[List[ClockManagerPll]] = None
        self.cmGGroups: Optional[List[ClockManagerGateGroup]] = None
        self.cmPeripheralClks: Optional[List[ClockManagerPClk]] = None

        # Tracking lists
        self._vGateClocks: List[SocFpgaGateClock] = []
        self._vPeripheralClocks: List[SocFpgaPeripClock] = []

        # Virtual MM master (children register here)
        self._virtualMaster = Interface(
            VirtualClockElement.MM_MASTER_NAME,
            SystemDataType.MEMORY_MAPPED,
            True,
            self,
            secondary_width=0,
        )
        self._virtualMaster.interface_value = []
        self.add_interface(self._virtualMaster)

    # ------------------------------------------------------------------
    # Abstract methods
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def getFirstSupportedVersion(self) -> str: ...

    @abc.abstractmethod
    def preRemovalChecks(self, sys: "AvalonSystem") -> bool: ...

    @abc.abstractmethod
    def getSocFpgaPllClock(self, cName: str, iName: str, ver: Optional[str]) -> SocFpgaPllClock: ...

    @abc.abstractmethod
    def getSocFpgaPeripClock(
        self, cName: str, iName: str, ver: Optional[str],
        reg: Optional[int], div: Optional[int], divreg: Optional[List[int]],
    ) -> SocFpgaPeripClock: ...

    @abc.abstractmethod
    def getSocFpgaGateClock(self, cmgClk: ClockManagerGateClk, ver: Optional[str]) -> SocFpgaGateClock: ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _transferClockConnections(self, new_clock_master: Interface) -> None:
        old = self.get_interface_by_name(new_clock_master.owner.instance_name)
        if old is not None:
            logger.debug(
                "%s: transferring clock connections to %s",
                self.instance_name, new_clock_master.owner.instance_name,
            )
            while old.connections:
                conn = old.connections[0]
                conn.master_interface = new_clock_master
                old.connections.remove(conn)
                new_clock_master.connections.append(conn)
            self.remove_interface(old)

    def _getClockParentIntfByName(
        self, clk_parent_name: str, sys: "AvalonSystem"
    ) -> Optional[Interface]:
        clk_p_intf: Optional[Interface] = None

        # Check dedicated inputs on self
        clk_inp = self.get_interface_by_name(clk_parent_name)
        if clk_inp is not None and clk_inp.is_clock_slave() and clk_inp.connections:
            clk_p_intf = clk_inp.connections[0].master_interface

        if clk_p_intf is None:
            clk_parent = sys.get_component_by_name(clk_parent_name)
            if clk_parent is not None:
                if isinstance(clk_parent, VirtualClockElement):
                    clk_p_intf = clk_parent.get_clock_interface(True)
                else:
                    candidates = clk_parent.get_interfaces(SystemDataType.CLOCK, True)
                    if candidates:
                        clk_p_intf = candidates[0]

        return clk_p_intf

    # ------------------------------------------------------------------
    # System removal
    # ------------------------------------------------------------------

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if self._virtual_components_created:
            return False

        self._virtual_components_created = True

        from ....model.component import SopcComponentDescription as SCD
        if SCD.compare_versions(self.getFirstSupportedVersion(), self.version) < 0:
            logger.info(
                "%s: not supported on version '%s'. First supported: '%s'",
                self.instance_name, self.version, self.getFirstSupportedVersion(),
            )
            return False

        if not self.preRemovalChecks(sys):
            logger.warning("%s: pre-removal checks failed — not removing.", self.instance_name)
            return False

        if self.cmPLLs:
            for pll in self.cmPLLs:
                sf_pll = self.getSocFpgaPllClock(pll.name, pll.name, None)
                reg_intf = sf_pll.get_reg_interface(False)
                conn = Connection(self._virtualMaster, reg_intf, connect=True)
                conn.conn_value = [pll.addr]
                sys.add_system_component(sf_pll)
                for parent_name in pll.clk_parents:
                    sf_pll.add_clock_input(self._getClockParentIntfByName(parent_name, sys))
                for pclk in pll.pclks:
                    addr = (pll.addr + pclk.addr) if pclk.addr is not None else None
                    sf_pclk = self.getSocFpgaPeripClock(
                        pclk.name, pclk.name, None,
                        addr, pclk.fixed_divider, pclk.div_reg,
                    )
                    sf_pll.addClockOutput(sf_pclk)
                    if pclk.clk_parents:
                        for parent in pclk.clk_parents:
                            sf_pclk.add_clock_input(self._getClockParentIntfByName(parent, sys))
                    sys.add_system_component(sf_pclk)
                    self._transferClockConnections(sf_pclk.get_clock_interface(True))

        if self.cmPeripheralClks:
            for fpclk in self.cmPeripheralClks:
                sf_pclk = self.getSocFpgaPeripClock(
                    fpclk.name, fpclk.name, None,
                    fpclk.addr, fpclk.fixed_divider, fpclk.div_reg,
                )
                sys.add_system_component(sf_pclk)
                self._transferClockConnections(sf_pclk.get_clock_interface(True))
                self._vPeripheralClocks.append(sf_pclk)
                for parent in fpclk.clk_parents:
                    sf_pclk.add_clock_input(self._getClockParentIntfByName(parent, sys))

        if self.cmGGroups:
            for grp in self.cmGGroups:
                gate_reg = grp.reg
                gate_reg_bit = 0
                for cmg_clk in grp.clks:
                    sf_gclk = self.getSocFpgaGateClock(cmg_clk, None)
                    if cmg_clk.has_gate:
                        sf_gclk.gate_reg = [gate_reg, gate_reg_bit]
                        gate_reg_bit += 1
                    for parent_name in cmg_clk.clk_parents:
                        sf_gclk.add_clock_input(self._getClockParentIntfByName(parent_name, sys))
                    self._transferClockConnections(sf_gclk.get_clock_interface(True))
                    self._vGateClocks.append(sf_gclk)
                    sys.add_system_component(sf_gclk)

        return True

    # ------------------------------------------------------------------
    # Phase 2 stub
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: object) -> object:
        raise NotImplementedError("ClockManager.to_dt_node — Phase 2")
