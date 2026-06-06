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
Port of sopc2dts.parsers.sopcinfo.SopcInfoSystemLoader (and helpers).

The Java implementation used SAX with ContentHandler-swapping.  Here we
parse the whole tree with ElementTree and walk it once.

Real sopcinfo XML structure
---------------------------
<EnsembleReport name="..." version="13.1">
    <reportVersion>13.1</reportVersion>          <!-- optional override -->
    <module name="uart_0" kind="altera_avalon_uart" version="13.0">
        <interface name="s1" kind="avalon_slave" direction="end">
            <parameter name="addressSpan" value="32"/>
        </interface>
        <interface name="clk" kind="clock_source" direction="start">
            <parameter name="clockRate" value="50000000"/>
        </interface>
        <interface name="irq" kind="interrupt_sender" direction="start"/>
    </module>
    <!-- Connections route via TEXT child elements, NOT start=/end= attrs -->
    <connection kind="avalon" version="13.0">
        <startModule>cpu_0</startModule>
        <startConnectionPoint>data_master</startConnectionPoint>
        <endModule>uart_0</endModule>
        <endConnectionPoint>s1</endConnectionPoint>
        <parameter name="baseAddress" value="0x00000100"/>
    </connection>
    <connection kind="clock" version="13.0">
        <startModule>clk_0</startModule>
        <startConnectionPoint>clk</startConnectionPoint>
        <endModule>uart_0</endModule>
        <endConnectionPoint>clk</endConnectionPoint>
    </connection>
    <connection kind="interrupt" version="13.0">
        <startModule>uart_0</startModule>
        <startConnectionPoint>irq</startConnectionPoint>
        <endModule>cpu_0</endModule>
        <endConnectionPoint>d32</endConnectionPoint>
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
# Interface kind map  (mirrors SopcInfoInterface.setKind in Java)
# ---------------------------------------------------------------------------

_INTF_KIND_MAP: dict[str, Tuple[SystemDataType, bool]] = {
    # Memory-mapped masters
    "avalon_master":                    (SystemDataType.MEMORY_MAPPED,       True),
    "avalon_tristate_master":           (SystemDataType.MEMORY_MAPPED,       True),
    "tristate_conduit_master":          (SystemDataType.MEMORY_MAPPED,       True),
    "altera_axi_master":                (SystemDataType.MEMORY_MAPPED,       True),
    "altera_axi4_master":               (SystemDataType.MEMORY_MAPPED,       True),
    "apb_master":                       (SystemDataType.MEMORY_MAPPED,       True),
    "axi4_master":                      (SystemDataType.MEMORY_MAPPED,       True),
    "axi4lite_master":                  (SystemDataType.MEMORY_MAPPED,       True),
    # Memory-mapped slaves
    "avalon_slave":                     (SystemDataType.MEMORY_MAPPED,       False),
    "avalon_tristate_slave":            (SystemDataType.MEMORY_MAPPED,       False),
    "tristate_conduit_slave":           (SystemDataType.MEMORY_MAPPED,       False),
    "altera_axi_slave":                 (SystemDataType.MEMORY_MAPPED,       False),
    "altera_axi4_slave":                (SystemDataType.MEMORY_MAPPED,       False),
    "altera_axi4lite_slave":            (SystemDataType.MEMORY_MAPPED,       False),
    "axi4_slave":                       (SystemDataType.MEMORY_MAPPED,       False),
    "axi4lite_slave":                   (SystemDataType.MEMORY_MAPPED,       False),
    "apb_slave":                        (SystemDataType.MEMORY_MAPPED,       False),
    "ahb_slave":                        (SystemDataType.MEMORY_MAPPED,       False),
    # Interrupts: Java interrupt_receiver->isMaster=True, sender->False
    "interrupt_sender":                 (SystemDataType.INTERRUPT,            False),
    "interrupt_receiver":               (SystemDataType.INTERRUPT,            True),
    # Clock
    "clock_source":                     (SystemDataType.CLOCK,                True),
    "clock_sink":                       (SystemDataType.CLOCK,                False),
    # Reset
    "reset_source":                     (SystemDataType.RESET,                True),
    "reset_sink":                       (SystemDataType.RESET,                False),
    # Streaming
    "avalon_streaming_source":          (SystemDataType.STREAMING,            True),
    "avalon_streaming_sink":            (SystemDataType.STREAMING,            False),
    # Custom instruction
    "nios_custom_instruction_master":   (SystemDataType.CUSTOM_INSTRUCTION,   True),
    "nios_custom_instruction_slave":    (SystemDataType.CUSTOM_INSTRUCTION,   False),
    # Conduit: all variants -> isMaster=False per Java
    "conduit":                          (SystemDataType.CONDUIT,              False),
    "conduit_start":                    (SystemDataType.CONDUIT,              False),
    "conduit_end":                      (SystemDataType.CONDUIT,              False),
}

