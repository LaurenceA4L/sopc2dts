# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.base.SICI2CMaster."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...model.component import BasicComponent

if TYPE_CHECKING:
    from ...model.connection import Connection


class SICI2CMaster(BasicComponent):
    """
    I2C master — adds #address-cells, #size-cells and slave sub-nodes.
    Port of sopc2dts.lib.components.base.SICI2CMaster.
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

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        from ...model.devicetree import DTProperty  # type: ignore[attr-defined]
        node = super().to_dt_node(board_info, conn)
        i2c_info = board_info.get_i2c_for_chip(self.instance_name)
        slaves = sorted(i2c_info.slaves) if i2c_info else []
        if slaves:
            node.add_property(DTProperty("#address-cells", 1))
            node.add_property(DTProperty("#size-cells", 0))
            for slave in slaves:
                node.add_child(slave.to_dt_node(board_info))
        return node
