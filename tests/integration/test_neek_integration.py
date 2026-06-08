"""
Integration tests: parse neek.sopcinfo end-to-end through Phase 1 pipeline.

These tests exercise the real parser + component_lib dispatch on a synthetic
Nios2 fixture that mirrors the NEEK board (see boardinfo_neek.xml).
"""
from __future__ import annotations

import pytest
from pathlib import Path

from sopc2dts_py.parsers.sopcinfo import load_system
from sopc2dts_py.model.component_lib import SopcComponentLib
from sopc2dts_py.components.base.SICCpuComponent import SICCpuComponent
from sopc2dts_py.components.base.SICFlash import SICFlash
from sopc2dts_py.components.base.SICI2CMaster import SICI2CMaster
from sopc2dts_py.components.base.SICClockSource import SICClockSource

FIXTURE = Path(__file__).parent.parent / "fixtures" / "neek.sopcinfo"
# XML component library files live in the repo root alongside the Java source
REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def neek_system():
    lib = SopcComponentLib()
    lib.load_component_libs_in_dir(REPO_ROOT)
    return load_system(FIXTURE, component_lib=lib)


# ── Basic system properties ───────────────────────────────────────────────────

def test_system_name(neek_system):
    assert neek_system.name == "neek"


def test_component_count(neek_system):
    # clk_0, cpu_0, ext_flash, ddr_sdram, onchip_memory2_0, i2c_1, jtag_uart_0
    assert len(neek_system.components) == 7


def test_all_component_names(neek_system):
    names = {c.instance_name for c in neek_system.components}
    assert names == {
        "clk_0", "cpu_0", "ext_flash", "ddr_sdram",
        "onchip_memory2_0", "i2c_1", "jtag_uart_0",
    }


# ── Component handler dispatch ────────────────────────────────────────────────

def _get(system, name):
    for c in system.components:
        if c.instance_name == name:
            return c
    raise KeyError(name)


def test_cpu_dispatched(neek_system):
    cpu = _get(neek_system, "cpu_0")
    assert isinstance(cpu, SICCpuComponent)


def test_cpu_class_name(neek_system):
    cpu = _get(neek_system, "cpu_0")
    assert cpu.class_name == "altera_nios2_qsys"


def test_flash_dispatched(neek_system):
    flash = _get(neek_system, "ext_flash")
    assert isinstance(flash, SICFlash)


def test_i2c_dispatched(neek_system):
    i2c = _get(neek_system, "i2c_1")
    assert isinstance(i2c, SICI2CMaster)


def test_clock_dispatched(neek_system):
    clk = _get(neek_system, "clk_0")
    assert isinstance(clk, SICClockSource)


def test_sdram_present(neek_system):
    sdram = _get(neek_system, "ddr_sdram")
    assert sdram is not None
    assert sdram.class_name == "altera_avalon_new_sdram_controller"


def test_onchip_memory_present(neek_system):
    mem = _get(neek_system, "onchip_memory2_0")
    assert mem is not None
    assert mem.class_name == "altera_avalon_onchip_memory2"


# ── Connections ───────────────────────────────────────────────────────────────

def test_cpu_has_data_master(neek_system):
    cpu = _get(neek_system, "cpu_0")
    iface_names = {i.name for i in cpu.interfaces}
    assert "data_master" in iface_names


def test_cpu_data_master_has_connections(neek_system):
    cpu = _get(neek_system, "cpu_0")
    dm = next(i for i in cpu.interfaces if i.name == "data_master")
    # flash, sdram, onchip_mem, i2c, jtag_uart
    assert len(dm.connections) >= 4


def test_i2c_irq_connection(neek_system):
    i2c = _get(neek_system, "i2c_1")
    irq_intf = next((i for i in i2c.interfaces if i.name == "irq"), None)
    assert irq_intf is not None
    assert len(irq_intf.connections) >= 1


def test_flash_base_address(neek_system):
    cpu = _get(neek_system, "cpu_0")
    dm = next(i for i in cpu.interfaces if i.name == "data_master")
    flash_conn = next(
        (c for c in dm.connections
         if c.slave_interface is not None and
            c.slave_interface.owner.instance_name == "ext_flash"),
        None,
    )
    assert flash_conn is not None
    assert flash_conn.conn_value is not None
    assert flash_conn.conn_value[0] == 0x00000000
