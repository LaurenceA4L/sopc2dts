# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Port of sopc2dts.lib.BoardInfo and sopc2dts.lib.boardinfo.* — the "board
overlay" model. A boardinfo XML file layers board-specific information
(aliases, flash partitions, I2C/SPI slaves, ethernet MAC addresses, raw
devicetree append/replace/remove instructions, ...) on top of the system
parsed from a .sopcinfo / .qsys file.

The Java version parsed boardinfo XML through a streaming SAX
``ContentHandler`` chain (BoardInfo -> BoardInfoComponent -> ...). Python's
``xml.etree.ElementTree`` gives us the whole document as a tree, so instead
of replicating SAX start/end-element state machines we walk the parsed tree
once and build up exactly the same data model. Behaviour (including which
attributes are read, defaults, and the generated Xml) is kept faithful to
the Java original.
"""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING
from xml.etree import ElementTree as ET

from ..log import logger
from .enums import ParameterAction
from .parameter import Parameter, DataType

if TYPE_CHECKING:
    from .component import BasicComponent
    from .devicetree import DTNode


# ---------------------------------------------------------------------------
# FlashPartition — sopc2dts.lib.components.base.FlashPartition
# ---------------------------------------------------------------------------

class FlashPartition:
    """A single named region of a flash chip. Port of FlashPartition.java."""

    def __init__(self, name: Optional[str] = None, address: int = 0,
                 size: int = 0, readonly: bool = False) -> None:
        self.name = name
        self.address = address
        self.size = size
        self.readonly = readonly

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FlashPartition):
            return False
        return (self.readonly == other.readonly
                and self.address == other.address
                and self.size == other.size
                and self.name == other.name)

    def __repr__(self) -> str:
        return (f"FlashPartition({self.name!r}, addr=0x{self.address:x}, "
                f"size=0x{self.size:x}, readonly={self.readonly})")


# ---------------------------------------------------------------------------
# I2CSlave — sopc2dts.lib.boardinfo.I2CSlave
# ---------------------------------------------------------------------------

class I2CSlave:
    """A single chip on an I2C bus. Port of I2CSlave.java."""

    TAG_NAME = "I2CChip"

    def __init__(self, addr: int, name: Optional[str], label: Optional[str] = None) -> None:
        self.addr = addr
        self.name = name
        self.label = label

    @classmethod
    def from_attribs(cls, atts: Dict[str, str]) -> "I2CSlave":
        return cls(int(atts["addr"], 0), atts.get("name"), atts.get("label"))

    def get_xml(self) -> str:
        xml = f'\t\t<{self.TAG_NAME} addr="{self.addr}" name="{self.name}"'
        if self.label:
            xml += f' label="{self.label}"'
        xml += "/>\n"
        return xml

    def to_dt_node(self, board_info: "BoardInfo") -> "DTNode":
        from .devicetree import DTNode, DTProperty, DTPropHexNumVal
        node = DTNode(f"{self.name}@0x{self.addr:x}", label=self.label)
        node.add_property(DTProperty.from_string("compatible", self.name))
        reg = DTProperty("reg")
        reg.add_value(DTPropHexNumVal(self.addr))
        node.add_property(reg)
        return node

    def __lt__(self, other: "I2CSlave") -> bool:
        return self.addr < other.addr

    def __repr__(self) -> str:
        return f"I2CSlave(addr=0x{self.addr:x}, name={self.name!r}, label={self.label!r})"


# ---------------------------------------------------------------------------
# SpiSlave / SpiSlaveMMC — sopc2dts.lib.boardinfo.{SpiSlave,SpiSlaveMMC}
# ---------------------------------------------------------------------------

def _parse_bool(val: Optional[str]) -> bool:
    """
    Parse an XML boolean attribute value ("true"/"false", case-insensitive).

    PORTING DEVIATION: the Java constructor reads these via
    ``Boolean.getBoolean(atts.getValue("cpol"))`` etc. ``Boolean.getBoolean``
    does *not* parse its argument — it looks up a JVM *system property* of
    that name, so for any ordinary XML attribute value it always returns
    False. cpol/cpha/csHigh were therefore permanently stuck at False in the
    Java tool regardless of what the boardinfo file said. That's a bug in the
    original, not intended behaviour worth preserving, so the Python port
    parses the attribute value properly instead.
    """
    if val is None:
        return False
    return val.strip().lower() == "true"


class SpiSlave:
    """A single device on a SPI bus. Port of SpiSlave.java."""

    SLAVE_TYPE_NAMES = ["MMC Slot", "Custom"]

    def __init__(self, name: Optional[str], reg: int, compatible: Optional[str],
                 max_freq: int = 10000000, cpol: bool = False, cpha: bool = False,
                 cs_high: bool = False) -> None:
        self.name = name
        self.reg = reg
        self.compatible = compatible
        self.spi_max_frequency = max_freq
        self.cpol = cpol
        self.cpha = cpha
        self.cs_high = cs_high

    @classmethod
    def from_attribs(cls, atts: Dict[str, str]) -> "SpiSlave":
        return cls(
            atts.get("name"),
            int(atts["reg"], 0),
            atts.get("compatible"),
            int(atts["maxfreq"], 0),
            _parse_bool(atts.get("cpol")),
            _parse_bool(atts.get("cpha")),
            _parse_bool(atts.get("csHigh")),
        )

    @property
    def class_name(self) -> str:
        """Mirrors Java's getClass().getCanonicalName(), used in getXml()."""
        return "sopc2dts.lib.boardinfo.SpiSlave"

    def get_xml(self) -> str:
        return (f'\t\t<SpiSlave reg="{self.reg}" name="{self.name}" '
                f'class="{self.class_name}" compatible="{self.compatible}" '
                f'maxfreq="{self.spi_max_frequency}" cpol="{str(self.cpol).lower()}" '
                f'cpha="{str(self.cpha).lower()}" csHigh="{str(self.cs_high).lower()}">'
                f'</SpiSlave>\n')

    def to_dt_node(self, board_info: "BoardInfo") -> "DTNode":
        from .devicetree import DTNode, DTProperty, DTPropHexNumVal
        node = DTNode(f"{self.name}@0x{self.reg:x}")
        node.add_property(DTProperty.from_string("compatible", self.compatible))
        node.add_property(DTProperty.from_long("spi-max-frequency", self.spi_max_frequency))
        reg = DTProperty("reg")
        reg.add_value(DTPropHexNumVal(self.reg))
        node.add_property(reg)
        return node

    def __repr__(self) -> str:
        return f"SpiSlave({self.name!r}, reg=0x{self.reg:x}, compatible={self.compatible!r})"


