"""
Integration tests: parse cv_soc_ghrd.sopcinfo end-to-end through Phase 1 pipeline.

Exercises Cyclone V SoC GHRD-style components:
  - altera_avalon_pio           → SICGpioController
  - altera_hps (group=ignore)   → BasicComponent (SCD exists, no specific handler)
  - arm_gic                     → CortexA9GIC (class-name dispatch)
  - lw_h2f_hps_bridge_avalon   → MultiBridge (class-name dispatch)
    └─ recheck_components splits it, adding a second SICBridge (f2h side)
"""
from __future__ import annotations

import pytest
from pathlib import Path

from sopc2dts_py.parsers.sopcinfo import load_system
from sopc2dts_py.model.component_lib import SopcComponentLib
from sopc2dts_py.model.component import BasicComponent
from sopc2dts_py.components.base.SICClockSource import SICClockSource
from sopc2dts_py.components.base.SICGpioController import SICGpioController
from sopc2dts_py.components.base.SICBridge import SICBridge
from sopc2dts_py.components.altera.MultiBridge import MultiBridge
from sopc2dts_py.components.arm.CortexA9GIC import CortexA9GIC

FIXTURE = Path(__file__).parent.parent / "fixtures" / "cv_soc_ghrd.sopcinfo"
REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def cv_system():
    lib = SopcComponentLib()
    lib.load_component_libs_in_dir(REPO_ROOT)
    return load_system(FIXTURE, component_lib=lib)


# ── Basic system properties ───────────────────────────────────────────────────

def test_system_name(cv_system):
    assert cv_system.name == "soc_system"


def test_component_count(cv_system):
    # Original 7 + 1 added by MultiBridge.remove_from_system_if_possible (f2h bridge)
    assert len(cv_system.components) == 8


def test_expected_names_present(cv_system):
    names = {c.instance_name for c in cv_system.components}
    expected = {
        "clk_0", "button_pio", "led_pio", "sysid_qsys",
        "hps_0", "hps_0_arm_gic_0", "lw_fpga2hps",
    }
    assert expected.issubset(names)


# ── Component handler dispatch ────────────────────────────────────────────────

def _get(system, name):
    for c in system.components:
        if c.instance_name == name:
            return c
    raise KeyError(name)


def test_clock_dispatched(cv_system):
    clk = _get(cv_system, "clk_0")
    assert isinstance(clk, SICClockSource)


def test_button_pio_dispatched(cv_system):
    pio = _get(cv_system, "button_pio")
    assert isinstance(pio, SICGpioController)


def test_led_pio_dispatched(cv_system):
    pio = _get(cv_system, "led_pio")
    assert isinstance(pio, SICGpioController)


def test_hps_stays_basic_component(cv_system):
    # altera_hps has group=ignore: SCD exists but no specific handler is wired.
    # The component remains as-is (BasicComponent), unlike truly unknown components
    # which get wrapped in SICUnknown (no SCD at all).
    hps = _get(cv_system, "hps_0")
    assert isinstance(hps, BasicComponent)
    assert hps.class_name == "altera_hps"


def test_arm_gic_dispatched(cv_system):
    gic = _get(cv_system, "hps_0_arm_gic_0")
    assert isinstance(gic, CortexA9GIC)


def test_arm_gic_class_name(cv_system):
    gic = _get(cv_system, "hps_0_arm_gic_0")
    assert gic.class_name == "arm_gic"


def test_hps_bridge_dispatched(cv_system):
    bridge = _get(cv_system, "lw_fpga2hps")
    assert isinstance(bridge, MultiBridge)


def test_hps_bridge_class_name(cv_system):
    bridge = _get(cv_system, "lw_fpga2hps")
    assert bridge.class_name == "lw_h2f_hps_bridge_avalon"


def test_multibridge_split_adds_f2h(cv_system):
    # MultiBridge.remove_from_system_if_possible adds the f2h SICBridge
    names = {c.instance_name for c in cv_system.components}
    assert "lw_fpga2hps_f2h" in names
    f2h = _get(cv_system, "lw_fpga2hps_f2h")
    assert isinstance(f2h, SICBridge)


# ── Connections ───────────────────────────────────────────────────────────────

def test_button_pio_has_irq_interface(cv_system):
    pio = _get(cv_system, "button_pio")
    irq = next((i for i in pio.interfaces if i.name == "irq"), None)
    assert irq is not None


def test_button_pio_irq_connects_to_gic(cv_system):
    pio = _get(cv_system, "button_pio")
    irq = next(i for i in pio.interfaces if i.name == "irq")
    assert len(irq.connections) >= 1
    conn = irq.connections[0]
    assert conn.slave_interface.owner.instance_name == "hps_0_arm_gic_0"


def test_hps_lw_master_connects_to_pios(cv_system):
    hps = _get(cv_system, "hps_0")
    lw_master = next(
        (i for i in hps.interfaces if i.name == "h2f_lw_axi_master"), None
    )
    assert lw_master is not None
    slave_names = {
        c.slave_interface.owner.instance_name
        for c in lw_master.connections
        if c.slave_interface is not None
    }
    assert "button_pio" in slave_names
    assert "led_pio" in slave_names
