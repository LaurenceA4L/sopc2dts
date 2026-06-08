# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2013 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.SICEpcs."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...model.enums import SystemDataType
from ..base.SICFlash import SICFlash

if TYPE_CHECKING:
    from ...model.system import AvalonSystem
    from ...model.connection import Connection


class SICEpcs(SICFlash):
    """
    EPCS serial configuration device — extends SICFlash.
    Adjusts addresses by REGISTER_OFFSET and adds m25p80 sub-node.
    Port of sopc2dts.lib.components.altera.SICEpcs.
    """

    def __init__(self, class_name: str, instance_name: str, version: str) -> None:
        from ...model.component_lib import SopcComponentLib
        scd = SopcComponentLib.get_instance().get_scd_by_class_name("altera_avalon_spi")
        super().__init__(class_name, instance_name, version, scd)
        self._address_fixed = False

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if not self._address_fixed:
            self._address_fixed = True
            try:
                reg_offset_str = self.get_param_val_by_name(
                    self.EMBSW_CMACRO + ".REGISTER_OFFSET"
                )
                reg_offset = int(reg_offset_str, 0) if reg_offset_str else 0
                if reg_offset > 0:
                    for intf in self.get_interfaces(SystemDataType.MEMORY_MAPPED, False):
                        for conn in intf.connections:
                            if conn.conn_value:
                                conn.conn_value = [v + reg_offset for v in conn.conn_value]
                        if intf.interface_value:
                            intf.interface_value = [v - reg_offset for v in intf.interface_value]
            except Exception:
                pass
            return True
        return False

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        from ...model.devicetree import DTNode, DTProperty  # type: ignore[attr-defined]
        node = super().to_dt_node(board_info, conn)
        node.add_property(DTProperty("#address-cells", 1))
        node.add_property(DTProperty("#size-cells", 0))
        m25p80 = DTNode("m25p80@0")
        m25p80.add_property(DTProperty("compatible", "m25p80"))
        m25p80.add_property(DTProperty("spi-max-frequency", 25000000))
        m25p80.add_property(DTProperty("reg", 0))
        self._add_partitions_to_dt_node(board_info, m25p80)
        node.add_child(m25p80)
        return node