class SpiSlaveMMC(SpiSlave):
    """An MMC/SD slot on a SPI bus. Port of SpiSlaveMMC.java."""

    def __init__(self, reg: int, name: str = "mmc-slot") -> None:
        super().__init__(name, reg, "mmc-spi-slot", 30000000)

    @classmethod
    def from_attribs(cls, atts: Dict[str, str]) -> "SpiSlaveMMC":
        # Java calls super(atts) which fully re-parses every attribute —
        # replicate that rather than the convenience constructor's defaults.
        slave = cls(int(atts["reg"], 0))
        slave.name = atts.get("name")
        slave.compatible = atts.get("compatible")
        slave.spi_max_frequency = int(atts["maxfreq"], 0)
        slave.cpol = _parse_bool(atts.get("cpol"))
        slave.cpha = _parse_bool(atts.get("cpha"))
        slave.cs_high = _parse_bool(atts.get("csHigh"))
        return slave

    @property
    def class_name(self) -> str:
        return "sopc2dts.lib.boardinfo.SpiSlaveMMC"

    def to_dt_node(self, board_info: "BoardInfo") -> "DTNode":
        from .devicetree import DTProperty
        node = super().to_dt_node(board_info)
        p = DTProperty("voltage-ranges")
        p.add_number_values([3200, 3400])
        node.add_property(p)
        return node


# ---------------------------------------------------------------------------
# BoardInfoComponent — sopc2dts.lib.boardinfo.BoardInfoComponent
# ---------------------------------------------------------------------------

