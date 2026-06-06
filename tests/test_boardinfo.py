# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for the boardinfo overlay model."""

from pathlib import Path

import pytest

from sopc2dts_py.model.boardinfo import (
    BoardInfo, BoardInfoComponent, FlashPartition,
    I2CSlave, SpiSlave, SpiSlaveMMC,
    BICEthernet, BICI2C, BICSpi, BICDTAppend,
    DTAppendType, DTAppendAction,
    PovType, SortType, RangesStyle, AltrStyle,
)


# ---------------------------------------------------------------------------
# FlashPartition
# ---------------------------------------------------------------------------

def test_flash_partition_equality():
    a = FlashPartition("uboot", 0x0, 0x40000, readonly=True)
    b = FlashPartition("uboot", 0x0, 0x40000, readonly=True)
    c = FlashPartition("uboot", 0x0, 0x40000, readonly=False)
    assert a == b
    assert a != c
    assert a != "not a partition"


# ---------------------------------------------------------------------------
# I2CSlave
# ---------------------------------------------------------------------------

def test_i2c_slave_from_attribs_and_xml():
    s = I2CSlave.from_attribs({"addr": "0x50", "name": "eeprom", "label": "eeprom0"})
    assert s.addr == 0x50
    assert s.name == "eeprom"
    assert s.label == "eeprom0"
    xml = s.get_xml()
    assert 'addr="80"' in xml
    assert 'name="eeprom"' in xml
    assert 'label="eeprom0"' in xml


def test_i2c_slave_to_dt_node():
    s = I2CSlave(0x50, "eeprom", "eeprom0")
    node = s.to_dt_node(BoardInfo())
    assert node.name == "eeprom@0x50"
    assert node.label == "eeprom0"
    assert node.get_property_by_name("compatible") is not None
    assert node.get_property_by_name("reg") is not None


def test_i2c_slave_ordering():
    a = I2CSlave(0x10, "a")
    b = I2CSlave(0x50, "b")
    assert a < b
    assert sorted([b, a]) == [a, b]


# ---------------------------------------------------------------------------
# SpiSlave / SpiSlaveMMC
# ---------------------------------------------------------------------------

def test_spi_slave_to_dt_node():
    slave = SpiSlave("flash", 0, "micron,n25q128", 50000000)
    node = slave.to_dt_node(BoardInfo())
    assert node.name == "flash@0x0"
    assert node.get_property_by_name("compatible") is not None
    assert node.get_property_by_name("spi-max-frequency") is not None
    assert node.get_property_by_name("reg") is not None


def test_spi_slave_mmc_adds_voltage_ranges():
    slave = SpiSlaveMMC(1)
    assert slave.compatible == "mmc-spi-slot"
    assert slave.spi_max_frequency == 30000000
    node = slave.to_dt_node(BoardInfo())
    assert node.get_property_by_name("voltage-ranges") is not None
    assert node.get_property_by_name("compatible") is not None


def test_spi_slave_class_name_in_xml():
    assert "SpiSlave" in SpiSlave("x", 0, "y").get_xml()
    assert "SpiSlaveMMC" in SpiSlaveMMC(0).get_xml()


def test_spi_slave_cpol_cpha_cshigh_parsed_correctly():
    # PORTING DEVIATION: Java read these via Boolean.getBoolean(attrValue),
    # which checks a JVM system property (not the attribute) and so always
    # returned False — a bug. The Python port parses "true"/"false" properly.
    slave = SpiSlave.from_attribs({
        "reg": "0", "name": "flash", "compatible": "jedec,spi-nor",
        "maxfreq": "1000000", "cpol": "true", "cpha": "TRUE", "csHigh": "false",
    })
    assert slave.cpol is True
    assert slave.cpha is True
    assert slave.cs_high is False


