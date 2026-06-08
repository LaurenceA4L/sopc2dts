# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.TSEMonolithic."""

from __future__ import annotations

from enum import Enum
from typing import Optional, TYPE_CHECKING

from ...log import logger
from ...model.component import BasicComponent, Interface, SopcComponentDescription
from ...model.enums import SystemDataType
from .SICTrippleSpeedEthernet import SICTrippleSpeedEthernet
from .SICSgdma import SICSgdma

if TYPE_CHECKING:
    from ...model.system import AvalonSystem
    from ...model.connection import Connection


class TSEDmaType(Enum):
    UNKNOWN = "UNKNOWN"
    SGDMA = "SGDMA"
    mSGDMA = "mSGDMA"
    COMPOSED_mSGDMA = "COMPOSED_mSGDMA"


class TSEMonolithic(SICTrippleSpeedEthernet):
    """
    Triple-Speed Ethernet monolithic variant — encapsulates its own DMA engines.
    Port of sopc2dts.lib.components.altera.TSEMonolithic.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd)
        self._scd_msgdma = SopcComponentDescription(
            scd.get_class_names()[0], scd.group, "altr", "tse-msgdma"
        )
        self._scd_msgdma.add_compatible_version("1.0")
        self._rx_dma: Optional[BasicComponent] = None
        self._tx_dma: Optional[BasicComponent] = None
        self._desc_mem: Optional[BasicComponent] = None
        self._dma_type = TSEDmaType.UNKNOWN

    # ------------------------------------------------------------------
    # SCD override: use mSGDMA SCD when appropriate
    # ------------------------------------------------------------------

    @property
    def scd(self) -> SopcComponentDescription:
        if self._dma_type in (TSEDmaType.mSGDMA, TSEDmaType.COMPOSED_mSGDMA):
            return self._scd_msgdma
        return self._scd

    @scd.setter
    def scd(self, value: SopcComponentDescription) -> None:
        self._scd = value

    # ------------------------------------------------------------------
    # DMA encapsulation helpers
    # ------------------------------------------------------------------

    def _encapsulate_sgdma(
        self, sys: "AvalonSystem", dma: SICSgdma, name: str
    ) -> bool:
        for src, dst in [("csr", f"{name}_csr"), ("csr_irq", f"{name}_irq")]:
            intf = dma.get_interface_by_name(src)
            if intf is not None:
                dma.remove_interface(intf)
                intf.name = dst
                self._interfaces.append(intf)
                intf.owner = self
        return True

    def _encapsulate_shared_msgdma(
        self,
        sys: "AvalonSystem",
        dispatcher: BasicComponent,
        name: str,
        response: str,
    ) -> bool:
        for src, dst in [
            ("CSR", f"{name}_csr"),
            ("Descriptor_Slave", f"{name}_desc"),
            ("csr_irq", f"{name}_irq"),
        ]:
            intf = dispatcher.get_interface_by_name(src)
            if intf is not None:
                dispatcher.remove_interface(intf)
                intf.name = dst
                self._interfaces.append(intf)
                intf.owner = self
        resp = dispatcher.get_interface_by_name(response)
        if resp is not None:
            dispatcher.remove_interface(resp)
            resp.name = "rx_resp"
            self._interfaces.append(resp)
            resp.owner = self
        return True

    def _encapsulate_msgdma(
        self, sys: "AvalonSystem", dma: BasicComponent, name: str
    ) -> bool:
        cmd_sink = dma.get_interface_by_name("Command_Sink")
        dispatcher = self._get_dma_engine_for_intf(cmd_sink) if cmd_sink else None
        if dispatcher is None:
            logger.warning(
                "%s: failed to find dispatcher for %s",
                self.instance_name, dma.instance_name,
            )
            return False
        if sys.get_component_by_name(dispatcher.instance_name) is None:
            logger.warning(
                "%s: mSGDMA dispatcher %s in use",
                self.instance_name, dispatcher.instance_name,
            )
            return False
        if dispatcher.class_name.lower() == "modular_sgdma_dispatcher":
            logger.info(
                "%s: found dispatcher %s for %s",
                self.instance_name, dispatcher.instance_name, dma.instance_name,
            )
            self._encapsulate_shared_msgdma(sys, dispatcher, name, "Response_Slave")
            sys.remove_component(dispatcher)
            return True
        logger.warning(
            "%s: unsupported dispatcher %s (class %s)",
            self.instance_name, dispatcher.instance_name, dispatcher.class_name,
        )
        return False

    def _encapsulate_dma_engine(
        self,
        sys: "AvalonSystem",
        dma: Optional[BasicComponent],
        name: str,
    ) -> bool:
        if dma is None:
            return False
        if isinstance(dma, SICSgdma):
            changed = self._encapsulate_sgdma(sys, dma, name)
        elif self._dma_type == TSEDmaType.COMPOSED_mSGDMA:
            changed = self._encapsulate_shared_msgdma(sys, dma, name, "response")
        else:
            changed = self._encapsulate_msgdma(sys, dma, name)
        if changed:
            sys.remove_component(dma)
        return changed

    def _find_dma_engine(self, receiver: bool) -> Optional[BasicComponent]:
        rx_tx = "RX" if receiver else "TX"
        base = "receive" if receiver else "transmit"
        intf = self.get_interface_by_name(base) or self.get_interface_by_name(f"{base}_0")
        if intf is None:
            candidates = self.get_interfaces(SystemDataType.STREAMING, receiver)
            if not candidates:
                return None
            intf = candidates[0]
            logger.warning(
                "%s: no '%s' port, using first streaming %s port (%s)",
                self.instance_name, base, rx_tx, intf.name,
            )
        comp = self._get_dma_engine_for_intf(intf)
        if comp is None:
            logger.warning("%s: failed to find SGDMA %s engine", self.instance_name, rx_tx)
            return None
        cn = comp.class_name.lower()
        if cn in ("dma_write_master", "dma_read_master") and self._dma_type != TSEDmaType.SGDMA:
            self._dma_type = TSEDmaType.mSGDMA
            logger.info("%s: found %s mSGDMA engine", self.instance_name, rx_tx)
        elif (
            cn == "altera_msgdma"
            and self._dma_type not in (TSEDmaType.mSGDMA, TSEDmaType.SGDMA)
        ):
            self._dma_type = TSEDmaType.COMPOSED_mSGDMA
            logger.info("%s: found %s composed mSGDMA engine", self.instance_name, rx_tx)
        elif (
            isinstance(comp, SICSgdma)
            and self._dma_type not in (TSEDmaType.mSGDMA, TSEDmaType.COMPOSED_mSGDMA)
        ):
            self._dma_type = TSEDmaType.SGDMA
            logger.info("%s: found %s SGDMA engine", self.instance_name, rx_tx)
        else:
            logger.warning(
                "%s: failed to find (m)SGDMA %s — got %s (%s)",
                self.instance_name, rx_tx, comp.instance_name, comp.class_name,
            )
            return None
        return comp

    def _find_slave_component(
        self,
        intf: Optional[Interface],
        group: Optional[str],
        device: Optional[str],
    ) -> Optional[BasicComponent]:
        if intf is None:
            return None
        for conn in intf.connections:
            res = conn.slave_module
            if res is None:
                continue
            if res.scd and res.scd.group == "bridge":
                logger.warning(
                    "descriptor memory through bridge %s — may mis-identify memory",
                    res.instance_name,
                )
                for mm in res.get_interfaces(SystemDataType.MEMORY_MAPPED, True):
                    found = self._find_slave_component(mm, group, device)
                    if found:
                        return found
                continue
            if group and (not res.scd or res.scd.group != group):
                continue
            if device and (not res.scd or res.scd.device != device):
                continue
            return res
        return None

    # ------------------------------------------------------------------
    # System removal
    # ------------------------------------------------------------------

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        changed = False
        if self._rx_dma is None:
            self._rx_dma = self._find_dma_engine(True)
            changed |= self._encapsulate_dma_engine(sys, self._rx_dma, "rx")
        if self._tx_dma is None:
            self._tx_dma = self._find_dma_engine(False)
            changed |= self._encapsulate_dma_engine(sys, self._tx_dma, "tx")
        if self._desc_mem is None and self._dma_type == TSEDmaType.SGDMA:
            if self._rx_dma is None:
                logger.warning(
                    "%s: no RX-DMA engine, cannot find descriptor memory",
                    self.instance_name,
                )
            else:
                descr_intf = self._rx_dma.get_interface_by_name("descriptor_read")
                self._desc_mem = self._find_slave_component(
                    descr_intf, "memory", "onchipmem"
                )
                if self._desc_mem is None:
                    logger.warning(
                        "%s: no onchip descriptor memory, trying others",
                        self.instance_name,
                    )
                    self._desc_mem = self._find_slave_component(
                        descr_intf, "memory", None
                    )
                if self._desc_mem is not None:
                    sys.remove_component(self._desc_mem)
                    changed = True
                    for s_name in ("s1", "s2"):
                        slave = self._desc_mem.get_interface_by_name(s_name)
                        if slave is not None:
                            self._desc_mem.remove_interface(slave)
                            slave.owner = self
                            self._interfaces.append(slave)
                else:
                    logger.warning(
                        "%s: failed to find descriptor memory", self.instance_name
                    )
        return changed

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> object:
        raise NotImplementedError("TSEMonolithic.to_dt_node — Phase 2")
