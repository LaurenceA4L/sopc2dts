# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2013 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.VIPMixer."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...model.component import BasicComponent, SopcComponentDescription
from ...model.connection import Connection as _Connection
from ...model.enums import SystemDataType

if TYPE_CHECKING:
    from ...model.system import AvalonSystem
    from ...model.connection import Connection


class VIPMixer(BasicComponent):
    """
    VIP mixer / switch — connects all streaming input channels to all outputs.
    Port of sopc2dts.lib.components.altera.VIPMixer.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd)
        self._connected_others = False

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if not self._connected_others:
            self._connected_others = True
            if_master = self.get_interface_by_name("dout")
            if if_master is None:
                return True
            for conn2new_slave in if_master.connections:
                for if_slave in self.get_interfaces(SystemDataType.STREAMING, False):
                    for conn2new_master in if_slave.connections:
                        _Connection(
                            conn2new_master.master_interface,
                            conn2new_slave.slave_interface,
                            SystemDataType.STREAMING,
                            connect=True,
                        )
            return True
        return False

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        raise NotImplementedError("VIPMixer.to_dt_node — Phase 2")
