# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2013 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.labx.LabXEthernet."""

from __future__ import annotations

from typing import Optional

from ...model.component import BasicComponent, Interface, SopcComponentDescription
from ..base.SICEthernet import SICEthernet

_SUPPORTED_MACS = ("labx_eth_mac", "labx_10g_eth_mac")


class LabXEthernet(SICEthernet):
    """
    Lab X Ethernet wrapper — finds the underlying MAC and exposes phy-mode.
    Port of sopc2dts.lib.components.labx.LabXEthernet.
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
    # Helpers
    # ------------------------------------------------------------------

    def _find_labx_eth_mac(self, intf: Optional[Interface]) -> Optional[BasicComponent]:
        if intf is None or not intf.connections:
            return None

        conn = intf.connections[0]
        comp: Optional[BasicComponent] = conn.slave_module
        if comp is self:
            comp = conn.master_module

        if comp is None:
            return None

        # Check if it's a supported MAC
        for mac_type in _SUPPORTED_MACS:
            if comp.class_name.lower() == mac_type:
                return comp

        # Handle tx arbiter passthrough
        if comp.class_name.lower() == "labx_eth_tx_arbiter":
            return self._find_labx_eth_mac(comp.get_interface_by_name("mac_tx"))

        return None

    def _get_phy_mode_string(self) -> str:
        mac_tx_intf = self.get_interface_by_name("mac_tx")
        mac = self._find_labx_eth_mac(mac_tx_intf)
        if mac is not None:
            val = mac.get_param_val_by_name("MII_TYPE")
            if val is not None:
                return val
        return "UNKNOWN"

    def _get_max_frame_size(self) -> int:
        # LabX supports VLAN tags
        return 1522

    # ------------------------------------------------------------------
    # Phase 2 stub
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: object) -> object:
        raise NotImplementedError("LabXEthernet.to_dt_node — Phase 2")
