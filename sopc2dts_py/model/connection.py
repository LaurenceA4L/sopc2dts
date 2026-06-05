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
Port of sopc2dts.lib.Connection — a directed link between two Interfaces.
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING

from .enums import SystemDataType
from .component import BasicElement

if TYPE_CHECKING:
    from .component import Interface, BasicComponent


class Connection(BasicElement):
    """
    A directed link from a master Interface to a slave Interface.
    Port of sopc2dts.lib.Connection.
    """

    def __init__(
        self,
        master: "Interface",
        slave: "Interface",
        conn_type: Optional[SystemDataType] = None,
        connect: bool = False,
    ) -> None:
        super().__init__()
        self.type: SystemDataType = conn_type if conn_type is not None else master.type
        self.conn_value: Optional[List[int]] = None

        if connect:
            self._master_interface: Optional["Interface"] = None
            self._slave_interface: Optional["Interface"] = None
            self.connect_master(master)
            self.connect_slave(slave)
        else:
            self._master_interface = master
            self._slave_interface = slave

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, intf: "Interface") -> None:
        if intf.is_master:
            self.connect_master(intf)
        else:
            self.connect_slave(intf)

    def connect_master(self, intf: "Interface") -> None:
        if self._master_interface is not None:
            try:
                self._master_interface.connections.remove(self)
            except ValueError:
                pass
        self._master_interface = intf
        intf.connections.append(self)

    def connect_slave(self, intf: "Interface") -> None:
        if self._slave_interface is not None:
            try:
                self._slave_interface.connections.remove(self)
            except ValueError:
                pass
        self._slave_interface = intf
        intf.connections.append(self)

    def disconnect(self, intf: Optional["Interface"] = None) -> None:
        if intf is None:
            self.disconnect(self._master_interface)
            self.disconnect(self._slave_interface)
            return
        try:
            intf.connections.remove(self)
        except ValueError:
            pass
        if self._slave_interface is intf:
            self._slave_interface = None
        if self._master_interface is intf:
            self._master_interface = None

    # ------------------------------------------------------------------
    # Value
    # ------------------------------------------------------------------

    def set_conn_value(self, val: List[int]) -> None:
        expected = self.master_interface.get_primary_width() if self.master_interface else 0
        if len(val) == expected:
            self.conn_value = val
        else:
            from ..log import logger
            logger.error(
                "set_conn_value: width mismatch — got %d, expected %d",
                len(val), expected,
            )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def master_interface(self) -> Optional["Interface"]:
        return self._master_interface

    @master_interface.setter
    def master_interface(self, intf: Optional["Interface"]) -> None:
        self._master_interface = intf

    @property
    def slave_interface(self) -> Optional["Interface"]:
        return self._slave_interface

    @slave_interface.setter
    def slave_interface(self, intf: Optional["Interface"]) -> None:
        self._slave_interface = intf

    @property
    def master_module(self) -> Optional["BasicComponent"]:
        return self._master_interface.owner if self._master_interface else None

    @property
    def slave_module(self) -> Optional["BasicComponent"]:
        return self._slave_interface.owner if self._slave_interface else None

    def __repr__(self) -> str:
        m = self._master_interface.owner.instance_name if self._master_interface else "?"
        s = self._slave_interface.owner.instance_name if self._slave_interface else "?"
        return f"Connection({m} → {s}, {self.type.name})"
