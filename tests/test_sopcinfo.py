# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for the sopcinfo parser (sopc2dts_py/parsers/sopcinfo.py)."""

import textwrap
from pathlib import Path

import pytest

from sopc2dts_py.model.component_lib import SopcComponentLib
from sopc2dts_py.model.enums import SystemDataType
from sopc2dts_py.model.parameter import DataType
from sopc2dts_py.parsers.sopcinfo import (
    _infer_type,
    _strip_c_suffix,
    _parse_param_elem,
    _kind_to_type_and_master,
    load_system,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from xml.etree import ElementTree as ET


def xml(s: str) -> ET.Element:
    return ET.fromstring(textwrap.dedent(s).strip())


# ---------------------------------------------------------------------------
# _strip_c_suffix
# ---------------------------------------------------------------------------

def test_strip_c_suffix_clean():
    assert _strip_c_suffix("50000000") == "50000000"

def test_strip_c_suffix_u():
    assert _strip_c_suffix("50000000u") == "50000000"

def test_strip_c_suffix_ul():
    assert _strip_c_suffix("50000000UL") == "50000000"

def test_strip_c_suffix_ull():
    assert _strip_c_suffix("0xFFFFFFFFULL") == "0xFFFFFFFF"

def test_strip_c_suffix_hex_no_suffix():
    assert _strip_c_suffix("0x1000") == "0x1000"


# ---------------------------------------------------------------------------
# _infer_type
# ---------------------------------------------------------------------------

def test_infer_type_empty():
    assert _infer_type("") == DataType.BOOLEAN

def test_infer_type_hex():
    assert _infer_type("0x100") == DataType.NUMBER

def test_infer_type_decimal():
    assert _infer_type("12345") == DataType.NUMBER

def test_infer_type_decimal_with_suffix():
    assert _infer_type("50000000UL") == DataType.NUMBER

def test_infer_type_string():
    assert _infer_type("nios2") == DataType.STRING

def test_infer_type_true():
    # "true" is not a number, so STRING
    assert _infer_type("true") == DataType.STRING


# ---------------------------------------------------------------------------
# _parse_param_elem — attribute form
# ---------------------------------------------------------------------------

def test_parse_param_attr_number():
    e = xml('<parameter name="clockRate" value="50000000"/>')
    p = _parse_param_elem(e)
    assert p is not None
    assert p.name == "clockRate"
    assert p.data_type == DataType.NUMBER
    assert int(p.value) == 50_000_000

def test_parse_param_attr_hex():
    e = xml('<parameter name="baseAddr" value="0x10000000"/>')
    p = _parse_param_elem(e)
    assert p.data_type == DataType.NUMBER
    assert int(p.value, 0) == 0x10000000

def test_parse_param_attr_string():
    e = xml('<parameter name="cpu_type" value="nios2"/>')
    p = _parse_param_elem(e)
    assert p.data_type == DataType.STRING
    assert p.value == "nios2"

def test_parse_param_attr_bool_empty():
    e = xml('<parameter name="tracing" value=""/>')
    p = _parse_param_elem(e)
    assert p.data_type == DataType.BOOLEAN

def test_parse_param_no_name():
    e = xml('<parameter value="42"/>')
    assert _parse_param_elem(e) is None


# ---------------------------------------------------------------------------
# _parse_param_elem — element form (with explicit <type> child)
# ---------------------------------------------------------------------------

def test_parse_param_elem_form_with_type():
    e = xml("""
        <parameter>
            <name>clockFreq</name>
            <value>50000000</value>
            <type>NUMBER</type>
        </parameter>
    """)
    p = _parse_param_elem(e)
    assert p is not None
    assert p.name == "clockFreq"
    assert p.data_type == DataType.NUMBER

def test_parse_param_elem_form_no_type():
    e = xml("""
        <parameter>
            <name>label</name>
            <value>hello</value>
        </parameter>
    """)
    p = _parse_param_elem(e)
    assert p.data_type == DataType.STRING


# ---------------------------------------------------------------------------
# _kind_to_type_and_master
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind,direction,expected_type,expected_master", [
    # Memory-mapped
    ("avalon_master",                 "start", SystemDataType.MEMORY_MAPPED,       True),
    ("avalon_slave",                  "end",   SystemDataType.MEMORY_MAPPED,       False),
    ("altera_axi4_master",            "start", SystemDataType.MEMORY_MAPPED,       True),
    ("axi4lite_slave",                "end",   SystemDataType.MEMORY_MAPPED,       False),
    # Interrupts: Java maps interrupt_receiver→isMaster=True, sender→False
    ("interrupt_sender",              "start", SystemDataType.INTERRUPT,            False),
    ("interrupt_receiver",            "end",   SystemDataType.INTERRUPT,            True),
    # Clock / Reset / Streaming / Custom
    ("clock_source",                  "start", SystemDataType.CLOCK,                True),
    ("clock_sink",                    "end",   SystemDataType.CLOCK,                False),
    ("reset_source",                  "start", SystemDataType.RESET,                True),
    ("reset_sink",                    "end",   SystemDataType.RESET,                False),
    ("avalon_streaming_source",       "start", SystemDataType.STREAMING,            True),
    ("avalon_streaming_sink",         "end",   SystemDataType.STREAMING,            False),
    ("nios_custom_instruction_master","start", SystemDataType.CUSTOM_INSTRUCTION,   True),
    ("nios_custom_instruction_slave", "end",   SystemDataType.CUSTOM_INSTRUCTION,   False),
    # Conduit: Java maps all conduit variants → isMaster=False
    ("conduit",                       "end",   SystemDataType.CONDUIT,              False),
    ("conduit_start",                 "end",   SystemDataType.CONDUIT,              False),
    ("conduit_end",                   "end",   SystemDataType.CONDUIT,              False),
])
def test_interface_kind_mapping(kind, direction, expected_type, expected_master):
    result = _kind_to_type_and_master(kind, direction)
    assert result is not None
    dt, is_master = result
    assert dt == expected_type
    assert is_master == expected_master

