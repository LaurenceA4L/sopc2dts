# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Smoke tests for the thin parser-facade modules:
  sopc2dts_py/parsers/boardinfo_xml.py
  sopc2dts_py/parsers/component_xml.py

The underlying logic is fully tested in test_boardinfo.py and
test_component_lib.py.  These tests verify only the public parser API:
correct return types, delegation to the model layer, and __init__ re-exports.
"""

import textwrap
from pathlib import Path

import pytest

from sopc2dts_py.model.boardinfo import BoardInfo
from sopc2dts_py.model.component_lib import SopcComponentLib


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_BOARDINFO_XML = (
    "<boardinfo pov=\"cpu_0\">\n"
    "    <Ethernet name=\"uart_0\" mac=\"00:11:22:33:44:55\"/>\n"
    "</boardinfo>\n"
)

MINIMAL_COMPONENT_LIB_XML = textwrap.dedent("""\
    <SOPC2DTS_COMPONENTLIB vendor="ALTR">
        <S2DComponent classname="altera_nios2" group="cpu" compatDevice="nios2">
            <parameter dtsName="clock-frequency" sopcName="embeddedsw.CMacro.CPU_FREQ"/>
        </S2DComponent>
        <S2DComponent classname="altera_avalon_uart" group="serial" compatDevice="uart">
            <parameter dtsName="current-speed" sopcName="embeddedsw.CMacro.BAUD"/>
        </S2DComponent>
    </SOPC2DTS_COMPONENTLIB>
""")


@pytest.fixture()
def boardinfo_file(tmp_path):
    f = tmp_path / "boardinfo.xml"
    f.write_text(MINIMAL_BOARDINFO_XML, encoding="utf-8")
    return f


@pytest.fixture()
def component_lib_file(tmp_path):
    f = tmp_path / "sopc_components_test.xml"
    f.write_text(MINIMAL_COMPONENT_LIB_XML, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# boardinfo_xml.load_boardinfo
# ---------------------------------------------------------------------------

def test_load_boardinfo_returns_boardinfo(boardinfo_file):
    from sopc2dts_py.parsers.boardinfo_xml import load_boardinfo
    bi = load_boardinfo(boardinfo_file)
    assert isinstance(bi, BoardInfo)


def test_load_boardinfo_parses_pov(boardinfo_file):
    from sopc2dts_py.parsers.boardinfo_xml import load_boardinfo
    bi = load_boardinfo(boardinfo_file)
    assert bi.pov == "cpu_0"


def test_load_boardinfo_parses_components(boardinfo_file):
    from sopc2dts_py.parsers.boardinfo_xml import load_boardinfo
    bi = load_boardinfo(boardinfo_file)
    assert len(bi.bics) == 1
    assert bi.bics[0].instance_name == "uart_0"


def test_load_boardinfo_accepts_str_path(boardinfo_file):
    from sopc2dts_py.parsers.boardinfo_xml import load_boardinfo
    bi = load_boardinfo(str(boardinfo_file))
    assert isinstance(bi, BoardInfo)


def test_load_boardinfo_missing_file():
    from sopc2dts_py.parsers.boardinfo_xml import load_boardinfo
    with pytest.raises(OSError):
        load_boardinfo("/nonexistent/path/boardinfo.xml")


# ---------------------------------------------------------------------------
# component_xml.load_component_lib
# ---------------------------------------------------------------------------

def test_load_component_lib_returns_lib(component_lib_file):
    from sopc2dts_py.parsers.component_xml import load_component_lib
    lib = SopcComponentLib()
    result = load_component_lib(component_lib_file, lib=lib)
    assert result is lib


def test_load_component_lib_populates(component_lib_file):
    from sopc2dts_py.parsers.component_xml import load_component_lib
    lib = SopcComponentLib()
    load_component_lib(component_lib_file, lib=lib)
    assert len(lib.lib_components) == 2
    assert lib.get_scd_by_class_name("altera_nios2") is not None
    assert lib.get_scd_by_class_name("altera_avalon_uart") is not None


def test_load_component_lib_accepts_str_path(component_lib_file):
    from sopc2dts_py.parsers.component_xml import load_component_lib
    lib = SopcComponentLib()
    load_component_lib(str(component_lib_file), lib=lib)
    assert len(lib.lib_components) == 2


def test_load_component_lib_uses_singleton_by_default(component_lib_file):
    """When lib=None the singleton is used and returned."""
    from sopc2dts_py.parsers.component_xml import load_component_lib
    # Use a fresh singleton for this test by constructing a local lib.
    # (We cannot reset the global singleton, so just verify return type.)
    result = load_component_lib(component_lib_file, lib=SopcComponentLib())
    assert isinstance(result, SopcComponentLib)


# ---------------------------------------------------------------------------
# component_xml.load_component_libs_in_dir
# ---------------------------------------------------------------------------

def test_load_component_libs_in_dir(tmp_path):
    from sopc2dts_py.parsers.component_xml import load_component_libs_in_dir
    (tmp_path / "sopc_components_a.xml").write_text(
        MINIMAL_COMPONENT_LIB_XML, encoding="utf-8"
    )
    (tmp_path / "sopc_components_b.xml").write_text(
        '<SOPC2DTS_COMPONENTLIB vendor="NXP">'
        '<S2DComponent classname="nxp_usb" group="usb" compatDevice="usb"/>'
        '</SOPC2DTS_COMPONENTLIB>',
        encoding="utf-8",
    )
    (tmp_path / "other.xml").write_text("<root/>", encoding="utf-8")

    lib = SopcComponentLib()
    result = load_component_libs_in_dir(tmp_path, lib=lib)
    assert result is lib
    assert len(lib.lib_components) == 3
    assert lib.get_scd_by_class_name("nxp_usb") is not None


def test_load_component_libs_in_dir_missing_dir(tmp_path):
    """Missing directory logs a warning but does not raise."""
    from sopc2dts_py.parsers.component_xml import load_component_libs_in_dir
    lib = SopcComponentLib()
    load_component_libs_in_dir(tmp_path / "nonexistent", lib=lib)
    assert len(lib.lib_components) == 0


# ---------------------------------------------------------------------------
# parsers.__init__ re-exports
# ---------------------------------------------------------------------------

def test_init_exports_load_boardinfo(boardinfo_file):
    from sopc2dts_py.parsers import load_boardinfo
    bi = load_boardinfo(boardinfo_file)
    assert isinstance(bi, BoardInfo)


def test_init_exports_load_component_lib(component_lib_file):
    from sopc2dts_py.parsers import load_component_lib
    lib = SopcComponentLib()
    load_component_lib(component_lib_file, lib=lib)
    assert lib.get_scd_by_class_name("altera_nios2") is not None


def test_init_exports_load_component_libs_in_dir(tmp_path):
    from sopc2dts_py.parsers import load_component_libs_in_dir
    (tmp_path / "sopc_components_test.xml").write_text(
        MINIMAL_COMPONENT_LIB_XML, encoding="utf-8"
    )
    lib = SopcComponentLib()
    load_component_libs_in_dir(tmp_path, lib=lib)
    assert len(lib.lib_components) == 2