class BoardInfoComponent:
    """
    Base class for board-info "components" — board-specific overlay info
    keyed by the instance name of a system component. Port of
    BoardInfoComponent.java (the abstract base, minus the SAX ContentHandler
    plumbing which ElementTree-based parsing makes unnecessary).
    """

    xml_tag_name: str = ""

    def __init__(self, tag: str, instance_name: Optional[str]) -> None:
        self.instance_name = instance_name
        self.xml_tag_name = tag

    def get_xml(self) -> str:
        raise NotImplementedError

    def get_instance_name(self) -> Optional[str]:
        return self.instance_name

    def get_xml_tag_name(self) -> str:
        return self.xml_tag_name

    @staticmethod
    def get_bic_for(local_name: str, elem: ET.Element) -> Optional["BoardInfoComponent"]:
        """Port of BoardInfoComponent.getBicFor — element-name based factory."""
        if local_name.lower() == BICEthernet.TAG_NAME.lower():
            return BICEthernet.from_element(local_name, elem)
        elif local_name.lower() == BICSpi.TAG_NAME.lower():
            return BICSpi.from_element(local_name, elem)
        elif local_name.lower() == BICDTAppend.TAG_NAME.lower():
            return BICDTAppend.from_element(local_name, elem)
        elif local_name.lower() == BICI2C.TAG_NAME.lower():
            return BICI2C.from_element(local_name, elem)
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.instance_name!r})"


# ---------------------------------------------------------------------------
# BICEthernet — sopc2dts.lib.boardinfo.BICEthernet
# ---------------------------------------------------------------------------

class BICEthernet(BoardInfoComponent):
    """Ethernet MAC/PHY board overlay info. Port of BICEthernet.java."""

    TAG_NAME = "Ethernet"

    def __init__(self, instance_name: Optional[str]) -> None:
        super().__init__(self.TAG_NAME, instance_name)
        self.mii_id: Optional[int] = None
        self.phy_id: Optional[int] = None
        self.mac: List[int] = [0, 0, 0, 0, 0, 0]

    @classmethod
    def from_element(cls, tag: str, elem: ET.Element) -> "BICEthernet":
        bic = cls(elem.get("name"))
        bic.xml_tag_name = tag
        s_val = elem.get("mii_id")
        if s_val is not None:
            bic.mii_id = int(s_val, 0)
        s_val = elem.get("phy_id")
        if s_val is not None:
            bic.phy_id = int(s_val, 0)
        bic.set_mac(elem.get("mac"))
        return bic

    def get_xml(self) -> str:
        res = f'<{self.TAG_NAME} name="{self.instance_name}" mac="{self.get_mac_string()}"'
        if self.mii_id is not None:
            res += f' mii_id="{self.mii_id}"'
        if self.phy_id is not None:
            res += f' phy_id="{self.phy_id}"'
        res += f'></{self.TAG_NAME}>\n'
        return res

    def get_mac_string(self) -> str:
        return ":".join(f"{b:02x}" for b in self.mac)

    def set_mac(self, val) -> None:
        if val is None:
            return
        if isinstance(val, str):
            parts = val.split(":")
            if len(parts) == 6:
                self.mac = [int(p, 16) for p in parts]
        elif isinstance(val, (list, tuple)) and len(val) == 6:
            self.mac = list(val)


# ---------------------------------------------------------------------------
# BICI2C — sopc2dts.lib.boardinfo.BICI2C
# ---------------------------------------------------------------------------

class BICI2C(BoardInfoComponent):
    """I2C bus board overlay info (a list of slave chips). Port of BICI2C.java."""

    TAG_NAME = "I2CBus"

    def __init__(self, instance_name: Optional[str]) -> None:
        super().__init__(self.TAG_NAME, instance_name)
        self.slaves: List[I2CSlave] = []

    @classmethod
    def from_element(cls, tag: str, elem: ET.Element) -> "BICI2C":
        # Java reads instanceName from the "master" attribute here, overriding
        # the "name" attribute the base constructor would have used.
        bic = cls(elem.get("master"))
        bic.xml_tag_name = tag
        for child in elem:
            if child.tag == I2CSlave.TAG_NAME:
                bic.slaves.append(I2CSlave.from_attribs(child.attrib))
        return bic

    def get_xml(self) -> str:
        xml = f"\t<{self.TAG_NAME}"
        if self.instance_name is not None:
            xml += f' master="{self.instance_name}"'
        xml += ">\n"
        for s in self.slaves:
            xml += s.get_xml()
        xml += f"\t</{self.TAG_NAME}>\n"
        return xml

    def set_slaves(self, slaves: List[I2CSlave]) -> None:
        self.slaves = slaves


