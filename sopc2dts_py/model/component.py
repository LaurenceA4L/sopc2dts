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
Port of:
  sopc2dts.lib.BasicElement
  sopc2dts.lib.components.Interface
  sopc2dts.lib.components.MemoryBlock
  sopc2dts.lib.components.BasicComponent
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING

from .enums import SystemDataType, ParameterAction
from .parameter import Parameter

if TYPE_CHECKING:
    from .connection import Connection
    from .devicetree import DTNode


# ---------------------------------------------------------------------------
# BasicElement
# ---------------------------------------------------------------------------

class BasicElement:
    """
    Base class for all sopcinfo model objects that carry parameters.
    Port of sopc2dts.lib.BasicElement.
    """

    def __init__(self) -> None:
        self._parameters: List[Parameter] = []

    def add_param(self, param: Parameter) -> None:
        self._parameters.append(param)

    def remove_param(self, param: Parameter) -> None:
        self._parameters.remove(param)

    def get_param_by_name(self, name: str) -> Optional[Parameter]:
        nl = name.lower()
        for p in self._parameters:
            if p.name.lower() == nl:
                return p
        return None

    def get_param_val_by_name(self, name: str) -> Optional[str]:
        p = self.get_param_by_name(name)
        return p.value if p else None

    @property
    def params(self) -> List[Parameter]:
        return self._parameters


# ---------------------------------------------------------------------------
# MemoryBlock
# ---------------------------------------------------------------------------

class MemoryBlock:
    """
    A memory region visible from a master.
    Port of sopc2dts.lib.components.MemoryBlock.
    """

    def __init__(
        self,
        owner: "BasicComponent",
        base: List[int],
        size: List[int],
    ) -> None:
        self.owner = owner
        self.base = base
        self.size = size

    @property
    def module_name(self) -> str:
        return self.owner.instance_name

    def __repr__(self) -> str:
        return f"MemoryBlock({self.owner.instance_name!r}, base={self.base}, size={self.size})"


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

