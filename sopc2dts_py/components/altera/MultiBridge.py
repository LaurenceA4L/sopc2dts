# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2013-2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.MultiBridge."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from ...log import logger
from ...model.component import BasicComponent, Interface, SopcComponentDescription
from ...model.enums import SystemDataType
from ..base.SICBridge import SICBridge

if TYPE_CHECKING:
    from ...model.system import AvalonSystem
    from ...model.connection import Connection


_HPS_BRIDGE_SCD = SopcComponentDescription("bridge", "bridge", "ALTR", "bridge")
_HPS2FPGA_BRIDGE_NAMES = ["h2f", "h2f_lw"]


class MultiBridge(SICBridge):
    """
    HPS multi-bridge — splits f2h and h2f bridges into separate components.
    Port of sopc2dts.lib.components.altera.MultiBridge.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        # SICBridge is copy-constructor-only; wrap in a BasicComponent first.
        bc = BasicComponent(class_name, instance_name, version, scd)
        super().__init__(bc)
        self._f2h_bridge: Optional[SICBridge] = None

    # ------------------------------------------------------------------
    # System removal
    # ------------------------------------------------------------------

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if self._f2h_bridge is None:
            self._f2h_bridge = self._get_bridge("f2h")
            sys.add_component(self._f2h_bridge)
            for i, name in enumerate(_HPS2FPGA_BRIDGE_NAMES):
                intf = self.get_interface_by_name(name)
                if intf is not None:
                    self._create_virtual_addresses(intf, i)
            return True
        return False

    def _get_bridge(self, base_name: str) -> SICBridge:
        intf_name_formats = [
            f"axi_{base_name}",
            f"{base_name}_reset",
            f"{base_name}_axi_clock",
            base_name,
        ]
        bridge = SICBridge.__new__(SICBridge)
        BasicComponent.__init__(
            bridge,
            self.class_name,
            f"{self.instance_name}_{base_name}",
            self.version,
            _HPS_BRIDGE_SCD,
        )
        bridge._parameters = []
        bridge._interfaces = []
        for fmt in intf_name_formats:
            intf = self.get_interface_by_name(fmt)
            if intf is not None:
                self.remove_interface(intf)
                bridge.add_interface(intf)
            else:
                logger.debug("MultiBridge: failed to find interface %s", fmt)
        return bridge

    def _create_virtual_addresses(self, master: Interface, cs: int) -> None:
        width = master.get_primary_width() + 1
        master.primary_width = width
        for conn in master.connections:
            old = conn.conn_value or []
            conn.conn_value = [cs] + list(old)

    # ------------------------------------------------------------------
    # Address translation overrides
    # ------------------------------------------------------------------

    def translate_address(
        self,
        master_val: Optional[List[int]],
        slave_val: Optional[List[int]],
    ) -> Optional[List[int]]:
        if master_val is None or slave_val is None:
            return None
        m, s = list(master_val), list(slave_val)
        # Strip CS field if mAddr is one shorter than sAddr
        if len(m) == (len(s) - 1):
            ns = s[1:]
        else:
            ns = s
        return super().translate_address(m, ns)

    def translate_address_from_conns(
        self, master_conn: "Connection", slave_conn: "Connection"
    ) -> Optional[List[int]]:
        upstream_slave = self.get_interface_by_name(
            "axi_" + slave_conn.master_interface.name
        )
        effective_master_conn = master_conn
        if upstream_slave is not master_conn.slave_interface:
            if upstream_slave and upstream_slave.connections:
                effective_master_conn = upstream_slave.connections[0]
        return self.translate_address(
            effective_master_conn.conn_value, slave_conn.conn_value
        )
