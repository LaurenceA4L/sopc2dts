# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2012 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.SICSgdma."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...model.component import BasicComponent, SopcComponentDescription

if TYPE_CHECKING:
    from ...model.connection import Connection


TYPE_NAMES = [
    "MEMORY_TO_MEMORY",
    "MEMORY_TO_STREAM",
    "STREAM_TO_MEMORY",
    "STREAM_TO_STREAM",
    "UNKNOWN",
]


class SICSgdma(BasicComponent):
    """Scatter-gather DMA controller component."""

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd)

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        from ...model.devicetree import DTProperty  # type: ignore[attr-defined]
        node = super().to_dt_node(board_info, conn)
        i_type = 0
        while i_type < (len(TYPE_NAMES) - 1):
            if TYPE_NAMES[i_type] == self.get_param_val_by_name("transferMode"):
                break
            i_type += 1
        node.add_property(DTProperty("type", TYPE_NAMES[i_type], i_type))
        return node
