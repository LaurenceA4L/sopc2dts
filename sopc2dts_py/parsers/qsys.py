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
Port of sopc2dts.parsers.qsys.QSysSystemLoader.

The Java implementation used SAX with inline-attribute parsing.  This port
uses ElementTree.  The structure of a ``.qsys`` file differs from a
``.sopcinfo`` file in several ways:

- Root element is ``<system version="...">``; system name is derived from
  the *filename* (the ``$${FILE_NAME}`` macro).
- ``<interface>`` uses ``type=`` (not ``kind=``) and ``dir=`` (not
  ``direction=``), both as inline attributes.
- ``<parameter>`` values are always inline attributes — no child ``<value>``
  or ``<type>`` elements.
- Connection parameters (``baseAddress``, etc.) are child ``<parameter>``
  elements of the ``<connection>`` element.
- Unknown modules trigger a recursive sub-system load if a matching
  ``<kind>.qsys`` file exists in the same directory.
- After loading, ``flattenDesign()`` hoists sub-system components into the
  parent, prefixing their names with ``"<subsystem_name>-"``.

QSys XML structure (abbreviated)
---------------------------------
<system version="13.1">
    <parameter name="..." value="..."/>
    <module name="cpu_0" kind="altera_nios2_qsys" version="13.0">
        <parameter name="clockFrequency" value="50000000"/>
        <interface name="data_master" type="avalon" dir="start">
            <parameter name="width" value="32"/>
        </interface>
        <interface name="clk" type="clock" dir="end"/>
    </module>
    ...
    <connection kind="avalon" version="13.0"
                start="cpu_0.data_master" end="uart_0.s1">
        <parameter name="baseAddress" value="0x00000100"/>
    </connection>
    <connection kind="clock" ... start="clk_0.clk" end="cpu_0.clk"/>
</system>
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
from xml.etree import ElementTree as ET

from ..log import logger
from ..model.component import BasicComponent, Interface
from ..model.component_lib import SopcComponentLib
from ..model.connection import Connection
from ..model.enums import SystemDataType
from ..model.parameter import DataType, Parameter
from ..model.system import AvalonSystem


# ---------------------------------------------------------------------------
# QSysSubSystem — a component that also holds sub-components
# Mirrors QSysSystemLoader.QSysSubSystem in Java.
# ---------------------------------------------------------------------------

class _QSysSubSystem(BasicComponent):
    """
    A Platform Designer hierarchical sub-system.

    Acts as a BasicComponent (has interfaces that represent the subsystem
    boundary ports) AND as a mini-system (owns a list of sub-components).
    After loading, ``_flatten_design`` promotes those sub-components into the
    parent system.
    """

    def __init__(
        self,
        name: str,
        version: str,
        scd=None,
    ) -> None:
        super().__init__("qsys_subsystem", name, version, scd)
        self.sub_components: List[BasicComponent] = []

    def add_module(self, comp: BasicComponent) -> None:
        self.sub_components.append(comp)

    def get_component_by_name(self, name: str) -> Optional[BasicComponent]:
        nl = name.lower()
        for c in self.sub_components:
            if c.instance_name.lower() == nl:
                return c
        return None


# ---------------------------------------------------------------------------
# Interface type / direction mapping
# QSys uses "type" attribute (not "kind") and a simplified set of type names.
# Mirrors QSysSystemLoader.getSystemDataTypeByName.
# ---------------------------------------------------------------------------

def _qsys_type_to_sdt(type_name: str) -> SystemDataType:
    """
    Map a QSys interface/connection ``type`` attribute to a SystemDataType.
    Port of ``QSysSystemLoader.getSystemDataTypeByName``.
    """
    n = type_name.lower()
    if n == "avalon":
        return SystemDataType.MEMORY_MAPPED
    if n == "avalon_streaming":
        return SystemDataType.STREAMING
    if n == "clock":
        return SystemDataType.CLOCK
    if n == "reset":
        return SystemDataType.RESET
    return SystemDataType.CONDUIT


# ---------------------------------------------------------------------------
# Parameter parsing (qsys uses inline attribute form only)
# ---------------------------------------------------------------------------

def _parse_qsys_param(elem: ET.Element) -> Optional[Parameter]:
    """
    Parse a qsys ``<parameter name="..." value="..."/>`` element.
    QSys parameter values are treated as STRING (Java used DataType.STRING
    for all qsys parameters via getDataTypeFromValue — it just returned
    STRING unconditionally).
    """
    name = elem.get("name")
    value = elem.get("value", "")
    if not name:
        return None
    return Parameter(name, value, DataType.STRING)