# ---------------------------------------------------------------------------
# BICSpi — sopc2dts.lib.boardinfo.BICSpi
# ---------------------------------------------------------------------------

class BICSpi(BoardInfoComponent):
    """SPI bus board overlay info (a list of slave devices). Port of BICSpi.java."""

    TAG_NAME = "SpiMaster"
    _MMC_CLASS_NAME = "sopc2dts.lib.boardinfo.SpiSlaveMMC"

    def __init__(self, instance_name: Optional[str]) -> None:
        super().__init__(self.TAG_NAME, instance_name)
        self.slaves: List[SpiSlave] = []

    @classmethod
    def from_element(cls, tag: str, elem: ET.Element) -> "BICSpi":
        bic = cls(elem.get("name"))
        bic.xml_tag_name = tag
        for child in elem:
            if child.tag == "SpiSlave":
                class_name = child.get("class")
                if class_name == cls._MMC_CLASS_NAME:
                    bic.slaves.append(SpiSlaveMMC.from_attribs(child.attrib))
                else:
                    bic.slaves.append(SpiSlave.from_attribs(child.attrib))
        return bic

    def get_xml(self) -> str:
        res = f'\t<{self.TAG_NAME} name="{self.instance_name}">\n'
        for slave in self.slaves:
            res += slave.get_xml()
        res += f"\t</{self.TAG_NAME}>\n"
        return res

    def set_slaves(self, slaves: List[SpiSlave]) -> None:
        self.slaves = slaves


# ---------------------------------------------------------------------------
# BICDTAppend — sopc2dts.lib.boardinfo.BICDTAppend
# ---------------------------------------------------------------------------

class DTAppendType(Enum):
    NODE = auto()
    PROP_BOOL = auto()
    PROP_NUMBER = auto()
    PROP_STRING = auto()
    PROP_HEX = auto()
    PROP_BYTE = auto()
    PROP_PHANDLE = auto()


class DTAppendAction(Enum):
    ADD = auto()
    REPLACE = auto()
    REMOVE = auto()


_DT_APPEND_TYPE_NAMES = {
    DTAppendType.NODE: "node",
    DTAppendType.PROP_BOOL: "bool",
    DTAppendType.PROP_HEX: "hex",
    DTAppendType.PROP_BYTE: "byte",
    DTAppendType.PROP_NUMBER: "number",
    DTAppendType.PROP_STRING: "string",
    DTAppendType.PROP_PHANDLE: "phandle",
}


