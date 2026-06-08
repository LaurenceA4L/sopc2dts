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
Renamed SICSICCpuComponent to carry the SOPC Info Component prefix consistently.
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from ...model.component import BasicComponent, SopcComponentDescription

if TYPE_CHECKING:
    from ...model.connection import Connection


# Nios II variants are uni-processors — cannot form SMP clusters
_SMP_BLACKLIST = frozenset(["altera_nios2", "altera_nios2_qsys"])


class SICCpuComponent(BasicComponent):
    """
    A CPU component instance.  Tracks cpu_index so the reg property emits
    the hart/CPU ID rather than a memory address.
    Port of sopc2dts.lib.components.base.SICCpuComponent.
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
    # Address helpers (mirrors Java getReg / getAddrFromConnection)
    # ------------------------------------------------------------------

    def _get_addr_from_conn(self, conn: Optional["Connection"]) -> List[int]:
        """When conn is None (no parent bus), return [cpu_index] as the address."""
        if conn is None:
            return [self.cpu_index]
        return list(conn.conn_value) if conn.conn_value else [0]

    # ------------------------------------------------------------------
    # SMP helpers
    # ------------------------------------------------------------------

    def is_smp_capable_with(self, other: "SICCpuComponent") -> bool:
        """True if both CPUs share the same class and are SMP-capable."""
        if self.scd is None or other.scd is None:
            return False
        if not self.scd.is_supporting_class_name(other.class_name):
            return False
        # Blacklisted uni-processors cannot form SMP
        for bl in _SMP_BLACKLIST:
            if self.scd.is_supporting_class_name(bl):
                return False
        return True

    # ------------------------------------------------------------------
    # DT node (Phase 2)
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        # Phase 2: super().to_dt_node needs to be implemented first.
        # SICCpuComponent overrides getReg/getAddrFromConnection so that when
        # conn is None, the address cell is cpu_index rather than 0.
        raise NotImplementedError("SICCpuComponent.to_dt_node — Phase 2")
