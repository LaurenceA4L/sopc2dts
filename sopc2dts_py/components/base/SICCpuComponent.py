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
Port of sopc2dts.lib.components.base.SICCpuComponent.
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from ...model.component import BasicComponent

if TYPE_CHECKING:
    from ...model.connection import Connection


# Nios II variants are uni-processors — cannot form SMP clusters
_SMP_BLACKLIST = frozenset(["altera_nios2", "altera_nios2_qsys"])


class SICCpuComponent(BasicComponent):
    """
    A CPU component instance. Tracks cpu_index so the reg property emits
    the hart/CPU ID rather than a memory address.
    Port of sopc2dts.lib.components.base.CpuComponent.
    """

    def __init__(self, comp: BasicComponent) -> None:
        super().__init__(
            comp.class_name,
            comp.instance_name,
            comp.version,
            comp.scd,
        )
        self._parameters = comp._parameters
        self._interfaces = comp._interfaces
        for intf in self._interfaces:
            intf.owner = self
        self.cpu_index: int = 0

    # ------------------------------------------------------------------
    # Address/reg overrides (port of Java CpuComponent)
    # ------------------------------------------------------------------

    def _get_addr_from_connection(self, conn: Optional["Connection"]) -> List[int]:
        """When conn is None (standalone cpu@ node), address = cpu_index."""
        if conn is None:
            return [self.cpu_index]
        return list(conn.conn_value) if conn.conn_value else [0]

    def _get_reg(self, master, v_reg_names: List[str]) -> List[int]:
        """When master is None, reg = [cpu_index]."""
        if master is None:
            return [self.cpu_index]
        return super()._get_reg(master, v_reg_names)

    # ------------------------------------------------------------------
    # DT node
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        """Port of CpuComponent — delegates to BasicComponent after overriding addr helpers."""
        return super().to_dt_node(board_info, conn)

    # ------------------------------------------------------------------
    # SMP helpers
    # ------------------------------------------------------------------

    def is_smp_capable_with(self, other: "SICCpuComponent") -> bool:
        """True if both CPUs share the same class and are SMP-capable."""
        if self.scd is None or other.scd is None:
            return False
        if not self.scd.is_supporting_class_name(other.class_name):
            return False
        for bl in _SMP_BLACKLIST:
            if self.scd.is_supporting_class_name(bl):
                return False
        return True
