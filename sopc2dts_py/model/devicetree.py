# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2012-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Port of the sopc2dts.lib.devicetree package:

  DTElement        — abstract base (name, label, comment, indent helper)
  DTPropVal        — abstract property value base
  DTPropNumVal     — decimal cell value  <N>
  DTPropHexNumVal  — hex cell value      <0xNNNNNNNN>
  DTPropStringVal  — string value        "..."
  DTPropByteVal    — byte value          [XX]
  DTPropPHandleVal — phandle reference   &label
  DTProperty       — named list of DTPropVal
  DTNode           — DT node (name, label, children, properties)
  DTBlob           — FDT binary serialiser (stub — full impl in Phase 2 generator)
  DTHelper         — multi-cell address/size arithmetic utilities
"""

from __future__ import annotations
import struct
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .component import BasicComponent


# ---------------------------------------------------------------------------
# DTPropType
# ---------------------------------------------------------------------------

class DTPropType(Enum):
    STRING = auto()
    NUMBER = auto()
    BYTE   = auto()
    BOOL   = auto()
    PHANDLE = auto()
    BAREREF = auto()


# ---------------------------------------------------------------------------
# DTElement — abstract base
# ---------------------------------------------------------------------------

class DTElement(ABC):
    """Port of sopc2dts.lib.devicetree.DTElement."""

    def __init__(
        self,
        name: str,
        label: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> None:
        self.name = name
        self.label = label
        self.comment = comment

    @staticmethod
    def indent(level: int) -> str:
        return "\t" * level

    @abstractmethod
    def to_string(self, indent: int = 0) -> str: ...

    def __str__(self) -> str:
        return self.to_string(0)


# ---------------------------------------------------------------------------
# DTPropVal hierarchy
# ---------------------------------------------------------------------------

class DTPropVal(ABC):
    """Port of sopc2dts.lib.devicetree.DTPropVal — abstract property value."""

    def __init__(
        self,
        prop_type: DTPropType,
        opening: str,
        closing: str,
        separator: str,
    ) -> None:
        self.type = prop_type
        self.opening = opening
        self.closing = closing
        self.separator = separator

    @abstractmethod
    def get_value_bytes(self) -> bytes: ...

    @abstractmethod
    def value_str(self) -> str: ...

    def is_type_compatible(self, other_type: DTPropType) -> bool:
        """NUMBER and PHANDLE are compatible with each other."""
        if self.type == other_type:
            return True
        compatible_pair = {DTPropType.NUMBER, DTPropType.PHANDLE}
        return self.type in compatible_pair and other_type in compatible_pair


class DTPropNumVal(DTPropVal):
    """Decimal cell value — <N>."""

    def __init__(self, val: int) -> None:
        super().__init__(DTPropType.NUMBER, "<", ">", " ")
        self.val = val

    def get_value_bytes(self) -> bytes:
        return struct.pack(">I", self.val & 0xFFFFFFFF)

    def value_str(self) -> str:
        return str(self.val)


class DTPropHexNumVal(DTPropNumVal):
    """Hex cell value — <0xNNNNNNNN>. Extends DTPropNumVal."""

    def value_str(self) -> str:
        v = self.val
        if v < 0:
            v = v + 0x100000000
        return f"0x{v:08x}"


class DTPropStringVal(DTPropVal):
    """String value — "..."."""

    def __init__(self, value: str) -> None:
        super().__init__(DTPropType.STRING, "", "", ", ")
        self.value = value

    def get_value_bytes(self) -> bytes:
        return self.value.encode("utf-8") + b"\x00"

    def value_str(self) -> str:
        return f'"{self.value}"'

    def get_string_value(self) -> str:
        return self.value

    def set_string_value(self, value: str) -> None:
        self.value = value


class DTPropByteVal(DTPropVal):
    """Byte value — [XX]."""

    def __init__(self, val: int) -> None:
        super().__init__(DTPropType.BYTE, "[", "]", " ")
        self.val = val & 0xFF

    def get_value_bytes(self) -> bytes:
        return bytes([self.val])

    def value_str(self) -> str:
        return f"{self.val:02x}"


class DTPropPHandleVal(DTPropVal):
    """Phandle reference — &label. Resolved to a numeric handle in DTB output."""

    def __init__(self, comp_or_label, phandle: int = 0) -> None:
        super().__init__(DTPropType.PHANDLE, "<", ">", " ")
        if isinstance(comp_or_label, str):
            self.label = comp_or_label
        else:
            # BasicComponent — use instance name as label
            self.label = comp_or_label.instance_name
        self.phandle = phandle

    def get_value_bytes(self) -> bytes:
        return struct.pack(">I", self.phandle & 0xFFFFFFFF)

    def value_str(self) -> str:
        return f"&{self.label}"


class DTPropBareRefVal(DTPropVal):
    """
    Bare label reference used as a whole property value — ``foo = &label;``
    (no enclosing ``<...>``), a dtc source-level convenience most commonly
    seen in ``aliases`` nodes. Unlike ``DTPropPHandleVal`` (a phandle *cell*,
    always written inside ``<...>``), this renders with no brackets at all;
    it is dtc's own job to expand it to the referenced node's path at
    compile time, so we simply pass the ``&label`` text through unchanged.
    """

    def __init__(self, label: str) -> None:
        super().__init__(DTPropType.BAREREF, "", "", "")
        self.label = label

    def get_value_bytes(self) -> bytes:
        # Never compiled to a DTB directly by this tool; dtc resolves and
        # expands bare references to a path string at its own compile time.
        return f"&{self.label}".encode("utf-8") + b"\x00"

    def value_str(self) -> str:
        return f"&{self.label}"


# ---------------------------------------------------------------------------
# DTProperty
# ---------------------------------------------------------------------------

class DTProperty(DTElement):
    """
    A named devicetree property holding a list of DTPropVal values.
    Port of sopc2dts.lib.devicetree.DTProperty.
    """

    OF_DT_PROP = 0x03

    def __init__(
        self,
        name: str,
        label: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> None:
        super().__init__(name, label, comment)
        self._values: List[DTPropVal] = []
        self.num_vals_per_row: int = 0

    # ------------------------------------------------------------------
    # Convenience constructors (mirror Java overloads)
    # ------------------------------------------------------------------

    @classmethod
    def from_long(cls, name: str, val: int) -> "DTProperty":
        p = cls(name)
        p.add_value(DTPropNumVal(val))
        return p

    @classmethod
    def from_string(cls, name: str, val: str) -> "DTProperty":
        p = cls(name)
        p.add_value(DTPropStringVal(val))
        return p

    @classmethod
    def from_strings(cls, name: str, vals: List[str]) -> "DTProperty":
        p = cls(name)
        p.add_string_values(vals)
        return p

    # ------------------------------------------------------------------
    # Value management
    # ------------------------------------------------------------------

    def add_value(self, val: DTPropVal) -> None:
        self._values.append(val)

    def add_hex_values(self, vals: List[int]) -> None:
        for v in vals:
            self._values.append(DTPropHexNumVal(v))

    def add_number_values(self, vals: List[int]) -> None:
        for v in vals:
            self._values.append(DTPropNumVal(v))

    def add_string_values(self, vals: List[str]) -> None:
        for v in vals:
            self._values.append(DTPropStringVal(v))

    def add_byte_values(self, vals: List[int]) -> None:
        for v in vals:
            self._values.append(DTPropByteVal(v))

    @property
    def values(self) -> List[DTPropVal]:
        return self._values

    def set_num_values_per_row(self, n: int) -> None:
        self.num_vals_per_row = n

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def get_all_value_bytes(self) -> bytes:
        result = b""
        for v in self._values:
            result += v.get_value_bytes()
        return result

    def get_bytes(self, dtb: "DTBlob") -> bytes:
        val_bytes = self.get_all_value_bytes()
        padded_len = (len(val_bytes) + 3) & ~3
        header = struct.pack(">III",
            self.OF_DT_PROP,
            len(val_bytes),
            dtb.register_string(self.name),
        )
        padding = bytes(padded_len - len(val_bytes))
        return header + val_bytes + padding

    def to_string(self, indent: int = 0) -> str:
        res = self.indent(indent)
        if self.label:
            res += f"{self.label}: "
        res += self.name

        prev_val: Optional[DTPropVal] = None
        val_num = 0
        nl_str = ""

        for val in self._values:
            if self.num_vals_per_row > 0 and (val_num % self.num_vals_per_row) == 0:
                nl_str = (
                    f"{val.closing},\n{self.indent(indent + 1)}{val.opening}"
                )
            else:
                nl_str = ""

            if prev_val is None:
                res += f" = {val.opening}"
            elif not val.is_type_compatible(prev_val.type):
                res += f"{prev_val.closing},{nl_str}{val.opening}"
            elif nl_str:
                res += nl_str
            else:
                res += val.separator

            res += val.value_str()
            prev_val = val
            val_num += 1

        if prev_val is not None:
            res += prev_val.closing

        if self.comment:
            res += f";\t/* {self.comment} */\n"
        else:
            res += ";\n"

        return res


# ---------------------------------------------------------------------------
# DTNode
# ---------------------------------------------------------------------------

class DTNode(DTElement):
    """
    A devicetree node with optional label, children, and properties.
    Port of sopc2dts.lib.devicetree.DTNode.
    """

    OF_DT_BEGIN_NODE = 0x01
    OF_DT_END_NODE   = 0x02

    def __init__(
        self,
        name: str,
        label: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> None:
        super().__init__(name, label, comment)
        self._children: List[DTNode] = []
        self._properties: List[DTProperty] = []

    # ------------------------------------------------------------------
    # Children
    # ------------------------------------------------------------------

    def add_child(self, child: "DTNode") -> None:
        if child is not None:
            self._children.append(child)

    def remove_child(self, child: "DTNode") -> None:
        """Remove a child from this node (no-op if not present)."""
        try:
            self._children.remove(child)
        except ValueError:
            pass

    def replace_child(self, old: "DTNode", new: "DTNode") -> None:
        """Replace ``old`` with ``new`` in place, preserving child order."""
        idx = self._children.index(old)
        self._children[idx] = new

    @property
    def children(self) -> List["DTNode"]:
        return self._children

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def add_property(self, prop: DTProperty, replace_existing: bool = False) -> None:
        if prop is None:
            return
        existing = self.get_property_by_name(prop.name)
        if existing is not None:
            if replace_existing:
                idx = self._properties.index(existing)
                self._properties[idx] = prop
            else:
                from ..log import logger
                logger.error(
                    "Cannot add duplicate property '%s' to node '%s' (%s)",
                    prop.name, self.name, self.label,
                )
        else:
            self._properties.append(prop)

    def get_property_by_name(self, name: str) -> Optional[DTProperty]:
        for p in self._properties:
            if p.name == name:
                return p
        return None

    def remove_property(self, prop: DTProperty) -> None:
        """Remove a property from this node (no-op if not present)."""
        try:
            self._properties.remove(prop)
        except ValueError:
            pass

    @property
    def properties(self) -> List[DTProperty]:
        return self._properties

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_string(self, indent: int = 0) -> str:
        res = "\n"
        if self.comment:
            res += f"{self.indent(indent)}/*{self.comment}*/\n"
        res += self.indent(indent)
        if self.label:
            res += f"{self.label}: "
        res += f"{self.name} {{\n"

        for prop in self._properties:
            res += prop.to_string(indent + 1)
        for child in self._children:
            res += child.to_string(indent + 1)

        res += self.indent(indent) + "};"
        res += f" //end {self.name}"
        if self.label:
            res += f" ({self.label})"
        res += "\n"
        return res

    def get_bytes(self, dtb: "DTBlob") -> bytes:
        node_name = self.name or ""
        # Name aligned to 4 bytes
        name_bytes = node_name.encode("utf-8") + b"\x00"
        padded = ((len(name_bytes) + 3) & ~3)
        header = struct.pack(">I", self.OF_DT_BEGIN_NODE) + name_bytes.ljust(padded, b"\x00")
        footer = struct.pack(">I", self.OF_DT_END_NODE)

        body = b""
        for prop in self._properties:
            body += prop.get_bytes(dtb)
        for child in self._children:
            body += child.get_bytes(dtb)

        return header + body + footer


# ---------------------------------------------------------------------------
# DTBlob — FDT binary serialiser (stub; full impl in Phase 2 generator)
# ---------------------------------------------------------------------------

class DTBlob:
    """
    FDT binary serialiser.
    Port of sopc2dts.lib.devicetree.DTBlob.

    Builds a valid Flattened Device Tree (DTB) blob from a DTNode tree.
    Also used as the string-table registry by DTNode/DTProperty.get_bytes().
    """

    FDT_MAGIC          = 0xD00DFEED
    DTB_VERSION        = 17
    DTB_COMPAT_VERSION = 16
    OF_DT_END          = 0x09
    HEADER_SIZE        = 40

    def __init__(self, phandle_offset: int = 0) -> None:
        self._next_phandle: int = phandle_offset + 1
        self._string_table: bytes = b""
        self._string_offsets: dict = {}
        self._root_node: Optional["DTNode"] = None

    # ------------------------------------------------------------------
    # Root node
    # ------------------------------------------------------------------

    def set_root_node(self, node: "DTNode") -> None:
        self._root_node = node

    def get_root_node(self) -> Optional["DTNode"]:
        return self._root_node

    # ------------------------------------------------------------------
    # String table (used by DTProperty.get_bytes during serialisation)
    # ------------------------------------------------------------------

    def register_string(self, s: str) -> int:
        """Add s to the string table if not present; return its offset."""
        if s in self._string_offsets:
            return self._string_offsets[s]
        offset = len(self._string_table)
        self._string_offsets[s] = offset
        self._string_table += s.encode("utf-8") + b"\x00"
        return offset

    @property
    def string_table(self) -> bytes:
        return self._string_table

    # ------------------------------------------------------------------
    # Phandle management
    # ------------------------------------------------------------------

    def get_phandle(self, label: str) -> int:
        """Return (creating if needed) the phandle for the node with the given label."""
        if self._root_node is None:
            return 0
        return self._find_or_assign_phandle(label, self._root_node)

    def _find_or_assign_phandle(self, label: str, node: "DTNode") -> int:
        if label and label == node.label:
            prop = node.get_property_by_name("linux,phandle")
            if prop is None:
                ph = self._next_phandle
                self._next_phandle += 1
                p = DTProperty("linux,phandle")
                p.add_value(DTPropNumVal(ph))
                node.add_property(p)
                return ph
            else:
                v = prop.values[0] if prop.values else None
                return int(v.val) if v is not None else 0
        for child in node.children:
            ph = self._find_or_assign_phandle(label, child)
            if ph != 0:
                return ph
        return 0

    def set_phandles(self, node: "DTNode") -> None:
        """Walk tree, resolving all DTPropPHandleVal labels to numeric phandles."""
        for prop in node.properties:
            for val in prop.values:
                if isinstance(val, DTPropPHandleVal):
                    val.phandle = self.get_phandle(val.label)
        for child in node.children:
            self.set_phandles(child)

    # ------------------------------------------------------------------
    # Binary assembly
    # ------------------------------------------------------------------

    def get_bytes(self) -> bytes:
        """Assemble and return the complete DTB binary blob."""
        if self._root_node is None:
            raise ValueError("DTBlob has no root node")
        mrm = self._get_mem_reserve_map()
        self.set_phandles(self._root_node)
        dt = self._get_dt()
        strings = self._string_table
        total_size = self.HEADER_SIZE + len(mrm) + len(dt) + len(strings)
        out = struct.pack(
            ">IIIIIIIIII",
            self.FDT_MAGIC,
            total_size,
            self.HEADER_SIZE + len(mrm),            # off_dt_struct
            self.HEADER_SIZE + len(mrm) + len(dt),  # off_dt_strings
            self.HEADER_SIZE,                        # off_mem_rsvmap
            self.DTB_VERSION,
            self.DTB_COMPAT_VERSION,
            0xFEEDBEEF,                             # boot_cpuid_phys
            len(strings),                           # size_dt_strings
            len(dt),                                # size_dt_struct
        )
        return out + mrm + dt + strings

    def _get_dt(self) -> bytes:
        dt = self._root_node.get_bytes(self)
        return dt + struct.pack(">I", self.OF_DT_END)

    @staticmethod
    def _get_mem_reserve_map() -> bytes:
        """Empty memory reservation map: one all-zero sentinel entry."""
        return struct.pack(">QQ", 0, 0)

    # ------------------------------------------------------------------
    # Static helpers (used by DTNode/DTProperty serialisation)
    # ------------------------------------------------------------------

    @staticmethod
    def put_u32(val: int, buf: bytearray, offset: int) -> None:
        struct.pack_into(">I", buf, offset, val & 0xFFFFFFFF)

    @staticmethod
    def put_string_aligned(s: str, buf: bytearray, offset: int) -> None:
        encoded = s.encode("utf-8") + b"\x00"
        for i, b in enumerate(encoded):
            buf[offset + i] = b


# ---------------------------------------------------------------------------
# DTHelper — multi-cell address/size arithmetic
# ---------------------------------------------------------------------------

class DTHelper:
    """
    Utility functions for multi-cell (64-bit / 128-bit) address arithmetic.
    Port of sopc2dts.lib.devicetree.DTHelper.

    Addresses in DTS are arrays of 32-bit cells. A 64-bit address uses
    2 cells [high, low]. All methods work with List[int] of 32-bit unsigned cells.
    """

    @staticmethod
    def parse_long_string(s: str, num_cells: int) -> List[int]:
        val = int(s, 0)
        if num_cells == 1:
            return [val & 0xFFFFFFFF]
        elif num_cells == 2:
            return DTHelper.long_to_long_arr(val, num_cells)
        else:
            from ..log import logger
            logger.error("parse_long_string: unsupported cell count %d", num_cells)
            return [0] * num_cells

    @staticmethod
    def long_to_long_arr(val: int, num_cells: int) -> List[int]:
        result = [0] * num_cells
        if num_cells == 1:
            result[0] = val & 0xFFFFFFFF
        elif num_cells >= 2:
            result[-1] = val & 0xFFFFFFFF
            result[-2] = (val >> 32) & 0xFFFFFFFF
        return result

    @staticmethod
    def long_arr_to_long(arr: List[int]) -> int:
        if len(arr) > 2:
            from ..log import logger
            logger.error("long_arr_to_long: values over 64-bit not supported")
        result = 0
        for i, v in enumerate(arr):
            result += (v & 0xFFFFFFFF) << (i * 32)
        return result

    @staticmethod
    def long_arr_to_hex_string(arr: List[int]) -> str:
        value_found = False
        res = "0x"
        for i in range(len(arr) - 1, -1, -1):
            if value_found:
                res += f"{arr[i]:08x}"
            elif arr[i] != 0:
                res += format(arr[i], "x")
                value_found = True
            elif i == 0:
                res += "00"
        return res

    @staticmethod
    def long_arr_add(arr: List[int], val) -> List[int]:
        """Add a scalar int or another cell array to arr."""
        result = list(arr)
        if isinstance(val, list):
            carry = 0
            for i in range(len(result)):
                s = result[i] + (val[i] if i < len(val) else 0) + carry
                result[i] = s & 0xFFFFFFFF
                carry = (s >> 32) & 0xFFFFFFFF
        else:
            carry = val
            for i in range(len(result)):
                s = result[i] + (carry & 0xFFFFFFFF)
                result[i] = s & 0xFFFFFFFF
                carry = ((carry >> 32) & 0xFFFFFFFF) + ((s >> 32) & 0xFFFFFFFF)
        return result

    @staticmethod
    def long_arr_subtract(arr: List[int], val: int) -> List[int]:
        result = list(arr)
        borrow = val
        for i in range(len(result)):
            d = result[i] - (borrow & 0xFFFFFFFF)
            result[i] = d & 0xFFFFFFFF
            borrow = ((borrow >> 32) & 0xFFFFFFFF) - ((d >> 32) & 0xFFFFFFFF)
        return result

    @staticmethod
    def long_arr_compare(arr1: List[int], arr2) -> int:
        """Returns negative / 0 / positive like Java compareTo."""
        if isinstance(arr2, int):
            arr2 = DTHelper.long_to_long_arr(arr2, len(arr1))
        if len(arr1) != len(arr2):
            return len(arr1) - len(arr2)
        for a, b in zip(arr1, arr2):
            if a < b:
                return -1
            if a > b:
                return 1
        return 0

    @staticmethod
    def get_child_by_label(base: DTNode, label: str) -> Optional[DTNode]:
        if base.label and base.label.lower() == label.lower():
            return base
        for child in base.children:
            found = DTHelper.get_child_by_label(child, label)
            if found:
                return found
        return None

    @staticmethod
    def parse_address_for_interface(s: str, intf) -> List[int]:
        return DTHelper.parse_long_string(s, intf.get_primary_width())

    @staticmethod
    def parse_size_for_interface(s: str, intf) -> List[int]:
        return DTHelper.parse_long_string(s, intf.get_secondary_width())
