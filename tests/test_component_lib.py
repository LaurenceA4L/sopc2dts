# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for SopcComponentDescription (fleshed-out) and SopcComponentLib."""

from pathlib import Path

import pytest

from sopc2dts_py.model.component import (
    SopcComponentDescription, SICAutoParam, SICRequiredParam,
    TransparentInterfaceBridge, BasicComponent,
)
from sopc2dts_py.model.component_lib import SopcComponentLib


# ---------------------------------------------------------------------------
# SopcComponentDescription — multi-class name support
# ---------------------------------------------------------------------------

def test_scd_single_classname():
    scd = SopcComponentDescription("altera_nios2")
    assert scd.class_name == "altera_nios2"
    assert scd.class_names == ["altera_nios2"]
    assert scd.is_supporting_class_name("altera_nios2")
    assert scd.is_supporting_class_name("ALTERA_NIOS2")  # case-insensitive
    assert not scd.is_supporting_class_name("something_else")


def test_scd_multi_classname():
    scd = SopcComponentDescription("altera_nios2, altera_nios2_qsys", group="cpu")
    assert scd.is_supporting_class_name("altera_nios2")
    assert scd.is_supporting_class_name("altera_nios2_qsys")
    assert not scd.is_supporting_class_name("altera_nios2_v2")


# ---------------------------------------------------------------------------
# SopcComponentDescription — auto params / required params
# ---------------------------------------------------------------------------

def test_scd_add_auto_param():
    scd = SopcComponentDescription("altera_avalon_uart", vendor="ALTR", device="uart")
    scd.add_auto_param("current-speed", "embeddedsw.CMacro.BAUD", None)
    scd.add_auto_param("clock-frequency", "embeddedsw.CMacro.FREQ", None)
    assert len(scd.auto_params) == 2
    assert scd.auto_params[0].dts_name == "current-speed"
    assert scd.auto_params[0].sopc_info_name == "embeddedsw.CMacro.BAUD"


def test_scd_required_params_ok():
    scd = SopcComponentDescription("altera_nios2", group="cpu")
    scd.add_required_param("cpu_type", "nios2")

    comp_ok = BasicComponent("altera_nios2", "cpu_0", "13.0", scd)
    from sopc2dts_py.model.parameter import Parameter, DataType
    comp_ok.add_param(Parameter("cpu_type", "nios2", DataType.STRING))
    assert scd.is_required_params_ok(comp_ok)

    comp_bad = BasicComponent("altera_nios2", "cpu_1", "13.0", scd)
    assert not scd.is_required_params_ok(comp_bad)


# ---------------------------------------------------------------------------
# SopcComponentDescription — get_compatibles / compare_versions
# ---------------------------------------------------------------------------

def test_compare_versions_equal():
    assert SopcComponentDescription.compare_versions("1.0", "1.0") == 0


def test_compare_versions_newer():
    # v2 > v1  → positive (Java returns v2-v1 style diff)
    assert SopcComponentDescription.compare_versions("1.0", "2.0") > 0


def test_compare_versions_older():
    assert SopcComponentDescription.compare_versions("2.0", "1.0") < 0


def test_get_compatibles_with_version():
    scd = SopcComponentDescription(
        "altera_nios2", group="cpu", vendor="ALTR", device="nios2"
    )
    scd.add_compatible("altera,nios2-r1")
    result = scd.get_compatibles("13.0")
    assert "ALTR,nios2-13.0" in result
    assert "altera,nios2-r1" in result


def test_get_compatibles_no_version():
    scd = SopcComponentDescription(
        "altera_nios2", group="cpu", vendor="ALTR", device="nios2"
    )
    result = scd.get_compatibles(None)
    assert "ALTR,nios2" in result


def test_get_compatibles_with_bw_compat_version():
    scd = SopcComponentDescription(
        "altera_avalon_uart", group="serial", vendor="ALTR", device="uart"
    )
    scd.add_compatible_version("1.0")  # backward-compat version
    result = scd.get_compatibles("2.0")
    # Should include both versioned strings: 2.0 first, 1.0 (bw-compat) second
    assert "ALTR,uart-2.0" in result
    assert "ALTR,uart-1.0" in result


def test_is_overridden_version():
    scd = SopcComponentDescription("foo_ip", vendor="X", device="foo")
    scd.add_override_version("3.0")
    assert scd.is_overridden_version("3.0")
    assert not scd.is_overridden_version("2.0")


# ---------------------------------------------------------------------------
# SopcComponentLib — XML loading
# ---------------------------------------------------------------------------

MINIMAL_LIB_XML = """<SOPC2DTS_COMPONENTLIB vendor="ALTR">
    <S2DComponent classname="altera_nios2,altera_nios2_qsys" group="cpu" compatDevice="nios2">
        <CompatibleVersion value="1.0"/>
        <parameter dtsName="clock-frequency" sopcName="embeddedsw.CMacro.CPU_FREQ"/>
        <parameter dtsVName="implementation" sopcName="embeddedsw.CMacro.CPU_IMPLEMENTATION"/>
    </S2DComponent>
    <S2DComponent classname="altera_avalon_uart" group="serial" compatDevice="uart">
        <CompatibleVersion value="1.0"/>
        <parameter dtsName="current-speed" sopcName="embeddedsw.CMacro.BAUD"/>
    </S2DComponent>
    <S2DComponent classname="altera_avalon_pio" group="gpio" compatDevice="pio">
        <RequiredParameter name="direction" value="bidir"/>
        <parameter dtsName="width" sopcName="WIDTH"/>
    </S2DComponent>
    <S2DComponent classname="altera_avalon_cfi_flash" group="flash" compatDevice="cfi_flash">
        <compatible name="cfi-flash"/>
    </S2DComponent>
</SOPC2DTS_COMPONENTLIB>"""