# Connection kind map  (None = skip, no DTS output)
_CONN_KIND_MAP: dict[str, Optional[SystemDataType]] = {
    "avalon":            SystemDataType.MEMORY_MAPPED,
    "avalon_tristate":   SystemDataType.MEMORY_MAPPED,
    "tristate_conduit":  SystemDataType.MEMORY_MAPPED,
    "clock":             SystemDataType.CLOCK,
    "interrupt":         SystemDataType.INTERRUPT,
    "reset":             None,
    "avalon_streaming":  SystemDataType.STREAMING,
    "conduit":           SystemDataType.CONDUIT,
}

_C_SUFFIX_RE = re.compile(r'[uU][lL]{0,2}$')


def _strip_c_suffix(value: str) -> str:
    return _C_SUFFIX_RE.sub("", value.strip())


def _infer_type(raw: str) -> DataType:
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
    if dt == DataType.NUMBER:
        return _strip_c_suffix(raw)
    return raw


def _parse_param_elem(elem: ET.Element) -> Optional[Parameter]:
    """Parse <parameter> or <assignment> (attribute or element form)."""
    name = elem.get("name")
    if name is None:
        ne = elem.find("name")
        name = ne.text.strip() if (ne is not None and ne.text) else None
    if not name:
        return None
    value_attr = elem.get("value")
    if value_attr is not None:
        raw_value = value_attr
    else:
        ve = elem.find("value")
        raw_value = (ve.text or "") if ve is not None else ""
    te = elem.find("type")
    if te is not None and te.text:
        dt = Parameter.data_type_by_name(te.text.strip()) or _infer_type(raw_value)
    else:
        dt = _infer_type(raw_value)
    return Parameter(name, _coerce_value(raw_value, dt), dt)


def _kind_to_type_and_master(kind: str, direction: str) -> Optional[Tuple[SystemDataType, bool]]:
    """Map interface kind -> (SystemDataType, is_master).  Mirrors SopcInfoInterface.setKind."""
    return _INTF_KIND_MAP.get(kind.lower())


def _parse_interface(elem: ET.Element, owner: BasicComponent) -> Optional[Interface]:
    """Parse one <interface> element."""
    name = elem.get("name", "")
    kind = elem.get("kind", "")
    direction = elem.get("direction", "end")
    mapping = _kind_to_type_and_master(kind, direction)
    if mapping is None:
        logger.debug("Ignoring unknown interface kind %r on %s", kind, owner.instance_name)
        return None
    data_type, is_master = mapping
    intf = Interface(name, data_type, is_master, owner)
    for child in elem:
        if child.tag in ("parameter", "assignment"):
            p = _parse_param_elem(child)
            if p:
                intf.add_param(p)
    # Set interface_value -- mirrors SopcInfoInterface.endElement in Java.
    if data_type == SystemDataType.MEMORY_MAPPED and not is_master:
        # Java reads addressSpan (not addressableSize).
        span_p = intf.get_param_by_name("addressSpan")
        if span_p:
            step = 1
            al = intf.get_param_by_name("addressAlignment")
            if al and al.value == "NATIVE":
                un = intf.get_param_by_name("addressUnits")
                if un and un.value.upper() == "WORDS":
                    step = 4
            try:
                intf.interface_value = [int(span_p.value, 0) * step]
            except (ValueError, TypeError):
                logger.warning("Cannot parse addressSpan %r on %s.%s",
                               span_p.value, owner.instance_name, name)
    elif data_type == SystemDataType.CLOCK and is_master:
        # Java: bi.setInterfaceValue(DTHelper.parseSize4Intf(getParamValue("clockRate"), bi))
        rate_p = intf.get_param_by_name("clockRate")
        if rate_p:
            try:
                intf.interface_value = [int(rate_p.value, 0)]
            except (ValueError, TypeError):
                logger.warning("Cannot parse clockRate %r on %s.%s",
                               rate_p.value, owner.instance_name, name)
    return intf


def _parse_module(elem: ET.Element, lib: SopcComponentLib) -> Optional[BasicComponent]:
    """Parse one <module> element."""
    kind = elem.get("kind", "")
    name = elem.get("name", "")
    version = elem.get("version", "")
    if not name:
        logger.warning("Module element missing name -- skipping")
        return None
    comp = lib.get_component_for_class(kind, name, version)
    for child in elem:
        if child.tag in ("parameter", "assignment"):
            p = _parse_param_elem(child)
            if p:
                comp.add_param(p)
        elif child.tag == "interface":
            intf = _parse_interface(child, comp)
            if intf:
                comp.add_interface(intf)
    return comp


