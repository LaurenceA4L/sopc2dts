# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Matthew Gerlach <matt@smallplanetbrewery.com>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.InterruptLatencyCounter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...model.component import Interface, SopcComponentDescription
from ...model.enums import SystemDataType
from ..base.InterruptReceiver import InterruptReceiver

if TYPE_CHECKING:
    from ...model.connection import Connection


class InterruptLatencyCounter(InterruptReceiver):
    """
    IRQ latency counter — absorbs an IRQ connection and creates a new sender.
    Port of sopc2dts.lib.components.altera.InterruptLatencyCounter.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd)

    def _remove_connection(self, conn: "Connection") -> None:
        irq_sender = conn.slave_interface
        new_sender = Interface(
            irq_sender.owner.instance_name,
            SystemDataType.INTERRUPT,
            False,
            self,
        )
        self.add_interface(new_sender)
        # Transfer existing downstream connections to new sender
        existing_connections = list(irq_sender.connections)
        conn.disconnect()
        new_sender._connections = existing_connections
