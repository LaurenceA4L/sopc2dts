# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for the QSys parser (sopc2dts_py/parsers/qsys.py)."""

import textwrap
from pathlib import Path

import pytest

from sopc2dts_py.model.component_lib import SopcComponentLib
from sopc2dts_py.model.enums import SystemDataType
from sopc2dts_py.model.parameter import DataType
from sopc2dts_py.parsers.qsys import (
    _qsys_type_to_sdt,
    _parse_address,
    _is_zero_or_none,
    _parse_qsys_param,
    _QSysSubSystem,
    load_system,
)

from xml.etree import ElementTree as ET


def xml(s: str) -> ET.Element:
    return ET.fromstring(textwrap.dedent(s).strip())


# ---------------------------------------------------------------------------
# _qsys_type_to_sdt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("type_str,expected", [
    ("avalon",           SystemDataType.MEMORY_MAPPED),
    ("AVALON",           SystemDataType.MEMORY_MAPPED),
    ("avalon_streaming", SystemDataType.STREAMING),
    ("clock",            SystemDataType.CLOCK),
    ("reset",            SystemDataType.RESET),
    ("conduit",          SystemDataType.CONDUIT),
    ("unknown_type",     SystemDataType.CONDUIT),   # fallthrough → CONDUIT
])
def test_qsys_type_to_sdt(type_str, expected):
    assert _qsys_type_to_sdt(type_str) == expected


# ---------------------------------------------------------------------------
# _parse_address
# ---------------------------------------------------------------------------

def test_parse_address_hex():
    assert _parse_address("0x100", 1) == [0x100]

def test_parse_address_decimal():
    assert _parse_address("256", 1) == [256]

def test_parse_address_wide():
    # 64-bit address into 2 cells
    assert _parse_address("0x100000000", 2) == [0x1, 0x0]

def test_parse_address_none():
    assert _parse_address(None, 1) is None

def test_parse_address_bad():
    assert _parse_address("notanumber", 1) is None


# ---------------------------------------------------------------------------
# _is_zero_or_none
# ---------------------------------------------------------------------------

def test_is_zero_or_none_none():
    assert _is_zero_or_none(None)

def test_is_zero_or_none_zeros():
    assert _is_zero_or_none([0, 0])

def test_is_zero_or_none_nonzero():
    assert not _is_zero_or_none([50_000_000])


# ---------------------------------------------------------------------------
# _parse_qsys_param
# ---------------------------------------------------------------------------

def test_parse_qsys_param_basic():
    e = xml('<parameter name="clockFrequency" value="50000000"/>')
    p = _parse_qsys_param(e)
    assert p is not None
    assert p.name == "clockFrequency"
    assert p.value == "50000000"
    assert p.data_type == DataType.STRING   # QSys always STRING

def test_parse_qsys_param_no_name():
    e = xml('<parameter value="42"/>')
    assert _parse_qsys_param(e) is None


# ---------------------------------------------------------------------------
# load_system — minimal in-memory fixture
# ---------------------------------------------------------------------------

MINIMAL_QSYS = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <system version="13.1">
        <module name="clk_0" kind="altera_clock_bridge" version="13.0">
            <parameter name="clockFrequency" value="50000000"/>
            <interface name="clk" type="clock" dir="start"/>
        </module>
        <module name="uart_0" kind="altera_avalon_uart" version="13.0">
            <parameter name="BAUD_RATE" value="115200"/>
            <interface name="clk" type="clock" dir="end"/>
            <interface name="s1" type="avalon" dir="end"/>
        </module>
        <module name="cpu_0" kind="altera_nios2_qsys" version="13.0">
            <parameter name="clockFrequency" value="50000000"/>
            <interface name="clk" type="clock" dir="end"/>
            <interface name="data_master" type="avalon" dir="start"/>
        </module>
        <connection kind="clock" version="13.0"
                    start="clk_0.clk" end="uart_0.clk"/>
        <connection kind="clock" version="13.0"
                    start="clk_0.clk" end="cpu_0.clk"/>
        <connection kind="avalon" version="13.0"
                    start="cpu_0.data_master" end="uart_0.s1">
            <parameter name="baseAddress" value="0x00000100"/>
        </connection>
    </system>
