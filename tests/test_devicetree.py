# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for the devicetree model layer."""

import pytest

from sopc2dts_py.model.devicetree import (
    DTPropType,
    DTPropNumVal, DTPropHexNumVal, DTPropStringVal, DTPropByteVal, DTPropPHandleVal,
    DTProperty, DTNode, DTBlob, DTHelper,
)


# ---------------------------------------------------------------------------
# DTPropVal subtypes
# ---------------------------------------------------------------------------

def test_num_val_str():
    assert DTPropNumVal(42).value_str() == "42"
    assert DTPropNumVal(0).value_str() == "0"


def test_hex_val_str():
    assert DTPropHexNumVal(0xFF200000).value_str() == "0xff200000"
    assert DTPropHexNumVal(0).value_str() == "0x00000000"


def test_hex_val_negative():
    # Java: negative stored as unsigned 32-bit hex
    assert DTPropHexNumVal(-1).value_str() == "0xffffffff"


def test_string_val_str():
    v = DTPropStringVal("console=ttyS0,115200")
    assert v.value_str() == '"console=ttyS0,115200"'


def test_string_val_bytes():
    v = DTPropStringVal("hi")
    assert v.get_value_bytes() == b"hi\x00"


def test_byte_val_str():
    assert DTPropByteVal(0xAB).value_str() == "ab"
    assert DTPropByteVal(0).value_str() == "00"


def test_byte_val_bytes():
    assert DTPropByteVal(0xFF).get_value_bytes() == bytes([0xFF])


def test_phandle_val_from_string():
    v = DTPropPHandleVal("intc_0")
    assert v.value_str() == "&intc_0"
    assert v.label == "intc_0"


def test_phandle_val_from_component():
    class FakeComp:
        instance_name = "cpu_0"
    v = DTPropPHandleVal(FakeComp())
    assert v.value_str() == "&cpu_0"


def test_type_compatibility():
    num = DTPropNumVal(1)
    ph = DTPropPHandleVal("x")
    assert num.is_type_compatible(DTPropType.NUMBER)
    assert num.is_type_compatible(DTPropType.PHANDLE)   # NUMBER ↔ PHANDLE compatible
    assert ph.is_type_compatible(DTPropType.NUMBER)
    assert not num.is_type_compatible(DTPropType.STRING)
    assert not num.is_type_compatible(DTPropType.BYTE)


# ---------------------------------------------------------------------------
# DTProperty serialisation
# ---------------------------------------------------------------------------

def test_property_no_value():
    p = DTProperty("interrupt-controller")
    assert p.to_string(0) == "interrupt-controller;\n"


def test_property_single_string():
    p = DTProperty.from_string("status", "okay")
    assert p.to_string(0) == 'status = "okay";\n'


def test_property_multiple_strings():
    p = DTProperty.from_strings("compatible", ["altera,nios2", "altera,nios2-r1"])
    s = p.to_string(0)
    assert '"altera,nios2"' in s
    assert '"altera,nios2-r1"' in s
    assert s.endswith(";\n")


def test_property_hex_number():
    p = DTProperty("reg")
    p.add_value(DTPropHexNumVal(0xFF200000))
    p.add_value(DTPropHexNumVal(0x1000))
    s = p.to_string(0)
    assert "0xff200000" in s
    assert "0x00001000" in s
    assert s.startswith("reg = <")


def test_property_decimal_number():
    p = DTProperty.from_long("clock-frequency", 50000000)
    s = p.to_string(0)
    assert "50000000" in s


def test_property_phandle():
    p = DTProperty("interrupt-parent")
    p.add_value(DTPropPHandleVal("intc_0"))
    s = p.to_string(0)
    assert "&intc_0" in s


def test_property_mixed_number_phandle():
    # NUMBER and PHANDLE are type-compatible — share <> brackets
    p = DTProperty("clocks")
    p.add_value(DTPropPHandleVal("clk_0"))
    p.add_value(DTPropNumVal(0))
    s = p.to_string(0)
    assert "<&clk_0 0>" in s


def test_property_byte_array():
    p = DTProperty("local-mac-address")
    p.add_byte_values([0x00, 0x11, 0x22, 0x33, 0x44, 0x55])
    s = p.to_string(0)
    assert s.startswith("local-mac-address = [")
    assert "00 11 22 33 44 55" in s


def test_property_label():
    p = DTProperty("reg", label="my_reg")
    p.add_value(DTPropHexNumVal(0))
    assert "my_reg: reg" in p.to_string(0)


def test_property_comment():
    p = DTProperty("reg", comment="base address")
    p.add_value(DTPropHexNumVal(0xFF200000))
    assert "/* base address */" in p.to_string(0)


def test_property_replace_existing():
    node = DTNode("test")
    p1 = DTProperty.from_long("reg", 0x1000)
    p2 = DTProperty.from_long("reg", 0x2000)
    node.add_property(p1)
    node.add_property(p2, replace_existing=True)
    assert node.get_property_by_name("reg").values[0].val == 0x2000