def _resolve_intf(
    ref: str,
    system: AvalonSystem,
) -> Tuple[Optional[BasicComponent], Optional[Interface]]:
    dot = ref.find(".")
    if dot < 0:
        logger.warning("Cannot parse interface reference %r (no dot)", ref)
        return None, None
    comp = system.get_component_by_name(ref[:dot])
    if comp is None:
        logger.warning("Connection references unknown component %r", ref[:dot])
        return None, None
    intf = comp.get_interface_by_name(ref[dot + 1:])
    if intf is None:
        logger.warning("Connection references unknown interface %r on %r",
                       ref[dot + 1:], ref[:dot])
        return None, None
    return comp, intf


def _parse_connection(elem: ET.Element, system: AvalonSystem) -> None:
    """Parse one <connection> element.  Routing via text child elements (not attrs)."""
    kind = elem.get("kind", "").lower()
    if kind == "reset":
        return
    conn_type = _CONN_KIND_MAP.get(kind)
    if conn_type is None:
        logger.debug("Ignoring connection of unrecognised kind %r", kind)
        return
    start_module = start_cp = end_module = end_cp = ""
    conn_params: dict[str, Parameter] = {}
    for child in elem:
        tag = child.tag
        if tag == "startModule":
            start_module = (child.text or "").strip()
        elif tag == "startConnectionPoint":
            start_cp = (child.text or "").strip()
        elif tag == "endModule":
            end_module = (child.text or "").strip()
        elif tag == "endConnectionPoint":
            end_cp = (child.text or "").strip()
        elif tag in ("parameter", "assignment"):
            p = _parse_param_elem(child)
            if p:
                conn_params[p.name.lower()] = p
    if not (start_module and start_cp and end_module and end_cp):
        logger.warning("Connection of kind %r missing routing elements", kind)
        return
    start = f"{start_module}.{start_cp}"
    end = f"{end_module}.{end_cp}"
    _, master_intf = _resolve_intf(start, system)
    _, slave_intf = _resolve_intf(end, system)
    if master_intf is None or slave_intf is None:
        return
    conn = Connection(master_intf, slave_intf, conn_type, connect=True)
    if conn_type == SystemDataType.MEMORY_MAPPED:
        bp = conn_params.get("baseaddress")
        if bp:
            try:
                conn.conn_value = [int(bp.value, 0)]
            except (ValueError, TypeError):
                logger.warning("Cannot parse baseAddress %r for %s->%s", bp.value, start, end)
    elif conn_type == SystemDataType.CLOCK:
        # Java: bc.setConnValue(bc.getMasterInterface().getInterfaceValue())
        if master_intf.interface_value is not None:
            conn.conn_value = list(master_intf.interface_value)
        else:
            logger.warning("Clock %s->%s: master has no clockRate", start, end)
    elif conn_type == SystemDataType.INTERRUPT:
        ip = conn_params.get("irqnumber")
        if ip:
            try:
                conn.conn_value = [int(ip.value, 0)]
            except (ValueError, TypeError):
                logger.warning("Cannot parse irqNumber %r for %s->%s", ip.value, start, end)


def load_system(
    source: "str | Path",
    component_lib: Optional[SopcComponentLib] = None,
) -> AvalonSystem:
    """
    Parse a .sopcinfo (EnsembleReport) file and return an AvalonSystem.

    Raises ValueError if root is not EnsembleReport, ET.ParseError if malformed.
    """
    source = Path(source)
    lib = component_lib or SopcComponentLib.get_instance()
    logger.info("Loading sopcinfo: %s", source)
    tree = ET.parse(source)
    root = tree.getroot()
    if root.tag != "EnsembleReport":
        raise ValueError(
            f"Expected <EnsembleReport> root element, got <{root.tag}> in {source}"
        )
    name = root.get("name", source.stem)
    # Java reads atts.getValue("version"); fall back to quartusVersion for old files.
    version = root.get("version") or root.get("quartusVersion", "unknown")
    system = AvalonSystem(name, version, source)
    # <reportVersion> text child overrides -- mirrors SopcInfoSystemLoader.characters()
    rv = root.find("reportVersion")
    if rv is not None and rv.text:
        system.set_version(rv.text.strip())
    for mod_elem in root.findall("module"):
        comp = _parse_module(mod_elem, lib)
        if comp is not None:
            system.add_component(comp)
    logger.debug("Parsed %d components", len(system.components))
    for conn_elem in root.findall("connection"):
        _parse_connection(conn_elem, system)
    system.recheck_components()
    logger.info("Loaded system %r: %d components", system.name, len(system.components))
    return system