def test_interface_kind_unknown():
    assert _kind_to_type_and_master("totally_unknown_interface", "end") is None


# ---------------------------------------------------------------------------
# load_system — minimal in-memory fixture
# ---------------------------------------------------------------------------

MINIMAL_SOPCINFO = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <EnsembleReport name="test_sys" version="13.1">
        <module name="clk_0" kind="altera_clock_bridge" version="13.0">
            <interface name="clk" kind="clock_source" direction="start">
                <parameter name="clockRate" value="50000000"/>
            </interface>
        </module>
        <module name="uart_0" kind="altera_avalon_uart" version="13.0">
            <parameter name="BAUD_RATE" value="115200"/>
            <interface name="clk" kind="clock_sink" direction="end"/>
            <interface name="s1" kind="avalon_slave" direction="end">
                <parameter name="addressSpan" value="32"/>
            </interface>
            <interface name="irq" kind="interrupt_sender" direction="start"/>
        </module>
        <module name="cpu_0" kind="altera_nios2" version="13.0">
            <parameter name="cpu_type" value="nios2"/>
            <interface name="clk" kind="clock_sink" direction="end"/>
            <interface name="data_master" kind="avalon_master" direction="start"/>
            <interface name="d32" kind="interrupt_receiver" direction="end"/>
        </module>
        <connection kind="clock" version="13.0">
            <startModule>clk_0</startModule>
            <startConnectionPoint>clk</startConnectionPoint>
            <endModule>uart_0</endModule>
            <endConnectionPoint>clk</endConnectionPoint>
        </connection>
        <connection kind="clock" version="13.0">
            <startModule>clk_0</startModule>
            <startConnectionPoint>clk</startConnectionPoint>
            <endModule>cpu_0</endModule>
            <endConnectionPoint>clk</endConnectionPoint>
        </connection>
        <connection kind="avalon" version="13.0">
            <startModule>cpu_0</startModule>
            <startConnectionPoint>data_master</startConnectionPoint>
            <endModule>uart_0</endModule>
            <endConnectionPoint>s1</endConnectionPoint>
            <parameter name="baseAddress" value="0x00000100"/>
        </connection>
        <connection kind="interrupt" version="13.0">
            <startModule>uart_0</startModule>
            <startConnectionPoint>irq</startConnectionPoint>
            <endModule>cpu_0</endModule>
            <endConnectionPoint>d32</endConnectionPoint>
            <parameter name="irqNumber" value="1"/>
        </connection>
        <connection kind="reset" version="13.0">
            <startModule>clk_0</startModule>
            <startConnectionPoint>clk_reset</startConnectionPoint>
            <endModule>uart_0</endModule>
            <endConnectionPoint>reset</endConnectionPoint>
        </connection>
    </EnsembleReport>
