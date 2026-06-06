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
Port of sopc2dts.parsers.sopcinfo.SopcInfoSystemLoader (and its helpers
SopcInfoComponent, SopcInfoInterface, SopcInfoConnection,
SopcInfoAssignment, SopcInfoParameter).

The Java implementation used SAX with a ContentHandler-swapping pattern
(each element redirected the XMLReader to a fresh handler).  Here we
parse the whole tree with ElementTree and walk it once, producing the
same data model.

Sopcinfo XML structure
----------------------
<EnsembleReport name="..." quartusVersion="...">
    <module name="uart_0" kind="altera_avalon_uart" version="13.0">
        <parameter name="clockRate" value="50000000"/>
        <assignment name="embeddedsw.CMacro.BAUD" value="115200"/>
        <interface name="s1" kind="avalon_slave" direction="end">
            <parameter name="addressableSize" value="32"/>
            <assignment .../>
        </interface>
        <interface name="irq" kind="interrupt_sender" direction="start"/>
    </module>
    ...
    <connection kind="avalon" version="13.0"
                start="cpu_0.data_master" end="uart_0.s1">
        <parameter name="baseAddress" value="0x00000100"/>
    </connection>
    <connection kind="clock" ...  start="clk_0.clk" end="uart_0.clk">
        <parameter name="clockRate" value="50000000"/>
    </connection>
    <connection kind="interrupt" ... start="cpu_0.d32" end="uart_0.irq">
        <parameter name="irqNumber" value="0"/>
    </connection>
</EnsembleReport>
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple
from xml.etree import ElementTree as ET

from ..log import logger
from ..model.component import BasicComponent, Interface
from ..model.component_lib import SopcComponentLib
from ..model.connection import Connection
from ..model.enums import SystemDataType
from ..model.parameter import DataType, Parameter
from ..model.system import AvalonSystem

# ---------------------------------------------------------------------------
# Interface kind → (SystemDataType, is_master) mapping
# Mirrors SopcInfoInterface.startElement kind dispatch in Java.
# ---------------------------------------------------------------------------

_INTF_KIND_MAP: dict[str, Tuple[SystemDataType, bool]] = {
    "avalon_master":                    (SystemDataType.MEMORY_MAPPED,       True),
    "avalon_slave":                     (SystemDataType.MEMORY_MAPPED,       False),
    "interrupt_sender":                 (SystemDataType.INTERRUPT,            True),
    "interrupt_receiver":               (SystemDataType.INTERRUPT,            False),
    "clock_source":                     (SystemDataType.CLOCK,                True),
    "clock_sink":                       (SystemDataType.CLOCK,                False),
    "reset_source":                     (SystemDataType.RESET,                True),
    "reset_sink":                       (SystemDataType.RESET,                False),
    "avalon_streaming_source":          (SystemDataType.STREAMING,            True),
    "avalon_streaming_sink":            (SystemDataType.STREAMING,            False),
    "nios_custom_instruction_master":   (SystemDataType.CUSTOM_INSTRUCTION,   True),
    "nios_custom_instruction_slave":    (SystemDataType.CUSTOM_INSTRUCTION,   False),
    # conduit_end direction is resolved from the XML "direction" attribute
    "conduit_end":                      (SystemDataType.CONDUIT,              False),  # placeholder
    "conduit_master":                   (SystemDataType.CONDUIT,              True),
    "conduit_slave":                    (SystemDataType.CONDUIT,              False),
}

# Connection kind → SystemDataType
_CONN_KIND_MAP: dict[str, Optional[SystemDataType]] = {
    "avalon":            SystemDataType.MEMORY_MAPPED,
    "clock":             SystemDataType.CLOCK,
    "interrupt":         SystemDataType.INTERRUPT,
    "reset":             None,   # explicitly ignored (no DTS output)
    "avalon_streaming":  SystemDataType.STREAMING,
    "conduit":           SystemDataType.CONDUIT,
}

# Regex to strip C-literal integer suffixes: u, ul, ull, UL, ULL, etc.
_C_SUFFIX_RE = re.compile(r'[uU][lL]{0,2}$')


# ---------------------------------------------------------------------------
# Low-level value helpers
# ---------------------------------------------------------------------------

def _strip_c_suffix(value: str) -> str:
    """Remove trailing C integer literal suffix (u/ul/ull and variants)."""
    return _C_SUFFIX_RE.sub("", value.strip())


def _infer_type(raw: str) -> DataType:
    """
    Infer DataType from a raw string value — mirrors SopcInfoAssignment type
    inference logic (no explicit <type> element present).

    Rules (in order):
      empty string → BOOLEAN
      starts with 0x / 0X → NUMBER
      all digits (after suffix strip) → NUMBER
      otherwise → STRING
    """
    v = _strip_c_suffix(raw)
    if not v:
        return DataType.BOOLEAN
    if v.startswith(("0x", "0X")):
        return DataType.NUMBER
    try:
        int(v)
        return DataType.NUMBER
    except ValueError:
        return DataType.STRING