# ---------------------------------------------------------------------------
# Address helpers (simplified port of DTHelper methods)
# ---------------------------------------------------------------------------

def _parse_address(raw: Optional[str], width: int) -> Optional[List[int]]:
    """
    Convert a hex/decimal string address into a list of ``width`` 32-bit
    cells (most-significant cell first).  Mirrors DTHelper.parseAddress4Conn
    and DTHelper.parseAddress4Intf for width-1 and wider addresses.
    """
    if not raw:
        return None
    try:
        val = int(raw, 0)
    except (ValueError, TypeError):
        logger.warning("Cannot parse address %r", raw)
        return None
    if width <= 0:
        width = 1
    cells = []
    for _ in range(width):
        cells.insert(0, val & 0xFFFF_FFFF)
        val >>= 32
    return cells


def _is_zero_or_none(arr: Optional[List[int]]) -> bool:
    """Return True if *arr* is None or consists entirely of zeros."""
    return arr is None or all(v == 0 for v in arr)


# ---------------------------------------------------------------------------
# Interface parsing
# ---------------------------------------------------------------------------

def _parse_qsys_interface(
    elem: ET.Element,
    owner: BasicComponent,
    hier_prefix: str = "",
) -> Optional[Interface]:
    """
    Parse one QSys ``<interface>`` element.

    ``type`` attribute  → SystemDataType via _qsys_type_to_sdt
    ``dir`` attribute   → is_master: "start" → True, else False
    ``internal`` attr   → stored as a STRING parameter (used for subsystem
                          boundary port routing during flattenDesign).
    """
    name = elem.get("name", "")
    type_str = elem.get("type", "conduit")
    dir_str = elem.get("dir", "end")

    data_type = _qsys_type_to_sdt(type_str)
    is_master = dir_str.lower() == "start"

    intf = Interface(name, data_type, is_master, owner)

    # Subsystem boundary ports carry an "internal" reference attribute that
    # maps this boundary port to an internal component.interface.
    internal = elem.get("internal")
    if internal is not None:
        intf.add_param(Parameter("internal", internal, DataType.STRING))

    # Child parameter elements
    for child in elem:
        if child.tag == "parameter":
            p = _parse_qsys_param(child)
            if p:
                intf.add_param(p)

    return intf


# ---------------------------------------------------------------------------
# Module parsing
# ---------------------------------------------------------------------------

def _parse_qsys_module(
    elem: ET.Element,
    lib: SopcComponentLib,
    source_dir: Path,
    parent_name: str,
    hier_prefix: str,
    depth: int = 0,
) -> Optional[BasicComponent]:
    """
    Parse one QSys ``<module>`` element.

    If the module's kind is unknown to the component library AND a matching
    ``<kind>.qsys`` file exists next to *source_dir*, the module is loaded
    recursively as a :class:`_QSysSubSystem`.  This mirrors the Java
    ``QSysSystemLoader.startElement("module")`` subsystem-loading path.
    """
    kind = elem.get("kind", "")
    name = elem.get("name", "")
    version = elem.get("version", "")

    if not name:
        logger.warning("QSys module element missing name — skipping")
        return None

    full_name = hier_prefix + name if hier_prefix else name
    comp = lib.get_component_for_class(kind, full_name, version)

    # Check if this is an unknown component that might be a sub-system.
    # Java: if(currModule.getScd() instanceof SICUnknown) { try .qsys file }
    # Python: we approximate "unknown" as "no device in SCD".
    # TODO (Component handlers phase): use isinstance(comp.scd, SICUnknown).
    sub_qsys = source_dir / f"{kind}.qsys"
    if comp.scd.device is None and sub_qsys.exists() and depth < 8:
        try:
            logger.debug("Loading sub-system %s from %s", name, sub_qsys)
            sub = _load_subsystem(sub_qsys, name, lib, depth + 1)
            if sub is not None:
                comp = sub
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load sub-system %s: %s", sub_qsys, exc)

    # Module-level parameters
    for child in elem:
        if child.tag == "parameter":
            p = _parse_qsys_param(child)
            if p:
                comp.add_param(p)

    # Interface elements
    for child in elem:
        if child.tag == "interface":
            # For SUBSYSTEM_RELOAD the Java reuses existing interfaces;
            # for plain load we create all interfaces fresh.
            existing = comp.get_interface_by_name(child.get("name", ""))
            if existing is None:
                intf = _parse_qsys_interface(child, comp, hier_prefix)
                if intf:
                    comp.add_interface(intf)
            else:
                # Subsystem-reload: update "internal" param if present
                internal = child.get("internal")
                if internal is not None:
                    existing.add_param(Parameter("internal", internal, DataType.STRING))

    return comp