""")


@pytest.fixture()
def minimal_system(tmp_path):
    sopcinfo = tmp_path / "test_sys.sopcinfo"
    sopcinfo.write_text(MINIMAL_SOPCINFO, encoding="utf-8")
    lib = SopcComponentLib()
    return load_system(sopcinfo, component_lib=lib)


def test_system_name(minimal_system):
    assert minimal_system.name == "test_sys"


def test_system_version(minimal_system):
    assert "13" in minimal_system.version


def test_system_component_count(minimal_system):
    assert len(minimal_system.components) == 3


def test_component_names(minimal_system):
    names = {c.instance_name for c in minimal_system.components}
    assert "clk_0" in names
    assert "uart_0" in names
    assert "cpu_0" in names


def test_component_class(minimal_system):
    uart = minimal_system.get_component_by_name("uart_0")
    assert uart is not None
    assert uart.class_name == "altera_avalon_uart"


def test_component_param(minimal_system):
    uart = minimal_system.get_component_by_name("uart_0")
    assert uart.get_param_val_by_name("BAUD_RATE") == "115200"


def test_interface_count_uart(minimal_system):
    uart = minimal_system.get_component_by_name("uart_0")
    # clk (clock_sink), s1 (avalon_slave), irq (interrupt_sender)
    assert len(uart.interfaces) == 3


def test_interface_types(minimal_system):
    uart = minimal_system.get_component_by_name("uart_0")
    s1 = uart.get_interface_by_name("s1")
    assert s1 is not None
    assert s1.type == SystemDataType.MEMORY_MAPPED
    assert not s1.is_master

    # interrupt_sender maps to isMaster=False per Java SopcInfoInterface.setKind
    irq = uart.get_interface_by_name("irq")
    assert irq.type == SystemDataType.INTERRUPT
    assert not irq.is_master


def test_addressable_size_set(minimal_system):
    uart = minimal_system.get_component_by_name("uart_0")
    s1 = uart.get_interface_by_name("s1")
    assert s1.interface_value is not None
    assert s1.interface_value[0] == 32


def test_avalon_connection_wired(minimal_system):
    cpu = minimal_system.get_component_by_name("cpu_0")
    dm = cpu.get_interface_by_name("data_master")
    assert dm is not None
    assert len(dm.connections) == 1
    conn = dm.connections[0]
    assert conn.slave_module.instance_name == "uart_0"


def test_avalon_connection_base_address(minimal_system):
    cpu = minimal_system.get_component_by_name("cpu_0")
    dm = cpu.get_interface_by_name("data_master")
    conn = dm.connections[0]
    assert conn.conn_value == [0x100]


def test_clock_connection_wired(minimal_system):
    uart = minimal_system.get_component_by_name("uart_0")
    clk_sink = uart.get_interface_by_name("clk")
    assert len(clk_sink.connections) == 1
    conn = clk_sink.connections[0]
    assert conn.type == SystemDataType.CLOCK


def test_clock_connection_rate(minimal_system):
    uart = minimal_system.get_component_by_name("uart_0")
    clk_sink = uart.get_interface_by_name("clk")
    conn = clk_sink.connections[0]
    assert conn.conn_value == [50_000_000]


def test_interrupt_connection_irq_number(minimal_system):
    cpu = minimal_system.get_component_by_name("cpu_0")
    d32 = cpu.get_interface_by_name("d32")
    assert len(d32.connections) == 1
    conn = d32.connections[0]
    assert conn.type == SystemDataType.INTERRUPT
    assert conn.conn_value == [1]


def test_reset_connection_not_wired(minimal_system):
    # Reset connections are skipped — clk_0 should have no reset interface
    clk = minimal_system.get_component_by_name("clk_0")
    reset_intf = clk.get_interface_by_name("clk_reset")
    assert reset_intf is None


def test_master_components(minimal_system):
    masters = minimal_system.get_master_components()
    names = {c.instance_name for c in masters}
    assert "cpu_0" in names
    assert "uart_0" not in names


def test_clock_rate_via_get_clock_rate(minimal_system):
    uart = minimal_system.get_component_by_name("uart_0")
    assert uart.get_clock_rate() == 50_000_000


# ---------------------------------------------------------------------------
# load_system — wrong root element raises
# ---------------------------------------------------------------------------

def test_load_system_bad_root(tmp_path):
    bad = tmp_path / "bad.sopcinfo"
    bad.write_text("<NotEnsembleReport/>", encoding="utf-8")
    with pytest.raises(ValueError, match="EnsembleReport"):
        load_system(bad, component_lib=SopcComponentLib())


# ---------------------------------------------------------------------------
# Dispatch via parsers.__init__.load_system
# ---------------------------------------------------------------------------

def test_dispatch_sopcinfo(tmp_path):
    from sopc2dts_py.parsers import load_system as dispatch_load
    sopcinfo = tmp_path / "test.sopcinfo"
    sopcinfo.write_text(MINIMAL_SOPCINFO, encoding="utf-8")
    sys = dispatch_load(sopcinfo)
    assert sys.name == "test_sys"


def test_dispatch_unknown_ext(tmp_path):
    from sopc2dts_py.parsers import load_system as dispatch_load
    bad = tmp_path / "design.vhd"
    bad.write_text("<x/>", encoding="utf-8")
    with pytest.raises(ValueError, match="Unrecognised"):
        dispatch_load(bad)
