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
Port of sopc2dts.lib.Parameter — a named, typed value attached to any
BasicElement (component, interface, connection).
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .devicetree import DTProperty


class DataType(Enum):
    NUMBER = "NUMBER"
    UNSIGNED = "UNSIGNED"
    BOOLEAN = "BOOLEAN"
    STRING = "STRING"
    BOOLEAN_TRUE_WHEN_PRESENT = "BOOLEAN_TRUE_WHEN_PRESENT"


class Parameter:
    """A named, typed parameter value. Port of sopc2dts.lib.Parameter."""

    def __init__(self, name: str, value: str, data_type: DataType) -> None:
        self.name = name
        self.data_type: DataType

        if data_type == DataType.BOOLEAN_TRUE_WHEN_PRESENT:
            self.data_type = DataType.BOOLEAN
            self.value = "true"
        elif data_type == DataType.UNSIGNED:
            self.data_type = DataType.UNSIGNED
            # Negative values stored as unsigned hex (matches Java behaviour)
            if value and value[0] == '-':
                self.value = f"0x{int(value, 0) & 0xFFFFFFFF:08x}"
            else:
                self.value = value
        else:
            self.data_type = data_type
            self.value = value

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def data_type_by_name(name: Optional[str]) -> Optional[DataType]:
        """Map a string type name to DataType, mirroring Parameter.getDataTypeByName."""
        if name is None:
            return None
        n = name.upper()
        if n == "BOOLEAN_TRUE_WHEN_PRESENT":
            return DataType.BOOLEAN_TRUE_WHEN_PRESENT
        if n in ("BOOLEAN", "BOOL"):
            return DataType.BOOLEAN
        if n == "NUMBER":
            return DataType.NUMBER
        if n == "UNSIGNED":
            return DataType.UNSIGNED
        if n == "STRING":
            return DataType.STRING
        return None

    # ------------------------------------------------------------------
    # Value accessors
    # ------------------------------------------------------------------

    def get_value_as_bool(self) -> bool:
        """Mirrors Parameter.getValueAsBoolean."""
        if not self.value:
            return False
        try:
            return int(self.value, 0) != 0
        except ValueError:
            return self.value.lower() != "false"

    # ------------------------------------------------------------------
    # DT serialisation (requires devicetree model — imported lazily)
    # ------------------------------------------------------------------

    def to_dt_property(
        self,
        dts_name: Optional[str] = None,
        force_type: Optional[DataType] = None,
    ) -> Optional["DTProperty"]:
        """
        Convert this parameter to a DTProperty.
        Mirrors Parameter.toDTProperty(String, DataType).
        Returns None if the parameter should not appear in the DTS
        (e.g. a BOOLEAN that is false).
        """
        from .devicetree import (
            DTProperty, DTPropHexNumVal, DTPropNumVal, DTPropStringVal,
        )

        name = dts_name or self.name
        dt = force_type or self.data_type

        prop = DTProperty(name, comment=f"{self.name} type {self.data_type.value}")

        if dt == DataType.UNSIGNED:
            prop.add_value(DTPropHexNumVal(int(self.value, 0)))
        elif dt == DataType.NUMBER:
            prop.add_value(DTPropNumVal(int(self.value, 0)))
        elif dt == DataType.BOOLEAN_TRUE_WHEN_PRESENT:
            pass  # property present with no value
        elif dt == DataType.BOOLEAN:
            if not self.get_value_as_bool():
                return None
        elif dt == DataType.STRING:
            tmp = self.value.strip().strip('"')
            prop.add_value(DTPropStringVal(tmp))
        else:
            return None

        return prop

    def __repr__(self) -> str:
        return f"Parameter({self.name!r}, {self.value!r}, {self.data_type})"