def _coerce_value(raw: str, dt: DataType) -> str:
    """
    Normalise the value string for storage in a Parameter.
    For NUMBER types, strip the C suffix so int(..., 0) works later.
    """
    if dt == DataType.NUMBER:
        return _strip_c_suffix(raw)
    return raw


# ---------------------------------------------------------------------------
# Parameter / assignment parsing
# ---------------------------------------------------------------------------

def _parse_param_elem(elem: ET.Element) -> Optional[Parameter]:
    """
    Parse a <parameter> or <assignment> element into a Parameter.

    Both formats are supported:
      Attribute form:  <parameter name="foo" value="bar"/>
      Element form:    <parameter>
                           <name>foo</name>
                           <value>bar</value>
                           <type>NUMBER</type>   <!-- optional -->
                       </parameter>
    """
    # Prefer attribute form; fall back to child elements.
    name = elem.get("name")
    if name is None:
        name_elem = elem.find("name")
        name = name_elem.text.strip() if (name_elem is not None and name_elem.text) else None
    if not name:
        return None

    value_attr = elem.get("value")
    if value_attr is not None:
        raw_value = value_attr
    else:
        val_elem = elem.find("value")
        raw_value = (val_elem.text or "") if val_elem is not None else ""

    # Explicit <type> element (present in <parameter>, absent in <assignment>)
    type_elem = elem.find("type")
    if type_elem is not None and type_elem.text:
        dt = Parameter.data_type_by_name(type_elem.text.strip()) or _infer_type(raw_value)
    else:
        dt = _infer_type(raw_value)

    value = _coerce_value(raw_value, dt)
    return Parameter(name, value, dt)


# ---------------------------------------------------------------------------
# Interface parsing
# ---------------------------------------------------------------------------

def _kind_to_type_and_master(kind: str, direction: str) -> Optional[Tuple[SystemDataType, bool]]:
    """
    Map an interface kind (and optional direction attribute) to
    (SystemDataType, is_master).

    For ``conduit_end`` the direction attribute ("start" = source/master,
    "end" = sink/slave) determines is_master.
    """
    entry = _INTF_KIND_MAP.get(kind.lower())
    if entry is None:
        return None
    data_type, is_master = entry
    if kind.lower() == "conduit_end":
        is_master = direction.lower() == "start"
    return data_type, is_master


def _parse_interface(elem: ET.Element, owner: BasicComponent) -> Optional[Interface]:
    """Parse one <interface> element into an Interface attached to *owner*."""
    name = elem.get("name", "")
    kind = elem.get("kind", "")
    direction = elem.get("direction", "end")

    mapping = _kind_to_type_and_master(kind, direction)
    if mapping is None:
        logger.debug("Ignoring unknown interface kind %r on %s", kind, owner.instance_name)
        return None

    data_type, is_master = mapping
    intf = Interface(name, data_type, is_master, owner)

    # Parse child parameters and assignments
    for child in elem:
        if child.tag in ("parameter", "assignment"):
            param = _parse_param_elem(child)
            if param:
                intf.add_param(param)

    # Set addressable size as interface_value (MEMORY_MAPPED slave interfaces only).
    # This is later used by the DTS generator to emit the `reg` size cell.
    # Mirrors SopcInfoInterface.endElement("interface") in Java.
    if data_type == SystemDataType.MEMORY_MAPPED and not is_master:
        addr_p = intf.get_param_by_name("addressableSize")
        if addr_p:
            try:
                intf.interface_value = [int(addr_p.value, 0)]
            except (ValueError, TypeError):
                logger.warning(
                    "Cannot parse addressableSize %r on %s.%s",
                    addr_p.value, owner.instance_name, name,
                )

    return intf


# ---------------------------------------------------------------------------
# Module (component) parsing
# ---------------------------------------------------------------------------

def _parse_module(
    elem: ET.Element,
    lib: SopcComponentLib,
) -> Optional[BasicComponent]:
    """Parse one <module> element into a BasicComponent."""
    kind = elem.get("kind", "")
    name = elem.get("name", "")
    version = elem.get("version", "")

    if not name:
        logger.warning("Module element missing name attribute — skipping")
        return None

    comp = lib.get_component_for_class(kind, name, version)

    for child in elem:
        if child.tag in ("parameter", "assignment"):
            param = _parse_param_elem(child)
            if param:
                comp.add_param(param)
        elif child.tag == "interface":
            intf = _parse_interface(child, comp)
            if intf:
                comp.add_interface(intf)

    return comp


# ---------------------------------------------------------------------------
# Connection resolution
# ---------------------------------------------------------------------------