class BICDTAppend(BoardInfoComponent):
    """
    Raw devicetree-append/replace/remove instruction from a boardinfo file.
    Port of BICDTAppend.java.
    """

    TAG_NAME = "DTAppend"
    VAL_TAG = "val"

    def __init__(self, instance_name: Optional[str]) -> None:
        super().__init__(self.TAG_NAME, instance_name)
        self.parent_path: Optional[List[str]] = None
        self.parent_label: Optional[str] = None
        self.values: List[Optional[str]] = []
        self.types: List[DTAppendType] = []
        self.action: DTAppendAction = DTAppendAction.REPLACE
        self.label: Optional[str] = None

    @classmethod
    def from_element(cls, tag: str, elem: ET.Element) -> "BICDTAppend":
        bic = cls(elem.get("name"))
        bic.xml_tag_name = tag
        bic.add_value(elem.get("val"))
        bic._add_type(elem.get("type"))
        bic._set_path(elem.get("parentpath"))
        bic.set_parent_label(elem.get("parentlabel"))
        bic.set_label(elem.get("newlabel"))
        bic.set_action(elem.get("action"))

        # Nested <val> children (only present when there's more than one value)
        for child in elem:
            if child.tag == cls.VAL_TAG:
                t = child.get("type")
                if t is not None:
                    bic._add_type(t)
                elif bic.types:
                    bic.types.append(bic.types[-1])
                else:
                    logger.error("unspecified type for val tag found by BICDTAppend")
                bic.add_value((child.text or "").strip() if child.text else "")
            else:
                logger.error("unexpected start tag, %s found by BICDTAppend", child.tag)

        if not bic.types:
            bic.values.clear()  # No types implies a boolean which has no data either
        return bic

    def set_label(self, label: Optional[str]) -> None:
        self.label = label

    def set_parent_label(self, parent_label: Optional[str]) -> None:
        self.parent_label = parent_label

    def _set_path(self, path: Optional[str]) -> None:
        if path is not None:
            if path.startswith("/"):
                path = path[1:]
            self.parent_path = path.split("/")
        else:
            self.parent_path = None

    def add_value(self, val: Optional[str]) -> None:
        if val is not None:
            self.values.append(val)

    def _add_type(self, t: Optional[str]) -> None:
        if t is None:
            return
        tl = t.lower()
        if tl == "node":
            self.types.append(DTAppendType.NODE)
        elif tl == "number":
            self.types.append(DTAppendType.PROP_NUMBER)
        elif tl == "string":
            self.types.append(DTAppendType.PROP_STRING)
        elif tl == "hex":
            self.types.append(DTAppendType.PROP_HEX)
        elif tl == "byte":
            self.types.append(DTAppendType.PROP_BYTE)
        elif tl == "phandle":
            self.types.append(DTAppendType.PROP_PHANDLE)
        elif tl != "bool":
            logger.error("BICDTAppend.setType unknown type: %s", t)

    @staticmethod
    def _action_to_string(action: DTAppendAction) -> str:
        return action.name.lower()

    @staticmethod
    def _type_to_string(t: DTAppendType) -> str:
        return _DT_APPEND_TYPE_NAMES.get(t, "")

    def get_xml(self) -> str:
        xml = f'<{self.TAG_NAME} name="{self.instance_name}" '
        if len(self.types) == 1:
            xml += f'type="{self._type_to_string(self.types[0])}"'
        if self.parent_label is not None:
            xml += f' parentlabel="{self.parent_label}"'
        if self.parent_path is not None:
            xml += ' parentpath="' + "/".join(self.parent_path) + '"'
        if self.label is not None:
            xml += f' newlabel="{self.label}"'
        xml += f' action="{self._action_to_string(self.action)}"'

        n = len(self.values)
        if n == 1:
            value = self.values[0]
            if value is not None:
                xml += f' val="{value}"'
            xml += "/>\n"
        elif n == 0:
            xml += "/>\n"
        else:
            xml += ">\n"
            for i, value in enumerate(self.values):
                if i < len(self.types):
                    xml += f'    <{self.VAL_TAG} type="{self._type_to_string(self.types[i])}">{value}</{self.VAL_TAG}>\n'
                else:
                    xml += f'    <{self.VAL_TAG}>{value}</{self.VAL_TAG}>\n'
            xml += f"</{self.TAG_NAME}>\n"
        return xml

    def get_action(self) -> DTAppendAction:
        return self.action

    def get_parent_path(self) -> Optional[List[str]]:
        return self.parent_path

    def get_parent_label(self) -> Optional[str]:
        return self.parent_label

    def get_values(self) -> List[Optional[str]]:
        return self.values

    def get_types(self) -> List[DTAppendType]:
        return self.types

    def get_label(self) -> Optional[str]:
        return self.label

    def set_action(self, action) -> None:
        if action is None:
            return
        if isinstance(action, DTAppendAction):
            self.action = action
            return
        al = action.lower()
        if al == "add":
            self.action = DTAppendAction.ADD
        elif al == "replace":
            self.action = DTAppendAction.REPLACE
        elif al == "remove":
            self.action = DTAppendAction.REMOVE
        else:
            logger.error("Unsupported DTAppend action '%s'.", action)


# ---------------------------------------------------------------------------
# BoardInfo — sopc2dts.lib.BoardInfo
# ---------------------------------------------------------------------------

class PovType(Enum):
    CPU = auto()
    PCI = auto()


class SortType(Enum):
    NONE = auto()
    ADDRESS = auto()
    NAME = auto()
    LABEL = auto()


class RangesStyle(Enum):
    NONE = auto()
    FOR_BRIDGE = auto()
    FOR_EACH_CHILD = auto()


class AltrStyle(Enum):
    AUTO = auto()
    FORCE_UPPER = auto()
    FORCE_LOWER = auto()


