# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Port of sopc2dts.lib.Bin2IHex — Intel HEX encoder.

Supports I8Hex (standard), I16Hex, I32Hex, and I64Hex formats with
configurable byte ordering and addressing modes.
"""

from __future__ import annotations

import struct
from enum import Enum, auto
from typing import Optional

from ..log import logger


class HexType(Enum):
    I8Hex  = auto()
    I16Hex = auto()
    I32Hex = auto()
    I64Hex = auto()


class ByteOrder(Enum):
    LE   = auto()
    BE16 = auto()
    BE32 = auto()
    BE64 = auto()


class AddressingMode(Enum):
    AddrMode8  = auto()
    AddrMode16 = auto()
    AddrMode32 = auto()
    AddrMode64 = auto()


def to_hex(
    data: bytes,
    hex_type: HexType = HexType.I8Hex,
    byte_order: ByteOrder = ByteOrder.LE,
    address: int = 0,
    addr_mode: AddressingMode = AddressingMode.AddrMode8,
) -> str:
    """Encode *data* as an Intel HEX string. Port of Bin2IHex.toHex."""
    # Pad to alignment boundary if required
    alignment = {
        HexType.I8Hex:  1,
        HexType.I16Hex: 2,
        HexType.I32Hex: 4,
        HexType.I64Hex: 8,
    }[hex_type]
    if len(data) % alignment != 0:
        logger.warning(
            "Bin2IHex: data length %d is not %d-byte aligned; padding with zeros",
            len(data), alignment,
        )
        data = data + bytes(alignment - (len(data) % alignment))

    result = ""
    pos = 0
    while pos < len(data):
        line_address = address
        line_size = min(0x10, len(data) - pos)
        # Shift address based on addressing mode
        shift = {
            AddressingMode.AddrMode8:  0,
            AddressingMode.AddrMode16: 1,
            AddressingMode.AddrMode32: 2,
            AddressingMode.AddrMode64: 3,
        }[addr_mode]
        line_address += (pos >> shift)
        result += _hex_line(data, pos, line_size, line_address, byte_order)
        pos += line_size

    result += ":00000001FF\n"
    return result


def _hex_line(
    data: bytes,
    pos: int,
    size: int,
    address: int,
    byte_order: ByteOrder,
) -> str:
    cksum = (size + ((address >> 8) & 0xFF) + (address & 0xFF)) & 0xFF
    result = f":{size:02X}{address & 0xFFFF:04X}00"
    remaining = size
    while remaining > 0:
        if byte_order == ByteOrder.LE:
            b = data[pos]
            cksum = (cksum + b) & 0xFF
            result += f"{b:02X}"
            pos += 1
            remaining -= 1
        elif byte_order == ByteOrder.BE16:
            b0, b1 = data[pos], data[pos + 1]
            cksum = (cksum + b0 + b1) & 0xFF
            result += f"{b1:02X}{b0:02X}"
            pos += 2
            remaining -= 2
        elif byte_order == ByteOrder.BE32:
            b = data[pos:pos + 4]
            for byte in b:
                cksum = (cksum + byte) & 0xFF
            result += f"{b[3]:02X}{b[2]:02X}{b[1]:02X}{b[0]:02X}"
            pos += 4
            remaining -= 4
        elif byte_order == ByteOrder.BE64:
            b = data[pos:pos + 8]
            for byte in b:
                cksum = (cksum + byte) & 0xFF
            result += (
                f"{b[7]:02X}{b[6]:02X}{b[5]:02X}{b[4]:02X}"
                f"{b[3]:02X}{b[2]:02X}{b[1]:02X}{b[0]:02X}"
            )
            pos += 8
            remaining -= 8

    result += f"{(-cksum) & 0xFF:02X}\n"
    return result
