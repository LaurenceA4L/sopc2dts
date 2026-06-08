# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2012 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.arm.CortexA9GIC."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...log import logger
from ...model.component import BasicComponent, Interface, SopcComponentDescription
from ...model.enums import SystemDataType

if TYPE_CHECKING:
    from ...model.system import AvalonSystem

# IRQ class constants
GIC_IRQ_CLASS_SPI = 0
GIC_IRQ_CLASS_PPI = 1

# IRQ type constants
GIC_IRQ_TYPE_RISING  = 1
GIC_IRQ_TYPE_FALLING = 2
GIC_IRQ_TYPE_HIGH    = 4
GIC_IRQ_TYPE_LOW     = 8

_SCD_ARM_GIC = SopcComponentDescription("arm_gic", "intc", "arm", "cortex-a9-gic")

_EMBSW_DTS_IRQ = "embeddedsw.dts.irq"


class CortexA9GIC(BasicComponent):
    """
    ARM Cortex-A9 GIC interrupt controller.
    Renumbers IRQ connection values so the DT generator sees
    [class, irqnr, type] triples.
    Port of sopc2dts.lib.components.arm.CortexA9GIC.
    """

    def __init__(self, instance_name: str, version: Optional[str]) -> None:
        super().__init__("arm_gic", instance_name, version or "", _SCD_ARM_GIC)
        self._irqs_renumbered = False

    # ------------------------------------------------------------------
    # Preferred interface widths (matches Java overrides)
    # ------------------------------------------------------------------

    def preferred_primary_width(
        self, iface_name: str, data_type: SystemDataType, is_master: bool
    ) -> Optional[int]:
        if is_master and data_type == SystemDataType.INTERRUPT:
            return 3
        return super().preferred_primary_width(iface_name, data_type, is_master)

    def preferred_secondary_width(
        self, iface_name: str, data_type: SystemDataType, is_master: bool
    ) -> Optional[int]:
        if is_master and data_type == SystemDataType.INTERRUPT:
            return 0
        return super().preferred_secondary_width(iface_name, data_type, is_master)

    # ------------------------------------------------------------------
    # IRQ class / type helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_irq_class_from_if(intf: Interface) -> int:
        rx_type_key = _EMBSW_DTS_IRQ + ".rx_type"
        irq_class = (
            GIC_IRQ_CLASS_PPI
            if intf.name.lower() == "arm_gic_ppi"
            else GIC_IRQ_CLASS_SPI
        )
        val = intf.get_param_val_by_name(rx_type_key)
        if val is not None:
            if val == "arm_gic_ppi":
                irq_class = GIC_IRQ_CLASS_PPI
            elif val == "arm_gic_spi":
                irq_class = GIC_IRQ_CLASS_SPI
            else:
                logger.error("unknown %s: %s", rx_type_key, val)
        return irq_class

    @staticmethod
    def _get_irq_type_from_if(intf: Interface) -> int:
        tx_type_key = _EMBSW_DTS_IRQ + ".tx_type"
        irq_type = GIC_IRQ_TYPE_HIGH
        val = intf.get_param_val_by_name(tx_type_key)
        if val is not None:
            mapping = {
                "ACTIVE_HIGH":  GIC_IRQ_TYPE_HIGH,
                "ACTIVE_LOW":   GIC_IRQ_TYPE_LOW,
                "FALLING_EDGE": GIC_IRQ_TYPE_FALLING,
                "RISING_EDGE":  GIC_IRQ_TYPE_RISING,
            }
            irq_type = mapping.get(val, GIC_IRQ_TYPE_HIGH)
            if val not in mapping:
                logger.error("unknown %s: %s", tx_type_key, val)
        tx_mask = intf.get_param_val_by_name(_EMBSW_DTS_IRQ + ".tx_mask")
        if tx_mask is not None:
            logger.debug("got mask %s", tx_mask)
            irq_type |= int(tx_mask, 0)
        return irq_type

    # ------------------------------------------------------------------
    # System removal: renumber IRQ conn_values
    # ------------------------------------------------------------------

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if not self._irqs_renumbered:
            for intf in self._interfaces:
                if intf.is_irq_master():
                    irq_class = self._get_irq_class_from_if(intf)
                    for conn in intf.connections:
                        irq_type = self._get_irq_type_from_if(conn.slave_interface)
                        cv = conn.conn_value
                        if cv and len(cv) >= 3:
                            cv[0] = irq_class
                            cv[1] = cv[2]   # irqnr was in slot 2
                            cv[2] = irq_type
            self._irqs_renumbered = True
        return False  # never actually removed from system

    # ------------------------------------------------------------------
    # Phase 2 stub
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: object) -> object:
        raise NotImplementedError("CortexA9GIC.to_dt_node — Phase 2")
