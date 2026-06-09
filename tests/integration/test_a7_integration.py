"""
Integration tests: parse a7_system.sopcinfo end-to-end.

Exercises Agilex 7 GHRD components from Quartus 25.1:
  - intel_agilex_hps            → BasicComponent (group=ignore)
  - intel_pcie_ptile_mcdma      → BasicComponent (group=ignore)
  - intel_cache_coherency_translator → BasicComponent (group=ignore)
  - altera_emif_cal / altera_emif_fm_hps / hps_response_timer → BasicComponent (group=ignore)
  - altera_s10_user_rst_clkgate → BasicComponent (group=ignore)
  - altera_reset_bridge         → BasicComponent (group=ignore)
  - altera_clock_bridge         → SICClockSource (group=clock)
  - altera_avalon_pio           → SICGpioController (group=gpio)
  - altera_avalon_onchip_memory2 → BasicComponent (group=memory)
"""
from __future__ import annotations

import pytest
from pathlib import Path

from sopc2dts_py.parsers.sopcinfo import load_system
from sopc2dts_py.model.component_lib import SopcComponentLib
from sopc2dts_py.model.component import BasicComponent
from sopc2dts_py.components.base.SICClockSource import SICClockSource
from sopc2dts_py.components.base.SICGpioController import SICGpioController

FIXTURE = Path(__file__).parent.parent / "fixtures" / "a7_system.sopcinfo"
REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def a7_system():
    lib = SopcComponentLib()
    lib.load_component_libs_in_dir(REPO_ROOT)
    return load_system(FIXTURE, component_lib=lib)


# ── Basic system properties ───────────────────────────────────────────────────

def test_system_name(a7_system):
    assert a7_system.name == "system"


def test_component_count(a7_system):
    assert len(a7_system.components) == 11


def test_expected_names_present(a7_system):
    names = {c.instance_name for c in a7_system.components}
    expected = {
        "clock_in", "hps", "emif_calbus", "hps_emif",
        "hps_response_timer_0", "init_done", "intel_pcie_ptile_mcdma_0",
        "led_pio", "ocm", "reset_in", "system_intel_cache_coherency_translator",
    }
    assert names == expected


# ── Component handler dispatch ────────────────────────────────────────────────

def _get(system, name):
    for c in system.components:
        if c.instance_name == name:
            return c
    raise KeyError(name)


def test_clock_dispatched(a7_system):
    clk = _get(a7_system, "clock_in")
    assert isinstance(clk, SICClockSource)


def test_led_pio_dispatched(a7_system):
    pio = _get(a7_system, "led_pio")
    assert isinstance(pio, SICGpioController)


def test_led_pio_class_name(a7_system):
    pio = _get(a7_system, "led_pio")
    assert pio.class_name == "altera_avalon_pio"


def test_hps_is_basic_component(a7_system):
    hps = _get(a7_system, "hps")
    assert isinstance(hps, BasicComponent)
    assert hps.class_name == "intel_agilex_hps"


def test_hps_group_is_ignore(a7_system):
    hps = _get(a7_system, "hps")
    assert hps.scd is not None
    assert hps.scd.group == "ignore"


def test_pcie_is_basic_component(a7_system):
    pcie = _get(a7_system, "intel_pcie_ptile_mcdma_0")
    assert isinstance(pcie, BasicComponent)
    assert pcie.class_name == "intel_pcie_ptile_mcdma"
    assert pcie.scd is not None
    assert pcie.scd.group == "ignore"


def test_cache_coherency_translator_ignored(a7_system):
    cct = _get(a7_system, "system_intel_cache_coherency_translator")
    assert isinstance(cct, BasicComponent)
    assert cct.scd is not None
    assert cct.scd.group == "ignore"


def test_emif_cal_ignored(a7_system):
    emif = _get(a7_system, "emif_calbus")
    assert emif.scd is not None
    assert emif.scd.group == "ignore"


def test_emif_fm_hps_ignored(a7_system):
    emif = _get(a7_system, "hps_emif")
    assert emif.scd is not None
    assert emif.scd.group == "ignore"


def test_reset_bridge_ignored(a7_system):
    rb = _get(a7_system, "reset_in")
    assert rb.scd is not None
    assert rb.scd.group == "ignore"


def test_ocm_is_memory(a7_system):
    ocm = _get(a7_system, "ocm")
    assert ocm.class_name == "altera_avalon_onchip_memory2"
    assert ocm.scd is not None
    assert ocm.scd.group == "memory"


# ── No unknown components ─────────────────────────────────────────────────────

def test_no_unknown_components(a7_system):
    """Every component in the Agilex7 GHRD should resolve to a known group."""
    from sopc2dts_py.components.base.SICUnknown import SICUnknown
    unknown = [
        c for c in a7_system.components
        if isinstance(c.scd, SICUnknown) or (c.scd and c.scd.group == "unknown")
    ]
    assert unknown == [], f"Unknown components: {[c.instance_name for c in unknown]}"
