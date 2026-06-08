# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2016 Tien Hock Loh <thloh@altera.com>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.PCIeRootPort."""

from __future__ import annotations

from typing import Optional, Union, TYPE_CHECKING

from ...model.component import BasicComponent, SopcComponentDescription

if TYPE_CHECKING:
    from ...model.connection import Connection


class PCIeRootPort(BasicComponent):
    """
    PCIe root-port component — adds bus-range, ranges, interrupt-map.
    Port of sopc2dts.lib.components.altera.PCIeRootPort.
    """

    PCI_PHYS_HI_RELOCATABLE = (1 << 31)
    PCI_PHYS_HI_PREFETCHABLE = (1 << 30)
    PCI_PHYS_HI_ALIASED = (1 << 29)
    PCI_PHYS_HI_SPACE_CONFIG = (0 << 24)
    PCI_PHYS_HI_SPACE_IO = (1 << 24)
    PCI_PHYS_HI_SPACE_MEM32 = (2 << 24)
    PCI_PHYS_HI_SPACE_MEM64 = (3 << 24)

    def __init__(
        self,
        comp_or_class_name: Union[BasicComponent, str],
        instance_name: Optional[str] = None,
        version: Optional[str] = None,
        scd: Optional[SopcComponentDescription] = None,
    ) -> None:
        if isinstance(comp_or_class_name, BasicComponent):
            comp = comp_or_class_name
            super().__init__(comp.class_name, comp.instance_name, comp.version, comp.scd)
            self._parameters = comp._parameters
            self._interfaces = comp._interfaces
            for intf in self._interfaces:
                intf.owner = self
        else:
            super().__init__(
                comp_or_class_name, instance_name, version or "", scd
            )

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        raise NotImplementedError("PCIeRootPort.to_dt_node — Phase 2")
