# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Matthew Gerlach <mgerlach@altera.com>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.InterruptReceiver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...log import logger
from ...model.component import BasicComponent, SopcComponentDescription
from ...model.enums import SystemDataType

if TYPE_CHECKING:
    from ...model.system import AvalonSystem
    from ...model.connection import Connection


class InterruptReceiver(BasicComponent):
    """
    Base class for components that act as IRQ bridges or latency counters.
    Removes all IRQ connections from its single interrupt-master interface.
    Port of sopc2dts.lib.components.InterruptReceiver.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd)
        self._removed = False

    def _remove_connection(self, conn: "Connection") -> None:
        """Subclasses override to rewire before disconnecting."""
        conn.disconnect()

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if not self._removed:
            self._removed = True
            irq_masters = self.get_interfaces(SystemDataType.INTERRUPT, True)
            if len(irq_masters) != 1:
                logger.error(
                    "%s: expected 1 interrupt master, got %d",
                    self.instance_name, len(irq_masters),
                )
                return False
            irq_master = irq_masters[0]
            logger.debug("irq receiver is %s", irq_master.name)
            while irq_master.connections:
                self._remove_connection(irq_master.connections[0])
            return True
        return False