# ---------------------------------------------------------------------------
# Subsystem loading
# ---------------------------------------------------------------------------

def _load_subsystem(
    path: Path,
    name: str,
    lib: SopcComponentLib,
    depth: int = 0,
) -> Optional[_QSysSubSystem]:
    """
    Load a ``.qsys`` file as a :class:`_QSysSubSystem`.
    Mirrors ``QSysSystemLoader.loadSubSystem``.
    """
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag.lower() != "system":
        logger.warning("Sub-system %s: expected <system>, got <%s>", path, root.tag)
        return None

    version = root.get("version", "unknown")
    sub = _QSysSubSystem(name, version)

    # System-level parameters
    for child in root:
        if child.tag == "parameter":
            p = _parse_qsys_param(child)
            if p:
                sub.add_param(p)

    # Interfaces (boundary ports) on the subsystem component itself
    for child in root:
        if child.tag == "interface":
            intf = _parse_qsys_interface(child, sub)
            if intf:
                sub.add_interface(intf)

    source_dir = path.parent

    # Sub-components (modules inside the subsystem)
    for child in root:
        if child.tag == "module":
            comp = _parse_qsys_module(child, lib, source_dir, name, "", depth)
            if comp:
                sub.add_module(comp)

    # Connections between sub-components
    for child in root:
        if child.tag == "connection":
            _parse_qsys_connection(child, sub)

    return sub


# ---------------------------------------------------------------------------
# Connection parsing
# ---------------------------------------------------------------------------

def _get_component_from_ref(
    ref_name: str,
    system: "AvalonSystem | _QSysSubSystem",
    hier_prefix: str,
) -> Optional[BasicComponent]:
    """
    Look up a component from a connection start/end component-name.
    For the top-level system: the component name is prefixed by hier_prefix.
    For subsystems: search within the sub-system's components directly.
    """
    if isinstance(system, _QSysSubSystem):
        return system.get_component_by_name(ref_name)
    return system.get_component_by_name(hier_prefix + ref_name)


def _parse_qsys_connection(
    elem: ET.Element,
    context: "AvalonSystem | _QSysSubSystem",
    hier_prefix: str = "",
) -> None:
    """
    Parse one QSys ``<connection>`` element and wire it into *context*.
    Mirrors the ``startElement("connection")`` + ``endElement("connection")``
    logic from QSysSystemLoader.
    """
    kind = elem.get("kind", "").lower()
    start = elem.get("start", "")   # "comp.intf"
    end = elem.get("end", "")       # "comp.intf"

    if not start or not end:
        return

    start_dot = start.find(".")
    end_dot = end.find(".")
    if start_dot < 0 or end_dot < 0:
        logger.warning("Malformed QSys connection start=%r end=%r", start, end)
        return

    master_comp_name = start[:start_dot]
    master_intf_name = start[start_dot + 1:]
    slave_comp_name = end[:end_dot]
    slave_intf_name = end[end_dot + 1:]

    master_comp = _get_component_from_ref(master_comp_name, context, hier_prefix)
    slave_comp = _get_component_from_ref(slave_comp_name, context, hier_prefix)

    if master_comp is None or slave_comp is None:
        logger.warning(
            "Cannot find components for QSys connection %s → %s", start, end
        )
        return

    dt = _qsys_type_to_sdt(kind if kind else elem.get("kind", ""))

    # Resolve interfaces; create them on-the-fly if missing (matches Java behaviour).
    master_intf = master_comp.get_interface_by_name(master_intf_name)
    if master_intf is None:
        master_intf = Interface(master_intf_name, dt, True, master_comp)
        master_comp.add_interface(master_intf)
        logger.debug("Invented master interface: %s.%s", master_comp_name, master_intf_name)

    slave_intf = slave_comp.get_interface_by_name(slave_intf_name)
    if slave_intf is None:
        slave_intf = Interface(slave_intf_name, dt, False, slave_comp)
        slave_comp.add_interface(slave_intf)
        logger.debug("Invented slave interface: %s.%s", slave_comp_name, slave_intf_name)

    conn = Connection(master_intf, slave_intf, dt, connect=True)

    # For CLOCK connections, set the interface value from the master component's
    # clockFrequency parameter if the interface has no value yet.
    if dt == SystemDataType.CLOCK:
        if _is_zero_or_none(master_intf.interface_value):
            clock_rate_str = master_comp.get_param_val_by_name("clockFrequency")
            if clock_rate_str:
                addr = _parse_address(clock_rate_str, master_intf.get_secondary_width())
                if addr:
                    master_intf.interface_value = addr
        conn.conn_value = master_intf.interface_value

    # Collect child parameters so endElement logic can set baseAddress.
    for child in elem:
        if child.tag == "parameter":
            p = _parse_qsys_param(child)
            if p:
                conn.add_param(p)

    # MEMORY_MAPPED: set baseAddress as conn_value (mirrors endElement in Java).
    if dt == SystemDataType.MEMORY_MAPPED:
        base_raw = conn.get_param_val_by_name("baseAddress")
        if base_raw:
            addr = _parse_address(base_raw, master_intf.get_primary_width())
            if addr:
                conn.conn_value = addr