class BoardInfo:
    """
    Top-level board overlay model. Port of sopc2dts.lib.BoardInfo — parses a
    boardinfo XML file (via ElementTree rather than a SAX ContentHandler
    chain) and exposes the same lookups the rest of the tool relies on.
    """

    def __init__(self) -> None:
        self.source_file: Optional[Path] = None
        self.include_time: bool = True
        self.show_clock_tree: bool = False
        self.show_conduits: bool = False
        self.show_resets: bool = False
        self.show_streaming: bool = False
        self.boot_args: Optional[str] = None

        self.bics: List[BoardInfoComponent] = []
        self.aliases: List[Parameter] = []
        self.alias_refs: List[Parameter] = []
        self.irq_master_class_ignore: List[str] = []
        self.irq_master_label_ignore: List[str] = []
        self.memory_nodes: Optional[List[str]] = []

        self._altr_style: AltrStyle = AltrStyle.AUTO
        self._pov: str = ""
        self._pov_type: PovType = PovType.CPU
        self._ranges_style: RangesStyle = RangesStyle.FOR_EACH_CHILD
        self._sort_type: SortType = SortType.NONE
        self._dump_parameters: ParameterAction = ParameterAction.NONE

        self._flash_partitions: Dict[Optional[str], List[FlashPartition]] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, source: Path) -> "BoardInfo":
        bi = cls()
        bi.load(source)
        return bi

    def load(self, source: Path) -> None:
        self.source_file = Path(source)
        tree = ET.parse(self.source_file)
        self._load_root(tree.getroot())

    def _load_root(self, root: ET.Element) -> None:
        if root.tag.lower() != "boardinfo":
            logger.warning("Boardinfo: unexpected root element %s", root.tag)
        self.set_pov(root.get("pov"))
        for elem in root:
            self._load_top_level_element(elem)

    def _load_top_level_element(self, elem: ET.Element) -> None:
        local_name = elem.tag

        bic = BoardInfoComponent.get_bic_for(local_name, elem)
        if bic is not None:
            self.bics.append(bic)
            return

        ll = local_name.lower()
        if ll == "alias":
            name = elem.get("name")
            value = elem.get("value")
            if value is not None:
                logger.info("alias %s %s", name, value)
                self.aliases.append(Parameter(name, value, DataType.STRING))
            else:
                value = elem.get("label")
                if value is not None:
                    logger.info("alias %s %s", name, value)
                    self.alias_refs.append(Parameter(name, value, DataType.STRING))
                else:
                    logger.warning("alias %s is badly formatted in boardinfo file", name)
        elif ll == "bootargs":
            self.boot_args = elem.get("val")
        elif ll == "flashpartitions":
            chip = elem.get("chip")
            partitions: List[FlashPartition] = []
            self._flash_partitions[chip] = partitions
            for child in elem:
                self._load_partition_element(child, partitions)
        elif ll == "irqmasterignore":
            ignore = elem.get("className")
            if ignore is not None:
                self.irq_master_class_ignore.append(ignore)
            ignore = elem.get("label")
            if ignore is not None:
                self.irq_master_label_ignore.append(ignore)
        elif ll == "memory":
            self.memory_nodes = []
            for child in elem:
                if child.tag.lower() == "node":
                    self.memory_nodes.append(child.get("chip"))
        elif ll == "chosen":
            for child in elem:
                self._load_top_level_element(child)
        else:
            logger.warning("Boardinfo: Unhandled element %s", local_name)

    def _load_partition_element(self, elem: ET.Element, partitions: List[FlashPartition]) -> None:
        if elem.tag.lower() != "partition":
            return
        part = FlashPartition()
        part.name = elem.get("name")
        part.address = int(elem.get("address"), 0)
        part.size = int(elem.get("size"), 0)
        for child in elem:
            if child.tag.lower() == "readonly":
                part.readonly = True
        partitions.append(part)

    # ------------------------------------------------------------------
    # Pov
    # ------------------------------------------------------------------

    def set_pov(self, pov: Optional[str]) -> None:
        if pov is not None:
            self._pov = pov

    def get_pov(self) -> str:
        return self._pov

    @property
    def pov(self) -> str:
        return self._pov

    # ------------------------------------------------------------------
    # Boot args
    # ------------------------------------------------------------------

    def get_boot_args(self) -> Optional[str]:
        return self.boot_args

    def set_boot_args(self, boot_args: Optional[str]) -> None:
        self.boot_args = boot_args

    # ------------------------------------------------------------------
    # BIC lookups
    # ------------------------------------------------------------------

    def get_bic_for_chip(self, instance_name: Optional[str],
                         tag_name: Optional[str] = None) -> Optional[BoardInfoComponent]:
        for bic in self.bics:
            if ((instance_name is None and bic.instance_name is None) or
                    (instance_name is not None and bic.instance_name is not None
                     and instance_name.lower() == bic.instance_name.lower())):
                if tag_name is None or tag_name.lower() == bic.xml_tag_name.lower():
                    return bic
        return None

    def set_bic(self, new_bic: BoardInfoComponent) -> None:
        old_bic = self.get_bic_for_chip(new_bic.instance_name)
        if old_bic is None:
            self.bics.append(new_bic)
        elif old_bic is not new_bic:
            self.bics.remove(old_bic)
            self.bics.append(new_bic)

    def get_ethernet_for_chip(self, instance_name: Optional[str]) -> BICEthernet:
        bic = self.get_bic_for_chip(instance_name, BICEthernet.TAG_NAME)
        if isinstance(bic, BICEthernet):
            return bic
        return BICEthernet(instance_name)

    def get_i2c_for_chip(self, instance_name: Optional[str]) -> BICI2C:
        bic = self.get_bic_for_chip(instance_name)
        if bic is not None:
            if isinstance(bic, BICI2C):
                return bic
        else:
            # Get wildcard
            for b in self.bics:
                if b.instance_name is None and isinstance(b, BICI2C):
                    return b
        return BICI2C(instance_name)

    def get_dt_appends(self) -> List[BICDTAppend]:
        return [bic for bic in self.bics if isinstance(bic, BICDTAppend)]

    def set_ethernet_for_chip(self, be: BICEthernet) -> None:
        old = self.get_bic_for_chip(be.instance_name)
        if old is not None:
            self.bics.remove(old)
        self.bics.append(be)

    def set_i2c_bus_for_chip(self, instance_name: Optional[str], slaves: List[I2CSlave]) -> None:
        bic = self.get_bic_for_chip(instance_name, BICI2C.TAG_NAME)
        if bic is None:
            bic = BICI2C(instance_name)
            self.bics.append(bic)
        bic.set_slaves(slaves)

    # ------------------------------------------------------------------
    # Flash partitions
    # ------------------------------------------------------------------

    def get_partitions_for_chip(self, instance_name: Optional[str]) -> Optional[List[FlashPartition]]:
        res = self._flash_partitions.get(instance_name)
        if res is None:
            # Try to get a backup/wildcard map
            res = self._flash_partitions.get(None)
        return res

    def set_partitions_for_chip(self, instance_name: Optional[str], partitions: List[FlashPartition]) -> None:
        self._flash_partitions[instance_name] = partitions

    # ------------------------------------------------------------------
    # Memory nodes
    # ------------------------------------------------------------------

    def get_memory_nodes(self) -> Optional[List[str]]:
        return self.memory_nodes

    def set_memory_nodes(self, nodes: Optional[List[str]]) -> None:
        self.memory_nodes = nodes

    # ------------------------------------------------------------------
    # Output style settings
    # ------------------------------------------------------------------

    def get_pov_type(self) -> PovType:
        return self._pov_type

    def set_pov_type(self, pov_type) -> None:
        if isinstance(pov_type, PovType):
            self._pov_type = pov_type
            return
        name = pov_type.lower()
        if name == "cpu":
            self._pov_type = PovType.CPU
        elif name in ("pci", "pcie"):
            self._pov_type = PovType.PCI

    def get_ranges_style(self) -> RangesStyle:
        return self._ranges_style

    def set_ranges_style(self, style) -> None:
        if isinstance(style, RangesStyle):
            self._ranges_style = style
            return
        name = style.lower()
        if name == "child":
            self._ranges_style = RangesStyle.FOR_EACH_CHILD
        elif name == "bridge":
            self._ranges_style = RangesStyle.FOR_BRIDGE
        elif name == "none":
            self._ranges_style = RangesStyle.NONE
        else:
            logger.warning("Unsupported ranges-style '%s'", style)

    def get_sort_type(self) -> SortType:
        return self._sort_type

    def set_sort_type(self, sort_type) -> None:
        if isinstance(sort_type, SortType):
            self._sort_type = sort_type
            return
        name = sort_type.lower()
        if name == "address":
            self._sort_type = SortType.ADDRESS
        elif name == "name":
            self._sort_type = SortType.NAME
        elif name == "label":
            self._sort_type = SortType.LABEL
        else:
            self._sort_type = SortType.NONE

    # ------------------------------------------------------------------
    # IRQ master filtering
    # ------------------------------------------------------------------

    def is_valid_irq_master(self, comp: "BasicComponent") -> bool:
        for imi in self.irq_master_class_ignore:
            if comp.class_name.lower() == imi.lower():
                return False
        for imi in self.irq_master_label_ignore:
            if comp.instance_name.lower() == imi.lower():
                return False
        return True

    # ------------------------------------------------------------------
    # Misc accessors (mirror Java getters/setters)
    # ------------------------------------------------------------------

    def get_aliases(self) -> List[Parameter]:
        return self.aliases

    def get_alias_refs(self) -> List[Parameter]:
        return self.alias_refs

    def get_altr_style(self) -> AltrStyle:
        return self._altr_style

    def set_altr_style(self, style: AltrStyle) -> None:
        self._altr_style = style

    def is_include_time(self) -> bool:
        return self.include_time

    def set_include_time(self, val: bool) -> None:
        self.include_time = val

    def is_show_clock_tree(self) -> bool:
        return self.show_clock_tree

    def is_show_conduits(self) -> bool:
        return self.show_conduits

    def is_show_resets(self) -> bool:
        return self.show_resets

    def is_show_streaming(self) -> bool:
        return self.show_streaming

    def show_clock_tree_on(self) -> None:
        self.show_clock_tree = True

    def show_conduits_on(self) -> None:
        self.show_conduits = True

    def show_resets_on(self) -> None:
        self.show_resets = True

    def show_streaming_on(self) -> None:
        self.show_streaming = True

    def get_source_file(self) -> Optional[Path]:
        return self.source_file

    def set_source_file(self, source_file: Path) -> None:
        self.source_file = source_file

    def get_dump_parameters(self) -> ParameterAction:
        return self._dump_parameters

    def set_dump_parameters(self, action: ParameterAction) -> None:
        self._dump_parameters = action

    # ------------------------------------------------------------------
    # XML serialisation — port of BoardInfo.getXml()
    # ------------------------------------------------------------------

    def get_xml(self) -> str:
        xml = "<BoardInfo"
        if self._pov:
            xml += f' pov="{self._pov}"'
        xml += ">\n"

        if self.memory_nodes:
            xml += "\t<Memory>\n"
            for node in self.memory_nodes:
                if node:
                    xml += f'\t\t<Node chip="{node}"/>\n'
            xml += "\t</Memory>\n"

        if self.boot_args:
            xml += ("\t<Chosen>\n"
                    f'\t\t<Bootargs val="{self.boot_args}"/>\n'
                    "\t</Chosen>\n")

        for chip, partitions in self._flash_partitions.items():
            if partitions:
                xml += "\t<FlashPartitions"
                if chip is not None:
                    xml += f' chip="{chip}"'
                xml += ">\n"
                for part in partitions:
                    xml += (f'\t\t<Partition name="{part.name}"'
                            f' address="0x{part.address:x}"'
                            f' size="0x{part.size:x}">\n')
                    if part.readonly:
                        xml += "\t\t\t<readonly/>\n"
                    xml += "\t\t</Partition>\n"
                xml += "\t</FlashPartitions>\n"

        for imi in self.irq_master_class_ignore:
            xml += f'\t<IRQMasterIgnore className="{imi}"/>\n'
        for imi in self.irq_master_label_ignore:
            xml += f'\t<IRQMasterIgnore label="{imi}"/>\n'

        for p in self.aliases:
            xml += f'\t<alias name="{p.name}" value="{p.value}/>\n'
        for p in self.alias_refs:
            xml += f'\t<alias name="{p.name}" label="{p.value}/>\n'

        for bic in self.bics:
            xml += bic.get_xml()

        xml += "</BoardInfo>\n"
        return xml

    def __repr__(self) -> str:
        return f"BoardInfo(pov={self._pov!r}, {len(self.bics)} bics)"