def test_property_duplicate_rejected(caplog):
    import logging
    node = DTNode("test")
    node.add_property(DTProperty.from_long("reg", 1))
    with caplog.at_level(logging.ERROR, logger="sopc2dts"):
        node.add_property(DTProperty.from_long("reg", 2))
    assert len(node.properties) == 1  # duplicate not added


# ---------------------------------------------------------------------------
# DTNode serialisation
# ---------------------------------------------------------------------------

def test_node_basic_structure():
    node = DTNode("/")
    s = node.to_string(0)
    assert "/ {" in s
    assert "}; //end /" in s


def test_node_with_label():
    node = DTNode("cpu@0", label="cpu0")
    s = node.to_string(0)
    assert "cpu0: cpu@0 {" in s
    assert "//end cpu@0 (cpu0)" in s


def test_node_with_property():
    node = DTNode("memory@0")
    node.add_property(DTProperty.from_string("device_type", "memory"))
    s = node.to_string(0)
    assert '"memory"' in s


def test_node_children_indented():
    root = DTNode("/")
    child = DTNode("chosen")
    child.add_property(DTProperty.from_string("bootargs", "console=ttyS0,115200"))
    root.add_child(child)
    s = root.to_string(0)
    # chosen node should be indented one level
    assert "\tchosen {" in s


def test_node_get_property_by_name():
    node = DTNode("cpu@0")
    node.add_property(DTProperty.from_string("compatible", "altera,nios2"))
    assert node.get_property_by_name("compatible") is not None
    assert node.get_property_by_name("missing") is None


def test_node_comment():
    node = DTNode("cpu@0", comment=" This is a comment ")
    s = node.to_string(0)
    assert "/* This is a comment */" in s


# ---------------------------------------------------------------------------
# DTBlob string table
# ---------------------------------------------------------------------------

def test_dtblob_register_string():
    dtb = DTBlob()
    off1 = dtb.register_string("compatible")
    off2 = dtb.register_string("reg")
    off3 = dtb.register_string("compatible")  # duplicate
    assert off1 == 0
    assert off2 > off1
    assert off3 == off1  # same offset returned


def test_dtblob_string_table_content():
    dtb = DTBlob()
    dtb.register_string("status")
    assert b"status\x00" in dtb.string_table


# ---------------------------------------------------------------------------
# DTHelper arithmetic
# ---------------------------------------------------------------------------

def test_helper_long_to_arr_1cell():
    assert DTHelper.long_to_long_arr(0xFF200000, 1) == [0xFF200000]


def test_helper_long_to_arr_2cell():
    arr = DTHelper.long_to_long_arr(0x1_00000000, 2)
    assert arr == [1, 0]


def test_helper_arr_to_long():
    assert DTHelper.long_arr_to_long([0xFF200000]) == 0xFF200000
    # Note: long_to_long_arr and long_arr_to_long are NOT inverses for 2-cell
    # arrays — (this matches the original Java behaviour). longArrToLong treats
    # index 0 as the low-order cell (shift by 0), while long2longArr stores
    # the HIGH word at index 0. From what I can determine, the Java code never 
    # roundtrips 2-cell values through both functions.
    assert DTHelper.long_arr_to_long([1, 0]) == 1


def test_helper_hex_string():
    assert DTHelper.long_arr_to_hex_string([0xFF200000]) == "0xff200000"
    assert DTHelper.long_arr_to_hex_string([0]) == "0x00"


def test_helper_add_scalar():
    result = DTHelper.long_arr_add([0xFF200000], 0x1000)
    assert result == [0xFF201000]


def test_helper_add_carry():
    result = DTHelper.long_arr_add([0xFFFFFFFF], 1)
    assert result == [0]  # overflow wraps within cell width


def test_helper_subtract():
    result = DTHelper.long_arr_subtract([0xFF201000], 0x1000)
    assert result == [0xFF200000]


def test_helper_compare_equal():
    assert DTHelper.long_arr_compare([0xFF200000], 0xFF200000) == 0


def test_helper_compare_less():
    assert DTHelper.long_arr_compare([0xFF200000], 0xFF201000) < 0


def test_helper_compare_greater():
    assert DTHelper.long_arr_compare([0xFF201000], 0xFF200000) > 0


def test_helper_get_child_by_label():
    root = DTNode("/")
    child = DTNode("cpu@0", label="cpu0")
    root.add_child(child)
    assert DTHelper.get_child_by_label(root, "cpu0") is child
    assert DTHelper.get_child_by_label(root, "missing") is None


def test_helper_parse_long_string():
    assert DTHelper.parse_long_string("0xFF200000", 1) == [0xFF200000]
    assert DTHelper.parse_long_string("50000000", 1) == [50000000]