def _resolve_intf(
    ref: str,
    system: AvalonSystem,
) -> Tuple[Optional[BasicComponent], Optional[Interface]]:
    """
    Resolve a "module_name.interface_name" reference string to a
    (BasicComponent, Interface) pair.  Returns (None, None) on failure.
    """
    dot = ref.find(".")
    if dot < 0:
        logger.warning("Cannot parse interface reference %r (no dot)", ref)
        return None, None
    comp_name = ref[:dot]
    intf_name = ref[dot + 1:]
    comp = system.get_component_by_name(comp_name)
    if comp is None:
        logger.warning("Connection references unknown component %r", comp_name)
        return None, None
    intf = comp.get_interface_by_name(intf_name)
    if intf is None:
        logger.warning(
            "Connection references unknown interface %r on %r",
            intf_name, comp_name,
        )
        return None, None
    return comp, intf


def _parse_connection(elem: ET.Element, system: AvalonSystem) -> None:
    """
    Parse one <connection> element and wire it into the system.
    Mirrors SopcInfoConnection + connectComponents() from Java.
    """
    kind = elem.get("kind", "").lower()
    start = elem.get("start", "")   # master side: "comp.intf"
    end = elem.get("end", "")       # slave side:  "comp.intf"

    # Reset connections carry no DTS information — skip them.
    if kind == "reset":
        return

    conn_type = _CONN_KIND_MAP.get(kind)
    if conn_type is None:
        logger.debug("Ignoring connection of unrecognised kind %r (%s→%s)", kind, start, end)
        return

    _master_comp, master_intf = _resolve_intf(start, system)
    _slave_comp, slave_intf = _resolve_intf(end, system)

    if master_intf is None or slave_intf is None:
        return  # warning already logged by _resolve_intf

    # Collect connection-level parameters (baseAddress, clockRate, irqNumber)
    conn_params: dict[str, Parameter] = {}
    for child in elem:
        if child.tag in ("parameter", "assignment"):
            p = _parse_param_elem(child)
            if p:
                conn_params[p.name.lower()] = p

    # Build and register the Connection.
    # connect=True appends it to both interfaces' connection lists.
    conn = Connection(master_intf, slave_intf, conn_type, connect=True)

    # Set the connection value (used by the DTS generator for addresses / IRQs).
    # We assign conn_value directly rather than through set_conn_value to avoid
    # width checks during parse — the widths are updated later in recheck_components.
    if conn_type == SystemDataType.MEMORY_MAPPED:
        bp = conn_params.get("baseaddress")
        if bp:
            try:
                conn.conn_value = [int(bp.value, 0)]
            except (ValueError, TypeError):
                logger.warning("Cannot parse baseAddress %r for %s→%s", bp.value, start, end)

    elif conn_type == SystemDataType.CLOCK:
        # The clock rate is stored both as the connection value and on the
        # master interface as interface_value (so slaves can read it via
        # get_clock_rate() without following the connection object).
        rp = conn_params.get("clockrate")
        if rp:
            try:
                rate = int(rp.value, 0)
                conn.conn_value = [rate]
                if master_intf.interface_value is None:
                    master_intf.interface_value = [rate]
            except (ValueError, TypeError):
                logger.warning("Cannot parse clockRate %r for %s→%s", rp.value, start, end)

    elif conn_type == SystemDataType.INTERRUPT:
        ip = conn_params.get("irqnumber")
        if ip:
            try:
                conn.conn_value = [int(ip.value, 0)]
            except (ValueError, TypeError):
                logger.warning("Cannot parse irqNumber %r for %s→%s", ip.value, start, end)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_system(
    source: "str | Path",
    component_lib: Optional[SopcComponentLib] = None,
) -> AvalonSystem:
    """
    Parse a ``.sopcinfo`` (EnsembleReport) file and return an
    :class:`~sopc2dts_py.model.system.AvalonSystem`.

    Parameters
    ----------
    source:
        Path to the ``.sopcinfo`` file.
    component_lib:
        The :class:`~sopc2dts_py.model.component_lib.SopcComponentLib` to use
        for component lookup.  Defaults to the process-wide singleton.

    Raises
    ------
    ValueError
        If the root element is not ``EnsembleReport``.
    ET.ParseError
        If the XML is malformed.
    """
    source = Path(source)
    lib = component_lib or SopcComponentLib.get_instance()

    logger.info("Loading sopcinfo: %s", source)
    tree = ET.parse(source)
    root = tree.getroot()

    if root.tag != "EnsembleReport":
        raise ValueError(
            f"Expected <EnsembleReport> root element, got <{root.tag}> "
            f"in {source}"
        )

    name = root.get("name", source.stem)
    version = root.get("quartusVersion", "unknown")

    system = AvalonSystem(name, version, source)
    system.set_version(version)

    # --- Parse modules → components ---
    for mod_elem in root.findall("module"):
        comp = _parse_module(mod_elem, lib)
        if comp is not None:
            system.add_component(comp)

    logger.debug("Parsed %d components", len(system.components))

    # --- Wire connections ---
    for conn_elem in root.findall("connection"):
        _parse_connection(conn_elem, system)

    # --- Post-parse validation ---
    system.recheck_components()

    logger.info(
        "Loaded system %r: %d components", system.name, len(system.components)
    )
    return system