def test_spi_slave_mmc_from_attribs_parses_booleans():
    slave = SpiSlaveMMC.from_attribs({
        "reg": "1", "name": "mmc-slot", "compatible": "mmc-spi-slot",
        "maxfreq": "30000000", "cpol": "false", "cpha": "true", "csHigh": "true",
    })
    assert slave.cpol is False
    assert slave.cpha is True
    assert slave.cs_high is True


# ---------------------------------------------------------------------------
# BICEthernet
# ---------------------------------------------------------------------------

def test_bic_ethernet_mac_string_default():
    bic = BICEthernet("emac0")
    assert bic.get_mac_string() == "00:00:00:00:00:00"


def test_bic_ethernet_set_mac_from_string():
    bic = BICEthernet("emac0")
    bic.set_mac("de:ad:be:ef:00:01")
    assert bic.mac == [0xde, 0xad, 0xbe, 0xef, 0x00, 0x01]
    assert bic.get_mac_string() == "de:ad:be:ef:00:01"


def test_bic_ethernet_xml_roundtrip():
    bic = BICEthernet("emac0")
    bic.set_mac("de:ad:be:ef:00:01")
    bic.mii_id = 1
    bic.phy_id = 2
    xml = bic.get_xml()
    assert 'name="emac0"' in xml
    assert 'mac="de:ad:be:ef:00:01"' in xml
    assert 'mii_id="1"' in xml
    assert 'phy_id="2"' in xml


# ---------------------------------------------------------------------------
# BICI2C / BICSpi
# ---------------------------------------------------------------------------

def test_bic_i2c_slave_management_and_xml():
    bic = BICI2C("i2c_0")
    bic.set_slaves([I2CSlave(0x50, "eeprom"), I2CSlave(0x68, "rtc")])
    xml = bic.get_xml()
    assert 'master="i2c_0"' in xml
    assert "eeprom" in xml
    assert "rtc" in xml


def test_bic_spi_slave_management_and_xml():
    bic = BICSpi("spi_0")
    bic.set_slaves([SpiSlave("flash", 0, "jedec,spi-nor"), SpiSlaveMMC(1)])
    xml = bic.get_xml()
    assert 'name="spi_0"' in xml
    assert "flash" in xml
    assert "mmc-slot" in xml


# ---------------------------------------------------------------------------
# BICDTAppend
# ---------------------------------------------------------------------------

def test_bic_dt_append_defaults():
    bic = BICDTAppend("foo")
    assert bic.action == DTAppendAction.REPLACE
    assert bic.values == []
    assert bic.types == []


def test_bic_dt_append_set_action_from_string():
    bic = BICDTAppend("foo")
    bic.set_action("add")
    assert bic.action == DTAppendAction.ADD
    bic.set_action("remove")
    assert bic.action == DTAppendAction.REMOVE
    bic.set_action("bogus")
    assert bic.action == DTAppendAction.REMOVE  # unchanged on bad input


def test_bic_dt_append_path_parsing():
    bic = BICDTAppend("foo")
    bic._set_path("/soc/bus/device")
    assert bic.parent_path == ["soc", "bus", "device"]
    bic._set_path(None)
    assert bic.parent_path is None


def test_bic_dt_append_xml_single_value():
    bic = BICDTAppend("foo")
    bic.add_value("okay")
    bic._add_type("string")
    bic.set_label("mylabel")
    xml = bic.get_xml()
    assert 'name="foo"' in xml
    assert 'type="string"' in xml
    assert 'val="okay"' in xml
    assert 'newlabel="mylabel"' in xml
    assert xml.strip().endswith("/>")


def test_bic_dt_append_xml_multi_value():
    bic = BICDTAppend("foo")
    bic.add_value("1")
    bic.add_value("2")
    bic._add_type("number")
    bic._add_type("number")
    xml = bic.get_xml()
    assert "<val type=\"number\">1</val>" in xml
    assert "<val type=\"number\">2</val>" in xml
    assert xml.strip().endswith("</DTAppend>")


