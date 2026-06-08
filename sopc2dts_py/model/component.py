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
# SopcComponentDescription — port of sopc2dts.lib.components.SopcComponentDescription
# ---------------------------------------------------------------------------

class SICAutoParam:
    """
    A mapping from a sopcinfo parameter name to a DTS property name.
    Port of SopcComponentDescription.SICAutoParam (inner class in Java).
    """

    def __init__(
        self,
        dts_name: str,
        sopc_info_name: Optional[str],
        force_type: Optional[str],
        fixed_value: Optional[str] = None,
    ) -> None:
        self.dts_name = dts_name
        self.sopc_info_name = sopc_info_name
        self.force_type = force_type
        self.fixed_value = fixed_value

    def __repr__(self) -> str:
        return f"SICAutoParam({self.dts_name!r} <- {self.sopc_info_name!r})"


class SICRequiredParam:
    """
    A name/value pair that must be present on a component for an SCD to match.
    Port of SopcComponentDescription.SICRequiredParam (protected inner class).
    """

    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        return f"SICRequiredParam({self.name!r}={self.value!r})"


class TransparentInterfaceBridge:
    """
    Describes a master→slave interface pair that is transparent at bridge level.
    Port of SopcComponentDescription.TransparentInterfaceBridge (inner class).
    """

    def __init__(
        self,
        master: Optional[str] = None,
        slave: Optional[str] = None,
        data_type: Optional[SystemDataType] = None,
    ) -> None:
        self.master_intf_name = master
        self.slave_intf_name = slave
        self.type = data_type

    def __repr__(self) -> str:
        return f"TransparentInterfaceBridge({self.master_intf_name!r} -> {self.slave_intf_name!r})"


