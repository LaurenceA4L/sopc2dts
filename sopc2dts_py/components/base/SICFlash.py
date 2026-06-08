# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.base.SICFlash."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...model.component import BasicComponent

if TYPE_CHECKING:
    from ...model.connection import Connection


class SICFlash(BasicComponent):
    """
    Flash memory component — adds bank-width and partition sub-nodes.
    Port of sopc2dts.lib.components.base.SICFlash.
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

    def get_bank_width(self) -> int:
        """Port of SICFlash.getBankWidth — default 2 bytes (16-bit)."""
        sdw = self.get_param_val_by_name("dataWidth")
        if sdw is None:
            sdw = self.get_param_val_by_name("TCM_DATA_W")
        if sdw is not None:
            try:
                return int(sdw, 0) // 8
            except (ValueError, TypeError):
                pass
        return 2

    def _add_partitions_to_dt_node(self, board_info: object, node: object) -> object:
        from ...model.devicetree import DTNode, DTProperty  # type: ignore[attr-defined]

        partitions = board_info.get_partitions_for_chip(self.instance_name)
        if not partitions:
            return node

        node.add_property(DTProperty("#address-cells", 1))
        node.add_property(DTProperty("#size-cells", 1))
        for part in partitions:
            part_node = DTNode(
                f"{part.name}@{part.address:x}",
                part.name,
            )
            reg_prop = DTProperty("reg")
            reg_prop.add_hex_values([part.address, part.size])
            reg_prop.set_num_values_per_row(2)
            part_node.add_property(reg_prop)
            if part.readonly:
                part_node.add_property(DTProperty("read-only"))
            node.add_child(part_node)
        return node

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        from ...model.devicetree import DTProperty  # type: ignore[attr-defined]
        node = super().to_dt_node(board_info, conn)
        node.add_property(DTProperty("bank-width", self.get_bank_width()))
        node.add_property(DTProperty("device-width", 1))
        return self._add_partitions_to_dt_node(board_info, node)
