# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Basic smoke tests for the model layer."""

from pathlib import Path
import pytest

from sopc2dts_py.model.enums import SystemDataType, ParameterAction
from sopc2dts_py.model.parameter import Parameter, DataType
from sopc2dts_py.model.component import (
    BasicElement, Interface, MemoryBlock, BasicComponent, SopcComponentDescription,
)
from sopc2dts_py.model.connection import Connection
from sopc2dts_py.model.system import AvalonSystem


# ---------------------------------------------------------------------------
# Parameter
# ---------------------------------------------------------------------------

def test_parameter_number():
    p = Parameter("width", "32", DataType.NUMBER)
    assert p.name == "width"
    assert p.value == "32"
    assert p.data_type == DataType.NUMBER


def test_parameter_unsigned_negative():
    # Negative values stored as 0x-padded unsigned hex, matching Java behaviour
    p = Parameter("base", "-1", DataType.UNSIGNED)
    assert p.value == "0xffffffff"


def test_parameter_boolean_true():
    p = Parameter("enabled", "1", DataType.BOOLEAN)
    assert p.get_value_as_bool() is True


def test_parameter_boolean_false():
    p = Parameter("enabled", "0", DataType.BOOLEAN)
    assert p.get_value_as_bool() is False


def test_parameter_boolean_true_when_present():
    p = Parameter("flag", "", DataType.BOOLEAN_TRUE_WHEN_PRESENT)
    assert p.data_type == DataType.BOOLEAN
    assert p.value == "true"


def test_parameter_data_type_by_name():
    assert Parameter.data_type_by_name("NUMBER") == DataType.NUMBER
    assert Parameter.data_type_by_name("bool") == DataType.BOOLEAN
    assert Parameter.data_type_by_name("UNSIGNED") == DataType.UNSIGNED
    assert Parameter.data_type_by_name(None) is None
    assert Parameter.data_type_by_name("garbage") is None


# ---------------------------------------------------------------------------
# BasicElement / parameter lookup
# ---------------------------------------------------------------------------

def test_basic_element_param_lookup():
    comp = BasicComponent("foo_ip", "foo_0", "1.0")
    comp.add_param(Parameter("clock-frequency", "50000000", DataType.NUMBER))
    p = comp.get_param_by_name("clock-frequency")
    assert p is not None
    assert p.value == "50000000"
    assert comp.get_param_val_by_name("clock-frequency") == "50000000"
    assert comp.get_param_by_name("nonexistent") is None


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

def _make_cpu() -> BasicComponent:
    scd = SopcComponentDescription("altera_nios2", group="cpu", vendor="altera")
    return BasicComponent("altera_nios2", "cpu_0", "13.0", scd)


def test_interface_predicates():
    cpu = _make_cpu()
    mm = Interface("data_master", SystemDataType.MEMORY_MAPPED, True, cpu)
    assert mm.is_memory_master() is True
    assert mm.is_memory_slave() is False
    assert mm.is_clock() is False

    clk = Interface("clk", SystemDataType.CLOCK, False, cpu)
    assert clk.is_clock_slave() is True
    assert clk.is_clock_master() is False

    irq = Interface("irq_in", SystemDataType.INTERRUPT, False, cpu)
    assert irq.is_irq_slave() is True
    assert irq.is_irq_master() is False


def test_interface_default_widths():
    cpu = _make_cpu()
    mm = Interface("data_master", SystemDataType.MEMORY_MAPPED, True, cpu)
    assert mm.primary_width == 1
    assert mm.secondary_width == 1  # MEMORY_MAPPED default

    clk_slave = Interface("clk", SystemDataType.CLOCK, False, cpu)
    assert clk_slave.secondary_width == 0  # CLOCK slave default


# ---------------------------------------------------------------------------
# BasicComponent
# ---------------------------------------------------------------------------

def test_component_interface_management():
    cpu = _make_cpu()
    intf = Interface("data_master", SystemDataType.MEMORY_MAPPED, True, cpu)
    cpu.add_interface(intf)

    assert cpu.get_interface_by_name("data_master") is intf
    assert cpu.get_interface_by_name("DATA_MASTER") is intf  # case-insensitive
    assert cpu.has_memory_master() is True
    assert len(cpu.get_interfaces(SystemDataType.MEMORY_MAPPED, True)) == 1


def test_component_no_memory_master():
    comp = BasicComponent("simple_ip", "simple_0", "1.0")
    assert comp.has_memory_master() is False


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def test_connection_links_interfaces():
    cpu = _make_cpu()
    master_intf = Interface("data_master", SystemDataType.MEMORY_MAPPED, True, cpu)
    cpu.add_interface(master_intf)

    scd = SopcComponentDescription("altera_onchip_memory2", group="memory")
    ram = BasicComponent("altera_onchip_memory2", "ram_0", "13.0", scd)
    slave_intf = Interface("s1", SystemDataType.MEMORY_MAPPED, False, ram)
    ram.add_interface(slave_intf)

    conn = Connection(master_intf, slave_intf, connect=True)
    conn.conn_value = [0xFF200000]

    assert conn.master_module is cpu
    assert conn.slave_module is ram
    assert conn in master_intf.connections
    assert conn in slave_intf.connections


def test_connection_disconnect():
    cpu = _make_cpu()
    mi = Interface("data_master", SystemDataType.MEMORY_MAPPED, True, cpu)
    cpu.add_interface(mi)

    ram = BasicComponent("ram", "ram_0", "1.0")
    si = Interface("s1", SystemDataType.MEMORY_MAPPED, False, ram)
    ram.add_interface(si)

    conn = Connection(mi, si, connect=True)
    conn.disconnect()

    assert conn not in mi.connections
    assert conn not in si.connections


# ---------------------------------------------------------------------------
# AvalonSystem
# ---------------------------------------------------------------------------

def test_avalon_system_lookup():
    sys = AvalonSystem("test", "13.0", Path("test.sopcinfo"))
    cpu = _make_cpu()
    sys.add_component(cpu)

    assert sys.get_component_by_name("cpu_0") is cpu
    assert sys.get_component_by_name("CPU_0") is cpu  # case-insensitive
    assert sys.get_component_by_name("missing") is None
    assert sys.get_master_components() == []  # no interfaces added yet


def test_avalon_system_masters():
    sys = AvalonSystem("test", "13.0", Path("test.sopcinfo"))
    cpu = _make_cpu()
    intf = Interface("data_master", SystemDataType.MEMORY_MAPPED, True, cpu)
    cpu.add_interface(intf)
    sys.add_component(cpu)

    assert cpu in sys.get_master_components()
