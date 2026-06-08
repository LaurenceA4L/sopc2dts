# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2012 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.SICTrippleSpeedEthernet."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...log import logger
from ...model.component import BasicComponent, SopcComponentDescription
from ..base.SICEthernet import SICEthernet, PhyMode

if TYPE_CHECKING:
    from ...model.system import AvalonSystem
    from ...model.connection import Connection


class SICTrippleSpeedEthernet(SICEthernet):
    """
    Altera Triple-Speed Ethernet MAC — detects PHY mode during system removal.
    Port of sopc2dts.lib.components.altera.SICTrippleSpeedEthernet.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd)
        self._removed = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_dma_engine_for_intf(
        self, intf: Optional[object]
    ) -> Optional[BasicComponent]:
        if intf is None or not intf.connections:
            if intf is not None:
                logger.info("Interface %s has no connections.", intf.name)
            return None
        conn = intf.connections[0]
        return conn.slave_module if intf.is_master else conn.master_module

    # ------------------------------------------------------------------
    # System removal — detects PHY mode
    # ------------------------------------------------------------------

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if not self._removed:
            self._removed = True
            phy_mode_str = self.get_param_val_by_name("ifGMII")
            phy_mode_sgmii = self.get_param_val_by_name("enable_sgmii")
            self._phy_mode = PhyMode.RGMII
            if phy_mode_sgmii and phy_mode_sgmii.lower() == "true":
                self._phy_mode = PhyMode.SGMII
            elif phy_mode_str:
                if phy_mode_str == "MII":
                    self._phy_mode = PhyMode.MII
                elif phy_mode_str == "MII_GMII":
                    self._phy_mode = PhyMode.GMII
                elif phy_mode_str == "RGMII":
                    self._phy_mode = PhyMode.RGMII
            return True
        return False

    # ------------------------------------------------------------------
    # Phase 2 stubs
    # ------------------------------------------------------------------

    def _get_mdio_node(self, board_eth: object) -> Optional[object]:
        """Phase 2 — MDIO child node generation."""
        raise NotImplementedError("SICTrippleSpeedEthernet._get_mdio_node — Phase 2")

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        raise NotImplementedError("SICTrippleSpeedEthernet.to_dt_node — Phase 2")