class SopcComponentDescription:
    """
    Describes a class of IP component: the compatible strings it generates,
    the sopcinfo parameters to emit as DTS properties, and required parameter
    constraints used for version disambiguation.

    Port of sopc2dts.lib.components.SopcComponentDescription.
    """

    def __init__(
        self,
        class_name: str,
        group: str = "unknown",
        vendor: str = "unknown",
        device: Optional[str] = None,
    ) -> None:
        # Java splits the classname on commas (multi-class entries in XML).
        # Keep the original string as `class_name` for backward compat with
        # existing code that accesses scd.class_name directly.
        self.class_name = class_name
        self.class_names: List[str] = [n.strip() for n in class_name.split(",")]
        self.group = group
        self.vendor = vendor
        self.device = device

        self._compatibles: List[str] = []
        self._auto_params: List[SICAutoParam] = []
        self._required_params: List[SICRequiredParam] = []
        self._compatible_versions: List[str] = []
        self._override_versions: List[str] = []
        self._transparent_bridges: List[TransparentInterfaceBridge] = []

    # ------------------------------------------------------------------
    # Mutation helpers (called by XML loader)
    # ------------------------------------------------------------------

    def add_compatible(self, compat: str) -> None:
        self._compatibles.append(compat)

    def add_auto_param(
        self,
        dts_name: str,
        sopc_name: Optional[str],
        force_type: Optional[str],
        fixed_value: Optional[str] = None,
    ) -> None:
        self._auto_params.append(SICAutoParam(dts_name, sopc_name, force_type, fixed_value))

    def add_required_param(self, name: str, value: str) -> None:
        self._required_params.append(SICRequiredParam(name, value))

    def add_compatible_version(self, version: str) -> None:
        self._compatible_versions.append(version)

    def add_override_version(self, version: str) -> None:
        self._override_versions.append(version)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def auto_params(self) -> List[SICAutoParam]:
        return self._auto_params

    def get_auto_params(self) -> List[SICAutoParam]:
        return self._auto_params

    def get_required_params(self) -> List[SICRequiredParam]:
        return self._required_params

    def get_transparent_bridges(self) -> List[TransparentInterfaceBridge]:
        return self._transparent_bridges

    def get_class_names(self) -> List[str]:
        return self.class_names

    # ------------------------------------------------------------------
    # Matching / version logic
    # ------------------------------------------------------------------

    def is_supporting_class_name(self, cn: str) -> bool:
        """Return True if this SCD handles the given IP class name."""
        cn_lower = cn.lower()
        return any(n.lower() == cn_lower for n in self.class_names)

    def is_required_params_ok(self, comp: "BasicComponent") -> bool:
        """True iff comp has all required param name/value pairs."""
        for rp in self._required_params:
            if comp.get_param_by_name(rp.name) is None:
                return False
            if not (comp.get_param_val_by_name(rp.name) or "").lower() == rp.value.lower():
                return False
        return True

    def is_overridden_version(self, version: str) -> bool:
        """True if this SCD overrides (replaces) the given component version."""
        for v in self._override_versions:
            if self.compare_versions(v, version) == 0:
                return True
        return False

    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """
        Numeric/lexicographic version comparison. Returns <0 if v1<v2,
        0 if equal, >0 if v1>v2. Port of SopcComponentDescription.compareVersions.
        """
        v1_parts = v1.split(".")
        v2_parts = v2.split(".")
        diff = 0
        for i in range(min(len(v1_parts), len(v2_parts))):
            if diff != 0:
                break
            try:
                diff = int(v2_parts[i], 0) - int(v1_parts[i], 0)
            except ValueError:
                a, b = v1_parts[i].lower(), v2_parts[i].lower()
                diff = (b > a) - (b < a)  # +1 if v2>v1, -1 if v1>v2, 0 if equal
        if diff == 0:
            diff = len(v2_parts) - len(v1_parts)
        if diff == 0:
            diff = len(v2) - len(v1)
        return diff

    def _get_compatible_version(self, version: str) -> Optional[str]:
        """
        Find the best backward-compatible version string, matching Java logic.
        Returns the lowest compatible version that is still >= the requested
        version, or None if the version is already listed or no compat exists.
        """
        compat: Optional[str] = None
        for bw in self._compatible_versions:
            if version.lower() == bw.lower():
                return None
            if compat is None or self.compare_versions(bw, compat) < 0:
                if self.compare_versions(bw, version) > 0:
                    compat = bw
        return compat

    def get_compatibles(self, version: Optional[str]) -> List[str]:
        """
        Build the ordered list of compatible strings for this component.
        Mirrors SopcComponentDescription.getCompatibles.
        """
        result: List[str] = []
        base = f"{self.vendor},{self.device}" if self.device else f"{self.vendor},unknown"
        if version is not None:
            result.append(f"{base}-{version}")
            bw = self._get_compatible_version(version)
            if bw is not None:
                result.append(f"{base}-{bw}")
        else:
            result.append(base)
        result.extend(self._compatibles)
        return result

    def get_compatible(self, version: Optional[str]) -> str:
        """Comma-quoted compatible string, e.g. '"altr,nios2-1.0", "altr,nios2"'."""
        return ",".join(f'"{c}"' for c in self.get_compatibles(version))

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def set_group(self, group: str) -> None:
        self.group = group

    def get_group(self) -> str:
        return self.group

    def get_vendor(self) -> str:
        return self.vendor

    def get_device(self) -> Optional[str]:
        return self.device

    def __repr__(self) -> str:
        return f"SopcComponentDescription({self.class_name!r}, group={self.group!r})"


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
    # DT generation helpers
    # ------------------------------------------------------------------

    def _get_addr_from_connection(self, conn: Optional["Connection"]) -> List[int]:
        """Port of BasicComponent.getAddrFromConnection."""
        if conn is None or conn.conn_value is None:
            return [0]
        return list(conn.conn_value)

    def _get_addr_from_connection_str(self, conn: Optional["Connection"]) -> str:
        """Port of BasicComponent.getAddrFromConnectionStr."""
        tmp = self._get_addr_from_connection(conn)
        if not tmp:
            return "0"
        res = format(tmp[0], 'x')          # first cell: no leading zeros
        for i in range(1, len(tmp)):
            res += f"{tmp[i]:08x}"         # subsequent cells: zero-padded
        return res

    def _get_reg(
        self,
        master: Optional["BasicComponent"],
        v_reg_names: List[str],
    ) -> List[int]:
        """Port of BasicComponent.getReg."""
        v_regs: List[int] = []
        for intf in self._interfaces:
            if not intf.is_memory_slave():
                continue
            conn = None
            for c in intf.connections:
                if master is None or c.master_module is master:
                    conn = c
                    break
            if conn is not None:
                v_regs.extend(self._get_addr_from_connection(conn))
                if intf.interface_value:
                    v_regs.extend(intf.interface_value)
                v_reg_names.append(intf.name)
        return v_regs

    def _get_interrupt_parent(
        self,
        intf: "Interface",
        board_info: object,
    ) -> Optional["BasicComponent"]:
        """Port of BasicComponent.getInterruptParent."""
        from ..log import logger
        irq_parent = None
        for c in intf.connections:
            master = c.master_module
            if master is not None and board_info.is_valid_irq_master(master):  # type: ignore[attr-defined]
                if irq_parent is None:
                    irq_parent = master
                else:
                    logger.warning(
                        "%s.%s: Multiple interrupt parents not supported. Using %s, not %s (%s)",
                        intf.owner.instance_name, intf.name,
                        irq_parent.instance_name,
                        master.instance_name, master.class_name,
                    )
        return irq_parent

    def _get_interrupts(
        self,
        v_irqs: List[int],
        board_info: object,
        v_irq_names: List[str],
    ) -> Optional["BasicComponent"]:
        """Port of BasicComponent.getInterrupts."""
        from ..log import logger
        irq_parent = None
        for intf in self._interfaces:
            if not intf.is_irq_slave():
                continue
            irqp = self._get_interrupt_parent(intf, board_info)
            if irqp is None:
                continue
            if irq_parent is None:
                irq_parent = irqp
            elif irq_parent is not irqp:
                logger.warning(
                    "%s: Multiple interrupt parents per component not supported.",
                    self.instance_name,
                )
            for c in intf.connections:
                if c.master_module is irq_parent:
                    if c.conn_value:
                        v_irqs.extend(c.conn_value)
                    v_irq_names.append(intf.name)
        return irq_parent

    def get_clock_master_ph(self, cm: "Interface") -> List["DTPropVal"]:
        """Port of BasicComponent.getClockMasterPH."""
        from .devicetree import DTPropPHandleVal, DTPropNumVal
        v_cms = self.get_interfaces(SystemDataType.CLOCK, True)
        phv = DTPropPHandleVal(self.instance_name)
        if len(v_cms) == 1:
            return [phv]
        for i, intf in enumerate(v_cms):
            if intf is cm:
                return [phv, DTPropNumVal(i)]
        return []

    def get_clocks_property(self) -> List["DTProperty"]:
        """Port of BasicComponent.getClocksProperty."""
        from .devicetree import DTProperty
        clock_slaves = self.get_interfaces(SystemDataType.CLOCK, False)
        if not clock_slaves:
            return []
        prop = DTProperty("clocks")
        v_names: List[str] = []
        for cs in clock_slaves:
            if not cs.connections:
                continue
            first_conn = cs.connections[0]
            mcomp = first_conn.master_module
            if mcomp is None:
                continue
            if mcomp.scd.group.lower() == "ignore":
                continue
            mi = first_conn.master_interface
            if mi is None:
                continue
            for phv in mcomp.get_clock_master_ph(mi):
                prop.add_value(phv)
            v_names.append(cs.name)
        if not v_names:
            return []
        result: List[DTProperty] = [prop]
        if len(v_names) > 1:
            result.append(DTProperty.from_strings("clock-names", v_names))
        return result

    def _create_fixed_prop(self, ap: "SICAutoParam") -> Optional["DTProperty"]:
        """Port of BasicComponent.createFixedProp."""
        from .devicetree import DTProperty
        if ap.fixed_value is None or ap.force_type is None:
            return None
        try:
            if ap.force_type.lower() == "unsigned":
                return DTProperty.from_long(ap.dts_name, int(ap.fixed_value))
            elif ap.force_type.lower() == "string":
                return DTProperty.from_string(ap.dts_name, ap.fixed_value)
        except (ValueError, TypeError):
            pass
        return None

    # ------------------------------------------------------------------
    # DT generation — main entry
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: Optional["Connection"]) -> "DTNode":
        """Full port of BasicComponent.toDTNode."""
        from .devicetree import (
            DTNode, DTProperty, DTPropPHandleVal, DTPropNumVal,
        )
        from .parameter import Parameter

        node = DTNode(
            self.scd.group + "@" + self._get_addr_from_connection_str(conn),
            label=self.instance_name,
        )

        grp = self.scd.group.lower()
        if grp in ("cpu", "memory"):
            node.add_property(DTProperty.from_string("device_type", grp))

        # compatible strings
        comp_prop_string = DTProperty.from_strings(
            "compatible", self.scd.get_compatibles(self.version)
        )
        node.add_property(comp_prop_string)

        # reg property
        v_reg_names: List[str] = []
        master = conn.master_module if conn is not None else None
        v_regs = self._get_reg(master, v_reg_names)
        if v_regs:
            p_reg = DTProperty("reg")
            p_reg.add_hex_values(v_regs)
            width = 2
            if conn is not None and conn.master_interface is not None:
                mi = conn.master_interface
                width = mi.primary_width + mi.secondary_width
            p_reg.set_num_values_per_row(width)
            node.add_property(p_reg)
            if len(v_reg_names) > 1 and node.get_property_by_name("reg-names") is None:
                node.add_property(DTProperty.from_strings("reg-names", v_reg_names))

        # interrupts
        v_irqs: List[int] = []
        v_irq_names: List[str] = []
        irq_parent = self._get_interrupts(v_irqs, board_info, v_irq_names)
        if irq_parent is not None:
            ip_prop = DTProperty("interrupt-parent")
            ip_prop.add_value(DTPropPHandleVal(irq_parent.instance_name))
            node.add_property(ip_prop)
            p_irq = DTProperty("interrupts")
            p_irq.add_number_values(v_irqs)
            node.add_property(p_irq)
            if len(v_irq_names) > 1:
                node.add_property(DTProperty.from_strings("interrupt-names", v_irq_names))

        # interrupt-controller
        if self.is_interrupt_master():
            node.add_property(DTProperty("interrupt-controller"))
            irq_masters = self.get_interfaces(SystemDataType.INTERRUPT, True)
            if irq_masters:
                node.add_property(
                    DTProperty.from_long(
                        "#interrupt-cells", irq_masters[0].get_primary_width()
                    )
                )

        # clocks
        if board_info.is_show_clock_tree():  # type: ignore[attr-defined]
            for clk_prop in self.get_clocks_property():
                node.add_property(clk_prop)

        # SCD auto-params
        v_param_todo = list(self._parameters)
        for ap in self.scd.get_auto_params():
            bp = self.get_param_by_name(ap.sopc_info_name or "")
            if bp is not None:
                dt = Parameter.data_type_by_name(ap.force_type)
                prop = bp.to_dt_property(ap.dts_name, dt)
                if prop is not None:
                    node.add_property(prop)
                try:
                    v_param_todo.remove(bp)
                except ValueError:
                    pass
            elif (ap.dts_name or "").lower() == "clock-frequency":
                node.add_property(DTProperty.from_long("clock-frequency", self.get_clock_rate()))
            elif (ap.dts_name or "").lower() == "regstep":
                node.add_property(DTProperty.from_long("regstep", 4))
            elif ap.fixed_value is not None:
                prop = self._create_fixed_prop(ap)
                if prop is not None:
                    node.add_property(prop)

        # embeddedsw / remaining params
        for bp in v_param_todo:
            ass_name: Optional[str] = bp.name
            if ass_name is None:
                continue
            if ass_name.lower() == self.EMBSW_DTS_COMPAT.lower():
                vals = bp.value.split()
                comp_prop_string.add_string_values(vals)
                ass_name = None
            elif ass_name.startswith(self.EMBSW_DTS_PARAMS):
                ass_name = ass_name[len(self.EMBSW_DTS_PARAMS):]
                prop = bp.to_dt_property(ass_name)
                if prop is not None:
                    node.add_property(prop, replace_existing=True)
                ass_name = None
            elif (ass_name.startswith(self.EMBSW_CMACRO)
                  and board_info.get_dump_parameters() != ParameterAction.NONE):  # type: ignore[attr-defined]
                ass_name = ass_name[len(self.EMBSW_CMACRO):]
            else:
                ass_name = None

            if ass_name is not None:
                ass_name = ass_name.replace('_', '-')
                prop = bp.to_dt_property(self.scd.vendor + ',' + ass_name)
                if prop is not None:
                    node.add_property(prop)

        return node

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.instance_name!r}, {self.class_name!r})"
