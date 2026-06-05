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
Port of sopc2dts.lib.AvalonSystem — the top-level container for all
components and connections parsed from a .sopcinfo / .qsys file.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from .component import BasicComponent
from .enums import SystemDataType

if TYPE_CHECKING:
    pass


class AvalonSystem:
    """
    The parsed representation of a Platform Designer system.
    Port of sopc2dts.lib.AvalonSystem.
    """

    _sopc2dts_version: str = "unknown"

    def __init__(self, name: str, version: str, source_file: Path) -> None:
        self.name = name
        self.version = version
        self.source_file = source_file
        self._components: List[BasicComponent] = []

    # ------------------------------------------------------------------
    # Class-level version string (shared across all instances, like Java)
    # ------------------------------------------------------------------

    @classmethod
    def set_sopc2dts_version(cls, ver: str) -> None:
        cls._sopc2dts_version = ver

    @classmethod
    def get_sopc2dts_version(cls) -> str:
        return cls._sopc2dts_version

    # ------------------------------------------------------------------
    # Component registry
    # ------------------------------------------------------------------

    def add_component(self, comp: BasicComponent) -> None:
        self._components.append(comp)

    @property
    def components(self) -> List[BasicComponent]:
        return self._components

    def get_component_by_name(self, name: str) -> Optional[BasicComponent]:
        nl = name.lower()
        for c in self._components:
            if c.instance_name.lower() == nl:
                return c
        return None

    def get_components_by_class(self, class_name: str) -> List[BasicComponent]:
        cn = class_name.lower()
        return [c for c in self._components if c.class_name.lower() == cn]

    def get_master_components(self) -> List[BasicComponent]:
        """Components that have at least one memory-mapped master interface."""
        return [c for c in self._components if c.has_memory_master()]

    # ------------------------------------------------------------------
    # Version helpers (mirrors AvalonSystem.setVersion / getVersion)
    # ------------------------------------------------------------------

    def set_version(self, version_str: str) -> None:
        self.version = version_str
        parts = version_str.split(".")
        try:
            self._version_major = int(parts[0]) if parts else 0
            self._version_minor = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            self._version_major = 0
            self._version_minor = 0

    @property
    def version_major(self) -> int:
        return getattr(self, "_version_major", 0)

    @property
    def version_minor(self) -> int:
        return getattr(self, "_version_minor", 0)

    def __repr__(self) -> str:
        return f"AvalonSystem({self.name!r}, {len(self._components)} components)"