@pytest.fixture()
def lib_with_xml(tmp_path):
    xml_file = tmp_path / "sopc_components_test.xml"
    xml_file.write_text(MINIMAL_LIB_XML, encoding="utf-8")
    lib = SopcComponentLib()
    lib.load_component_lib(xml_file)
    return lib


def test_load_component_lib_counts(lib_with_xml):
    assert len(lib_with_xml.lib_components) == 4


def test_get_scd_by_class_name(lib_with_xml):
    scd = lib_with_xml.get_scd_by_class_name("altera_nios2")
    assert scd is not None
    assert scd.group == "cpu"
    assert scd.device == "nios2"
    assert scd.vendor == "ALTR"


def test_get_scd_by_class_name_multi(lib_with_xml):
    # Both class names in the comma-separated list should resolve
    assert lib_with_xml.get_scd_by_class_name("altera_nios2_qsys") is not None


def test_get_scd_by_class_name_case_insensitive(lib_with_xml):
    assert lib_with_xml.get_scd_by_class_name("ALTERA_NIOS2") is not None


def test_get_scd_not_found(lib_with_xml):
    assert lib_with_xml.get_scd_by_class_name("nonexistent_ip") is None


def test_auto_params_loaded(lib_with_xml):
    scd = lib_with_xml.get_scd_by_class_name("altera_nios2")
    assert len(scd.auto_params) == 2
    names = [p.dts_name for p in scd.auto_params]
    assert "clock-frequency" in names
    # dtsVName should be prefixed with vendor
    assert "ALTR,implementation" in names


def test_compatible_version_loaded(lib_with_xml):
    scd = lib_with_xml.get_scd_by_class_name("altera_nios2")
    # CompatibleVersion "1.0" should be in the list
    result = scd.get_compatibles("2.0")
    assert "ALTR,nios2-1.0" in result


def test_explicit_compatible_loaded(lib_with_xml):
    scd = lib_with_xml.get_scd_by_class_name("altera_avalon_cfi_flash")
    compatibles = scd.get_compatibles("1.0")
    assert "cfi-flash" in compatibles


def test_required_param_loaded(lib_with_xml):
    scd = lib_with_xml.get_scd_by_class_name("altera_avalon_pio")
    assert len(scd.get_required_params()) == 1
    assert scd.get_required_params()[0].name == "direction"
    assert scd.get_required_params()[0].value == "bidir"


def test_get_component_for_class_returns_basic_component(lib_with_xml):
    comp = lib_with_xml.get_component_for_class("altera_nios2", "cpu_0", "13.0")
    assert isinstance(comp, BasicComponent)
    assert comp.class_name == "altera_nios2"
    assert comp.instance_name == "cpu_0"
    assert comp.scd is not None
    assert comp.scd.group == "cpu"


def test_get_component_for_unknown_class(lib_with_xml):
    # Unknown class → BasicComponent with no SCD from library
    comp = lib_with_xml.get_component_for_class("mystery_ip", "foo_0", "1.0")
    assert isinstance(comp, BasicComponent)
    assert comp.scd is not None  # default SCD created by BasicComponent.__init__


def test_final_check_required_params_selects_best_scd(lib_with_xml):
    from sopc2dts_py.model.parameter import Parameter, DataType
    # altera_avalon_pio has a RequiredParameter direction=bidir.
    # A component without that param should end up with scd=None after final_check.
    comp_no_param = lib_with_xml.get_component_for_class("altera_avalon_pio", "pio_0", "1.0")
    result = lib_with_xml.final_check_on_component(comp_no_param)
    assert result.scd is None  # no matching SCD — required param absent

    # A component WITH the required param should keep its SCD.
    comp_ok = lib_with_xml.get_component_for_class("altera_avalon_pio", "pio_1", "1.0")
    comp_ok.add_param(Parameter("direction", "bidir", DataType.STRING))
    result_ok = lib_with_xml.final_check_on_component(comp_ok)
    assert result_ok.scd is not None


def test_load_component_libs_in_dir(tmp_path):
    (tmp_path / "sopc_components_a.xml").write_text(MINIMAL_LIB_XML, encoding="utf-8")
    (tmp_path / "sopc_components_b.xml").write_text(
        '<SOPC2DTS_COMPONENTLIB vendor="NXP">'
        '<S2DComponent classname="nxp_usb" group="usb" compatDevice="usb"/>'
        '</SOPC2DTS_COMPONENTLIB>',
        encoding="utf-8"
    )
    # A non-matching file should be ignored
    (tmp_path / "other.xml").write_text("<root/>", encoding="utf-8")

    lib = SopcComponentLib()
    lib.load_component_libs_in_dir(tmp_path)
    assert len(lib.lib_components) == 5  # 4 from a + 1 from b
    assert lib.get_scd_by_class_name("nxp_usb") is not None


def test_singleton():
    # get_instance always returns the same object
    assert SopcComponentLib.get_instance() is SopcComponentLib.get_instance()


def test_load_real_altera_lib():
    """Smoke: load the bundled sopc_components_altera.xml without errors."""
    repo_root = Path(__file__).parent.parent
    altera_xml = repo_root / "sopc_components_altera.xml"
    if not altera_xml.exists():
        pytest.skip("sopc_components_altera.xml not found")
    lib = SopcComponentLib()
    count = lib.load_component_lib(altera_xml)
    assert count > 0
    assert lib.get_scd_by_class_name("altera_nios2") is not None
    assert lib.get_scd_by_class_name("altera_avalon_uart") is not None