class Interface(BasicElement):
    """
    A single port on a BasicComponent.
    Port of sopc2dts.lib.components.Interface.
    """

    def __init__(
        self,
        name: str,
        data_type: SystemDataType,
        is_master: bool,
        owner: "BasicComponent",
        primary_width: Optional[int] = None,
        secondary_width: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.type = data_type
        self.is_master = is_master
        self.owner = owner
        self.interface_value: Optional[List[int]] = None
        self._connections: List["Connection"] = []

        # Primary width — defaults to 1 for all types
        self.primary_width: int = primary_width if primary_width is not None else (
            owner.preferred_primary_width(name, data_type, is_master) or 1
        )

        # Secondary width — type-dependent defaults matching Java
        if secondary_width is not None:
            self.secondary_width: int = secondary_width
        else:
            sec = owner.preferred_secondary_width(name, data_type, is_master)
            if sec is not None:
                self.secondary_width = sec
            elif data_type == SystemDataType.CLOCK:
                self.secondary_width = 1 if is_master else 0
            elif data_type == SystemDataType.MEMORY_MAPPED:
                self.secondary_width = 1
            else:
                self.secondary_width = 0

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @property
    def connections(self) -> List["Connection"]:
        return self._connections

    def set_interface_value(self, val: List[int]) -> None:
        if len(val) == self.get_secondary_width():
            self.interface_value = val
        else:
            from ..log import logger
            logger.error(
                "set_interface_value: width mismatch — got %d, expected %d",
                len(val), self.get_secondary_width(),
            )

    # ------------------------------------------------------------------
    # Width helpers — slave defers to master connection if present
    # ------------------------------------------------------------------

    def get_primary_width(self) -> int:
        if not self.is_master and self._connections:
            mi = self._connections[0].master_interface
            if mi is not None:
                return mi.primary_width
        return self.primary_width

    def get_secondary_width(self) -> int:
        if not self.is_master and self._connections:
            mi = self._connections[0].master_interface
            if mi is not None:
                return mi.secondary_width
        return self.secondary_width

    # ------------------------------------------------------------------
    # Convenience predicates
    # ------------------------------------------------------------------

    def is_memory(self) -> bool:
        return self.type == SystemDataType.MEMORY_MAPPED

    def is_memory_master(self) -> bool:
        return self.is_memory() and self.is_master

    def is_memory_slave(self) -> bool:
        return self.is_memory() and not self.is_master

    def is_clock(self) -> bool:
        return self.type == SystemDataType.CLOCK

    def is_clock_master(self) -> bool:
        return self.is_clock() and self.is_master

    def is_clock_slave(self) -> bool:
        return self.is_clock() and not self.is_master

    def is_irq(self) -> bool:
        return self.type == SystemDataType.INTERRUPT

    def is_irq_master(self) -> bool:
        return self.is_irq() and self.is_master

    def is_irq_slave(self) -> bool:
        return self.is_irq() and not self.is_master

    def get_memory_map(self) -> List[MemoryBlock]:
        """Walk connections from a memory master to build a MemoryBlock list."""
        from .connection import Connection  # avoid top-level circular import

        result: List[MemoryBlock] = []
        if not self.is_memory_master():
            return result
        for conn in self._connections:
            slave = conn.slave_module
            if slave is None:
                continue
            # Bridges expand recursively — handled by SICBridge subclass
            if hasattr(slave, "get_memory_map"):
                result.extend(slave.get_memory_map(conn))
            else:
                si = conn.slave_interface
                size = si.interface_value if si and si.interface_value else []
                base = list(conn.conn_value) if conn.conn_value else []
                result.append(MemoryBlock(slave, base, size))
        return result

    def __repr__(self) -> str:
        direction = "master" if self.is_master else "slave"
        return f"Interface({self.name!r}, {self.type.name}, {direction})"


# ---------------------------------------------------------------------------
# SopcComponentDescription placeholder
# ---------------------------------------------------------------------------

class SopcComponentDescription:
    """
    Minimal placeholder — full implementation lives in component_lib.py.
    Provides the fields BasicComponent needs before the library is loaded.
    """

    def __init__(
        self,
        class_name: str,
        group: str = "unknown",
        vendor: str = "unknown",
    ) -> None:
        self.class_name = class_name
        self.group = group
        self.vendor = vendor
        self._compatibles: List[str] = []
        self._auto_params: List = []

    def get_compatibles(self, version: str) -> List[str]:
        return self._compatibles

    @property
    def auto_params(self) -> List:
        return self._auto_params

    def __repr__(self) -> str:
        return f"SopcComponentDescription({self.class_name!r})"


# ---------------------------------------------------------------------------
# BasicComponent
# ---------------------------------------------------------------------------

class BasicComponent(BasicElement):
    """
    A hardware IP component instance in an AvalonSystem.
    Port of sopc2dts.lib.components.BasicComponent.

    Note: toDTNode / getClocksProperty are implemented in Phase 2 once the
    devicetree model exists. They raise NotImplementedError for now so callers
    know they are not yet available rather than silently returning garbage.
    """

    # embeddedsw parameter name constants (mirrors Java)
    EMBSW = "embeddedsw"
    EMBSW_CMACRO = EMBSW + ".CMacro"
    EMBSW_CONF = EMBSW + ".configuration"
    EMBSW_DTS = EMBSW + ".dts"
    EMBSW_DTS_COMPAT = EMBSW_DTS + ".compatible"
    EMBSW_DTS_GROUP = EMBSW_DTS + ".group"
    EMBSW_DTS_IRQ = EMBSW_DTS + ".irq"
    EMBSW_DTS_NAME = EMBSW_DTS + ".name"
    EMBSW_DTS_PARAMS = EMBSW_DTS + ".params."
    EMBSW_DTS_VENDOR = EMBSW_DTS + ".vendor"

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: Optional[SopcComponentDescription] = None,
    ) -> None:
        super().__init__()
        self.class_name = class_name
        self.instance_name = instance_name
        self.version = version
        self._interfaces: List[Interface] = []
        self.scd: SopcComponentDescription = scd or SopcComponentDescription(class_name)

    # ------------------------------------------------------------------
    # Width hints — subclasses override to customise interface widths
    # ------------------------------------------------------------------

    def preferred_primary_width(
        self, iface_name: str, dt: SystemDataType, is_master: bool
    ) -> Optional[int]:
        return None

    def preferred_secondary_width(
        self, iface_name: str, dt: SystemDataType, is_master: bool
    ) -> Optional[int]:
        return None

    # ------------------------------------------------------------------
    # Interface management
    # ------------------------------------------------------------------

    def add_interface(self, intf: Interface) -> None:
        intf.owner = self
        self._interfaces.append(intf)

    def remove_interface(self, intf: Interface) -> None:
        self._interfaces.remove(intf)

    def get_interface_by_name(self, name: str) -> Optional[Interface]:
        nl = name.lower()
        for intf in self._interfaces:
            if intf.name.lower() == nl:
                return intf
        return None

    @property
    def interfaces(self) -> List[Interface]:
        return self._interfaces

    def get_interfaces(
        self,
        of_type: Optional[SystemDataType] = None,
        is_master: Optional[bool] = None,
    ) -> List[Interface]:
        return [
            i for i in self._interfaces
            if (of_type is None or i.type == of_type)
            and (is_master is None or i.is_master == is_master)
        ]

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def get_connections(
        self,
        of_type: Optional[SystemDataType] = None,
        is_master: Optional[bool] = None,
        to_component: Optional["BasicComponent"] = None,
    ) -> List["Connection"]:
        result = []
        for intf in self.get_interfaces(of_type, is_master):
            for conn in intf.connections:
                if to_component is None:
                    result.append(conn)
                elif intf.is_master and conn.slave_module == to_component:
                    result.append(conn)
                elif not intf.is_master and conn.master_module == to_component:
                    result.append(conn)
        return result

    # ------------------------------------------------------------------
    # Predicates
    # ------------------------------------------------------------------

    def has_memory_master(self) -> bool:
        return any(i.is_memory_master() for i in self._interfaces)

    def is_interrupt_master(self) -> bool:
        return any(i.is_irq_master() for i in self._interfaces)

    # ------------------------------------------------------------------
    # Clock rate
    # ------------------------------------------------------------------

    def get_clock_rate(self) -> int:
        for intf in self._interfaces:
            if intf.is_clock_slave() and intf.connections:
                cv = intf.connections[0].conn_value
                if cv:
                    # Flatten multi-cell clock value to a single int
                    result = 0
                    for v in cv:
                        result = (result << 32) | (v & 0xFFFFFFFF)
                    return result
        return 0

    # ------------------------------------------------------------------
    # System integration
    # ------------------------------------------------------------------

    def remove_from_system_if_possible(self, system: object) -> bool:
        """Subclasses (e.g. SICBridge) override to flatten themselves out."""
        return False

    # ------------------------------------------------------------------
    # DT generation — implemented in Phase 2
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> "DTNode":
        raise NotImplementedError("to_dt_node not yet implemented — Phase 2")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.instance_name!r}, {self.class_name!r})"