# ---------------------------------------------------------------------------
# flattenDesign
# ---------------------------------------------------------------------------

def _flatten_design(system: AvalonSystem) -> None:
    """
    Promote sub-components from each :class:`_QSysSubSystem` into *system*,
    re-routing boundary interfaces to the appropriate internal components.
    Port of ``QSysSystemLoader.flattenDesign``.
    """
    i = 0
    while i < len(system.components):
        comp = system.components[i]
        if not isinstance(comp, _QSysSubSystem):
            i += 1
            continue

        sub: _QSysSubSystem = comp
        logger.info("Flattening QSys subsystem %r", sub.instance_name)

        # Re-route boundary interfaces to their internal targets.
        while sub.interfaces:
            intf = sub.interfaces[0]
            internal_ref = intf.get_param_val_by_name("internal")
            if internal_ref is None:
                logger.warning(
                    "Subsystem %s boundary interface %s has no 'internal' param",
                    sub.instance_name, intf.name,
                )
                sub.interfaces.pop(0)
                continue

            ref_parts = internal_ref.split(".", 1)
            internal_comp = sub.get_component_by_name(ref_parts[0]) if ref_parts else None
            internal_intf = (
                internal_comp.get_interface_by_name(ref_parts[1])
                if (internal_comp and len(ref_parts) > 1)
                else None
            )

            if internal_intf is None:
                # No matching internal interface — move the boundary interface
                # directly onto the internal component (Java fallback path).
                if internal_comp:
                    internal_comp.add_interface(intf)
                    intf.owner = internal_comp
            else:
                # Rewire all connections from the boundary interface to the
                # internal interface.
                while intf.connections:
                    intf.connections[0].connect(internal_intf)

            sub.interfaces.pop(0)

        # Rename and promote sub-components.
        for sub_comp in sub.sub_components:
            sub_comp.instance_name = f"{sub.instance_name}-{sub_comp.instance_name}"
            system.add_component(sub_comp)
        sub.sub_components.clear()

        # Remove the now-empty subsystem component.
        system.remove_component(sub)
        # Do not advance i — the next component has shifted into position i.


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_system(
    source: "str | Path",
    component_lib: Optional[SopcComponentLib] = None,
) -> AvalonSystem:
    """
    Parse a ``.qsys`` (Platform Designer) file and return an
    :class:`~sopc2dts_py.model.system.AvalonSystem`.

    Parameters
    ----------
    source:
        Path to the ``.qsys`` file.
    component_lib:
        The component library to use.  Defaults to the process-wide singleton.
    """
    source = Path(source)
    lib = component_lib or SopcComponentLib.get_instance()

    logger.info("Loading qsys: %s", source)
    tree = ET.parse(source)
    root = tree.getroot()

    if root.tag.lower() != "system":
        raise ValueError(
            f"Expected <system> root element, got <{root.tag}> in {source}"
        )

    # System name = filename without extension (mirrors $${FILE_NAME} macro).
    name = source.stem
    version = root.get("version", "unknown")
    source_dir = source.parent

    system = AvalonSystem(name, version, source)
    system.set_version(version)

    # System-level parameters
    for child in root:
        if child.tag == "parameter":
            p = _parse_qsys_param(child)
            if p:
                system.add_component  # not used for system params; skip for now

    # --- Modules → components ---
    for child in root:
        if child.tag == "module":
            comp = _parse_qsys_module(child, lib, source_dir, name, "")
            if comp is not None:
                system.add_component(comp)

    logger.debug("Parsed %d components (pre-flatten)", len(system.components))

    # --- Connections ---
    for child in root:
        if child.tag == "connection":
            _parse_qsys_connection(child, system, "")

    # --- Post-parse ---
    system.recheck_components()

    # --- Flatten hierarchical sub-systems ---
    _flatten_design(system)

    logger.info(
        "Loaded QSys system %r: %d components", system.name, len(system.components)
    )
    return system