# ---------------------------------------------------------------------------
# BoardInfoComponent factory
# ---------------------------------------------------------------------------

def test_get_bic_for_dispatches_by_tag():
    import xml.etree.ElementTree as ET
    elem = ET.fromstring('<Ethernet name="emac0" mac="00:11:22:33:44:55"/>')
    bic = BoardInfoComponent.get_bic_for("Ethernet", elem)
    assert isinstance(bic, BICEthernet)
    assert bic.instance_name == "emac0"

    elem = ET.fromstring('<Unknown name="x"/>')
    assert BoardInfoComponent.get_bic_for("Unknown", elem) is None


# ---------------------------------------------------------------------------
# BoardInfo — settings / lookups
# ---------------------------------------------------------------------------

def test_board_info_pov():
    bi = BoardInfo()
    assert bi.get_pov() == ""
    bi.set_pov("cpu_0")
    assert bi.get_pov() == "cpu_0"
    bi.set_pov(None)
    assert bi.get_pov() == "cpu_0"  # None does not overwrite, matches Java


def test_board_info_pov_type_and_ranges_and_sort():
    bi = BoardInfo()
    bi.set_pov_type("pcie")
    assert bi.get_pov_type() == PovType.PCI
    bi.set_pov_type("cpu")
    assert bi.get_pov_type() == PovType.CPU

    bi.set_ranges_style("bridge")
    assert bi.get_ranges_style() == RangesStyle.FOR_BRIDGE
    bi.set_ranges_style("bogus")
    assert bi.get_ranges_style() == RangesStyle.FOR_BRIDGE  # unchanged on bad input

    bi.set_sort_type("address")
    assert bi.get_sort_type() == SortType.ADDRESS
    bi.set_sort_type("bogus")
    assert bi.get_sort_type() == SortType.NONE  # falls back to NONE, matches Java


def test_board_info_bic_lookup_and_set():
    bi = BoardInfo()
    eth = BICEthernet("emac0")
    bi.set_bic(eth)
    assert bi.get_bic_for_chip("emac0") is eth
    assert bi.get_bic_for_chip("EMAC0") is eth
    assert bi.get_bic_for_chip("missing") is None


def test_board_info_get_ethernet_for_chip_creates_default():
    bi = BoardInfo()
    eth = bi.get_ethernet_for_chip("emac0")
    assert isinstance(eth, BICEthernet)
    assert eth.instance_name == "emac0"
    # not stored automatically
    assert bi.get_bic_for_chip("emac0") is None


def test_board_info_set_i2c_bus_for_chip():
    bi = BoardInfo()
    slaves = [I2CSlave(0x50, "eeprom")]
    bi.set_i2c_bus_for_chip("i2c_0", slaves)
    bic = bi.get_bic_for_chip("i2c_0", BICI2C.TAG_NAME)
    assert isinstance(bic, BICI2C)
    assert bic.slaves == slaves


def test_board_info_get_dt_appends():
    bi = BoardInfo()
    append = BICDTAppend("foo")
    bi.bics.append(append)
    bi.bics.append(BICEthernet("emac0"))
    assert bi.get_dt_appends() == [append]


def test_board_info_flash_partitions_fallback():
    bi = BoardInfo()
    fallback = [FlashPartition("all", 0, 0x100000)]
    specific = [FlashPartition("uboot", 0, 0x40000)]
    bi.set_partitions_for_chip(None, fallback)
    bi.set_partitions_for_chip("flash_0", specific)

    assert bi.get_partitions_for_chip("flash_0") == specific
    assert bi.get_partitions_for_chip("flash_1") == fallback  # falls back to wildcard


