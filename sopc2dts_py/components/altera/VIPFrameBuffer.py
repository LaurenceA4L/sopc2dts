# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2013 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.VIPFrameBuffer."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...model.component import BasicComponent, SopcComponentDescription

if TYPE_CHECKING:
    from ...model.system import AvalonSystem
    from ...model.connection import Connection
    from .SICSgdma import SICSgdma


class VIPFrameBuffer(BasicComponent):
    """
    VIP frame buffer — encapsulates its connected SGDMA engine.
    Port of sopc2dts.lib.components.altera.VIPFrameBuffer.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd)
        self._dma_engine: Optional["SICSgdma"] = None

    def _encapsulate_sgdma(self, dma: "SICSgdma", sys: "AvalonSystem") -> None:
        sys.remove_component(dma)
        for if_name in ("csr", "csr_irq"):
            intf = dma.get_interface_by_name(if_name)
            if intf is not None:
                dma.remove_interface(intf)
                self._interfaces.append(intf)
                intf.owner = self

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        from .SICSgdma import SICSgdma
        intf = self.get_interface_by_name("in")
        if intf is None:
            return False
        for conn in intf.connections:
            if self._dma_engine is None and isinstance(conn.master_module, SICSgdma):
                self._dma_engine = conn.master_module
                self._encapsulate_sgdma(self._dma_engine, sys)
                return True
        return False

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        raise NotImplementedError("VIPFrameBuffer.to_dt_node — Phase 2")
