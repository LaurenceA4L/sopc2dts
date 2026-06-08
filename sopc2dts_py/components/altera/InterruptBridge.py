# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Matthew Gerlach <mgerlach@altera.com>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.InterruptBridge."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...log import logger
from ...model.component import Interface, SopcComponentDescription
from ...model.enums import SystemDataType
from ..base.InterruptReceiver import InterruptReceiver

if TYPE_CHECKING:
    from ...model.connection import Connection


class InterruptBridge(InterruptReceiver):
    """
    Interrupt bridge — rewires upstream IRQ connections through slave offsets.
    Port of sopc2dts.lib.components.altera.InterruptBridge.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd)

    def _get_irq_slave_intf_at_offset(self, offset: int) -> Optional[Interface]:
        for intf in self.get_interfaces(SystemDataType.INTERRUPT, False):
            bridged = intf.get_param_val_by_name("bridgedReceiverOffset")
            if bridged is not None:
                try:
                    if int(bridged, 0) == offset:
                        return intf
                except (ValueError, TypeError):
                    pass
            else:
                if intf.name.lower() == f"sender{offset}_irq":
                    return intf
        return None

    def _remove_connection(self, conn: "Connection") -> None:
        cv = conn.conn_value
        offset = cv[0] if cv else 0
        irq_slave = self._get_irq_slave_intf_at_offset(offset)
        if irq_slave is None:
            logger.error(
                "%s: no irqSlave interface for offset %d",
                self.instance_name, offset,
            )
        else:
            slave_intf = conn.slave_interface
            while irq_slave.connections:
                irq_slave.connections[0].connect(slave_intf)
        conn.disconnect()