def test_board_info_irq_master_ignore():
    bi = BoardInfo()
    bi.irq_master_class_ignore.append("altera_avalon_pio")
    bi.irq_master_label_ignore.append("special_irq_0")

    class FakeComp:
        class_name = "altera_avalon_pio"
        instance_name = "pio_0"

    class FakeComp2:
        class_name = "altera_nios2"
        instance_name = "special_irq_0"

    class FakeComp3:
        class_name = "altera_nios2"
        instance_name = "cpu_0"

    assert bi.is_valid_irq_master(FakeComp()) is False
    assert bi.is_valid_irq_master(FakeComp2()) is False
    assert bi.is_valid_irq_master(FakeComp3()) is True


# ---------------------------------------------------------------------------
# BoardInfo — XML loading
# ---------------------------------------------------------------------------

BOARDINFO_XML = """<?xml version="1.0"?>
<BoardInfo pov="cpu_0">
    <Memory>
        <Node chip="onchip_ram_0"/>
        <Node chip="sdram_0"/>
    </Memory>
    <Chosen>
        <Bootargs val="console=ttyS0,115200 root=/dev/mtdblock0"/>
    </Chosen>
    <FlashPartitions chip="epcs_0">
        <Partition name="uboot" address="0x0" size="0x40000">
            <readonly/>
        </Partition>
        <Partition name="rootfs" address="0x40000" size="0x3c0000"/>
    </FlashPartitions>
    <IRQMasterIgnore className="altera_avalon_pio"/>
    <IRQMasterIgnore label="special_irq_0"/>
    <alias name="serial0" value="/soc/serial@0"/>
    <alias name="eth0" label="emac0"/>
    <Ethernet name="emac0" mac="de:ad:be:ef:00:01" mii_id="0"/>
    <I2CBus master="i2c_0">
        <I2CChip addr="0x50" name="eeprom" label="eeprom0"/>
    </I2CBus>
    <SpiMaster name="spi_0">
        <SpiSlave reg="0" name="flash" class="sopc2dts.lib.boardinfo.SpiSlave"
                  compatible="jedec,spi-nor" maxfreq="50000000" cpol="false" cpha="false" csHigh="false"/>
    </SpiMaster>
    <DTAppend name="leds" type="node" parentpath="soc" newlabel="leds_0" action="add" val="okay"/>
</BoardInfo>
"""


def test_board_info_load_from_xml(tmp_path):
    p = tmp_path / "board.xml"
    p.write_text(BOARDINFO_XML, encoding="utf-8")

    bi = BoardInfo.from_file(p)

    assert bi.get_pov() == "cpu_0"
    assert bi.get_memory_nodes() == ["onchip_ram_0", "sdram_0"]
    assert bi.get_boot_args() == "console=ttyS0,115200 root=/dev/mtdblock0"

    parts = bi.get_partitions_for_chip("epcs_0")
    assert len(parts) == 2
    assert parts[0].name == "uboot"
    assert parts[0].readonly is True
    assert parts[1].readonly is False

    assert bi.irq_master_class_ignore == ["altera_avalon_pio"]
    assert bi.irq_master_label_ignore == ["special_irq_0"]

    assert len(bi.aliases) == 1
    assert bi.aliases[0].name == "serial0"
    assert len(bi.alias_refs) == 1
    assert bi.alias_refs[0].name == "eth0"

    eth = bi.get_ethernet_for_chip("emac0")
    assert eth.get_mac_string() == "de:ad:be:ef:00:01"
    assert eth.mii_id == 0

    i2c = bi.get_bic_for_chip("i2c_0", BICI2C.TAG_NAME)
    assert isinstance(i2c, BICI2C)
    assert len(i2c.slaves) == 1
    assert i2c.slaves[0].name == "eeprom"

    spi = bi.get_bic_for_chip("spi_0", BICSpi.TAG_NAME)
    assert isinstance(spi, BICSpi)
    assert len(spi.slaves) == 1
    assert spi.slaves[0].name == "flash"

    appends = bi.get_dt_appends()
    assert len(appends) == 1
    assert appends[0].instance_name == "leds"
    assert appends[0].types == [DTAppendType.NODE]
    assert appends[0].action == DTAppendAction.ADD
