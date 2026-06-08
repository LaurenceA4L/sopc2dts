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
Port of sopc2dts.lib.components.base.SICClockSource.

Generates a fixed-clock DT node (or a multi-output parent node) rather
than a memory-mapped slave node, since clock sources have no reg mapping.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...model.component import BasicComponent, Interface
from ...model.enums import SystemDataType

if TYPE_CHECKING:
    from ...model.connection import Connection


def freq_to_string(freq: int) -> str:
    """Human-readable frequency string. Port of SICClockSource.freq2String."""
    if freq > 1_000_000_000:
        return f"{freq / 1_000_000_000:.2f} GHz"
    elif freq > 1_000_000:
        return f"{freq / 1_000_000:.2f} MHz"
    elif freq > 1_000:
        return f"{freq / 1_000:.2f} kHz"
    else:
        return f"{float(freq):.2f} Hz"


class SICClockSource(BasicComponent):
    """
    A clock-source component.  Emits a fixed-clock (or multi-clock parent)
    DT node rather than a memory-mapped slave entry.
    Port of sopc2dts.lib.components.base.SICClockSource.
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
        self.clock_index: int = 0

    # ------------------------------------------------------------------
    # DT node generation (fully self-contained — does not call super)
    # ------------------------------------------------------------------

    def _create_clock_output_node(
        self, cm: Interface, idx: int, label: str
    ) -> object:
        """
        Build a single fixed-clock output node.
        Requires the DT model (Phase 2 imports are deferred).
        """
        from ...model.devicetree import DTNode, DTProperty  # type: ignore[attr-defined]

        freq = cm.interface_value[0] if cm.interface_value else 0
        node = DTNode(label, label)
        node.add_property(DTProperty("compatible", "fixed-clock"))
        node.add_property(DTProperty("#clock-cells", 0))
        node.add_property(DTProperty("clock-frequency", freq, freq_to_string(freq)))
        node.add_property(DTProperty(
            "clock-output-names",
            f"{self.instance_name}-{cm.name}",
        ))
        return node

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        from ...model.devicetree import DTNode, DTProperty  # type: ignore[attr-defined]

        clk_masters = self.get_interfaces(SystemDataType.CLOCK, True)
        if len(clk_masters) == 1:
            return self._create_clock_output_node(
                clk_masters[0], self.clock_index, self.instance_name
            )
        else:
            node = DTNode(self.instance_name, self.instance_name)
            node.add_property(DTProperty(
                "compatible",
                self.scd.get_compatibles(self.version) if self.scd else [self.class_name],
            ))
            node.add_property(DTProperty("#clock-cells", 1))
            for sub_idx, clk_intf in enumerate(clk_masters):
                child = self._create_clock_output_node(
                    clk_intf, sub_idx,
                    f"{self.instance_name}_{clk_intf.name}",
                )
                node.add_child(child)
            return node
