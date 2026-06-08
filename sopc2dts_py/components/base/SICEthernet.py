# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.base.SICEthernet."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from ...model.component import BasicComponent
from ...model.enums import SystemDataType

if TYPE_CHECKING:
    from ...model.connection import Connection


class PhyMode(Enum):
    MII = "mii"
    GMII = "gmii"
    RGMII = "rgmii"
    SGMII = "sgmii"
    NONE = "none"


class SICEthernet(BasicComponent):
    """
    Ethernet component — adds MAC address, PHY mode, and frame size properties.
    Port of sopc2dts.lib.components.base.SICEthernet.
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
        self._phy_mode: PhyMode = PhyMode.NONE

    def get_address_bits(self) -> int:
        return 48

    def get_max_frame_size(self) -> int:
        return 1518

    def get_mac_address(self, board_info: object) -> List[int]:
        eth = board_info.get_ethernet_for_chip(self.instance_name)
        return eth.mac if eth else [0, 0, 0, 0, 0, 0]

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        from ...model.devicetree import DTProperty  # type: ignore[attr-defined]
        node = super().to_dt_node(board_info, conn)
        node.add_property(DTProperty("address-bits", self.get_address_bits()))
        node.add_property(DTProperty("max-frame-size", self.get_max_frame_size()))
        mac_prop = DTProperty("local-mac-address")
        mac_prop.add_byte_values(self.get_mac_address(board_info))
        node.add_property(mac_prop)

        # GMII-to-SGMII converter conduit check
        for iconn in self.get_connections(SystemDataType.CONDUIT, False):
            if (iconn.slave_module and
                    iconn.slave_module.class_name.lower() ==
                    "altera_gmii_to_sgmii_converter"):
                from ...model.devicetree import DTPropPHandleVal  # type: ignore[attr-defined]
                phv = DTPropPHandleVal(iconn.slave_module.instance_name)
                node.add_property(DTProperty("altr,gmii-to-sgmii-converter", phv))
                node.add_property(DTProperty("altr,gmii_to_sgmii_converter", phv))
                self._phy_mode = PhyMode.SGMII

        if self._phy_mode != PhyMode.NONE:
            node.add_property(DTProperty("phy-mode", self._phy_mode.value))

        return node
