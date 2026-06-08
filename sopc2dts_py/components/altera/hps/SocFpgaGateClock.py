# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.hps.SocFpgaGateClock."""

from __future__ import annotations

from typing import List, Optional

from ....model.component import SopcComponentDescription
from .VirtualClockElement import VirtualClockElement


class _GateClkData:
    """Mirrors ClockManager.ClockManagerGateClk inner class."""
    __slots__ = ("name", "has_gate", "div_reg", "fixed_divider", "clk_parents")

    def __init__(
        self,
        name: str,
        has_gate: bool,
        div_reg: Optional[List[int]],
        fixed_divider: Optional[int],
        clk_parents: List[str],
    ) -> None:
        self.name = name
        self.has_gate = has_gate
        self.div_reg = div_reg
        self.fixed_divider = fixed_divider
        self.clk_parents = clk_parents


class SocFpgaGateClock(VirtualClockElement):
    """
    A gated clock node in the HPS clock tree.
    Port of sopc2dts.lib.components.altera.hps.SocFpgaGateClock.
    """

    def __init__(
        self,
        cm_gclk: "_GateClkData",
        version: Optional[str],
        scd_gclk: SopcComponentDescription,
    ) -> None:
        super().__init__(cm_gclk.name, cm_gclk.name, version, scd_gclk)
        self.gate_reg: Optional[List[int]] = None  # set by ClockManager after construction
        self._div_reg: Optional[List[int]] = cm_gclk.div_reg
        self._fixed_divider: Optional[int] = cm_gclk.fixed_divider

    # ------------------------------------------------------------------
    # Phase 2 stub
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: object) -> object:
        raise NotImplementedError("SocFpgaGateClock.to_dt_node — Phase 2")