""")


@pytest.fixture()
def minimal_qsys_system(tmp_path):
    qsys_file = tmp_path / "test_design.qsys"
    qsys_file.write_text(MINIMAL_QSYS, encoding="utf-8")
    lib = SopcComponentLib()
    return load_system(qsys_file, component_lib=lib)


def test_qsys_system_name(minimal_qsys_system):
    # Name derived from filename (without extension)
    assert minimal_qsys_system.name == "test_design"


def test_qsys_system_version(minimal_qsys_system):
    assert "13" in minimal_qsys_system.version


def test_qsys_component_count(minimal_qsys_system):
    assert len(minimal_qsys_system.components) == 3


def test_qsys_component_names(minimal_qsys_system):
    names = {c.instance_name for c in minimal_qsys_system.components}
    assert "clk_0" in names
    assert "uart_0" in names
    assert "cpu_0" in names


def test_qsys_component_class(minimal_qsys_system):
    uart = minimal_qsys_system.get_component_by_name("uart_0")
    assert uart.class_name == "altera_avalon_uart"


def test_qsys_param(minimal_qsys_system):
    uart = minimal_qsys_system.get_component_by_name("uart_0")
    assert uart.get_param_val_by_name("BAUD_RATE") == "115200"


def test_qsys_interface_types(minimal_qsys_system):
    uart = minimal_qsys_system.get_component_by_name("uart_0")
    s1 = uart.get_interface_by_name("s1")
    assert s1 is not None
    assert s1.type == SystemDataType.MEMORY_MAPPED
    assert not s1.is_master

    clk = uart.get_interface_by_name("clk")
    assert clk.type == SystemDataType.CLOCK
    assert not clk.is_master


def test_qsys_clock_connection(minimal_qsys_system):
    clk_0 = minimal_qsys_system.get_component_by_name("clk_0")
    clk_src = clk_0.get_interface_by_name("clk")
    assert len(clk_src.connections) == 2


def test_qsys_clock_rate_on_conn(minimal_qsys_system):
    cpu = minimal_qsys_system.get_component_by_name("cpu_0")
    clk_sink = cpu.get_interface_by_name("clk")
    conn = clk_sink.connections[0]
    assert conn.conn_value == [50_000_000]


def test_qsys_avalon_connection(minimal_qsys_system):
    cpu = minimal_qsys_system.get_component_by_name("cpu_0")
    dm = cpu.get_interface_by_name("data_master")
    assert len(dm.connections) == 1
    assert dm.connections[0].conn_value == [0x100]
    assert dm.connections[0].slave_module.instance_name == "uart_0"


def test_qsys_bad_root(tmp_path):
    bad = tmp_path / "bad.qsys"
    bad.write_text("<EnsembleReport/>", encoding="utf-8")
    with pytest.raises(ValueError, match="system"):
        load_system(bad, component_lib=SopcComponentLib())


# ---------------------------------------------------------------------------
# Hierarchical subsystem flattening
# ---------------------------------------------------------------------------

INNER_QSYS = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <system version="13.1">
        <module name="inner_uart" kind="altera_avalon_uart" version="13.0">
            <interface name="s1" type="avalon" dir="end"/>
        </module>
        <interface name="s1_export" type="avalon" dir="end">
        </interface>
    </system>
""")

OUTER_QSYS_TEMPLATE = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <system version="13.1">
        <module name="sub_0" kind="uart_sub" version="13.0">
            <interface name="s1_export" type="avalon" dir="end"
                       internal="inner_uart.s1"/>
        </module>
        <module name="cpu_0" kind="altera_nios2_qsys" version="13.0">
            <interface name="data_master" type="avalon" dir="start"/>
        </module>
        <connection kind="avalon" version="13.0"
                    start="cpu_0.data_master" end="sub_0.s1_export">
            <parameter name="baseAddress" value="0x200"/>
        </connection>
    </system>
""")


def test_subsystem_flatten(tmp_path):
    """After flattening, the inner component is promoted with a prefixed name."""
    # Write inner sub-system file  (kind=uart_sub → uart_sub.qsys)
    (tmp_path / "uart_sub.qsys").write_text(INNER_QSYS, encoding="utf-8")
    outer = tmp_path / "outer.qsys"
    outer.write_text(OUTER_QSYS_TEMPLATE, encoding="utf-8")

    lib = SopcComponentLib()
    sys = load_system(outer, component_lib=lib)

    names = {c.instance_name for c in sys.components}
    # sub_0 should be gone; inner_uart should be promoted as "sub_0-inner_uart"
    assert "sub_0" not in names
    assert "sub_0-inner_uart" in names
    assert "cpu_0" in names


# ---------------------------------------------------------------------------
# _QSysSubSystem helpers
# ---------------------------------------------------------------------------

def test_qsys_subsystem_add_and_find():
    from sopc2dts_py.model.component import BasicComponent
    sub = _QSysSubSystem("sub_0", "13.0")
    inner = BasicComponent("altera_avalon_uart", "uart_0", "13.0")
    sub.add_module(inner)
    assert sub.get_component_by_name("uart_0") is inner
    assert sub.get_component_by_name("missing") is None
