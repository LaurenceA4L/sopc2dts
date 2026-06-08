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
from ..log import logger

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

    def remove_component(self, comp: BasicComponent) -> bool:
        try:
            self._components.remove(comp)
            return True
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Post-parse validation (port of AvalonSystem.recheckComponents)
    # ------------------------------------------------------------------

    def recheck_components(self) -> None:
        """
        Post-parse component cleanup and validation.
        Port of AvalonSystem.recheckComponents.

        Hierarchy / QSys subsystem detection is handled by qsys.py, not here.
        SICBridge.removeFromSystemIfPossible is deferred to the Component
        handlers phase.
        """
        # Late import to avoid circular dependency at module level.
        from .component_lib import SopcComponentLib

        # --- Transparent interface bridges ---
        # STREAMING-type bridges are fully handled in Java by reconnecting the
        # connections; other types log a warning. We only log for now — full
        # implementation needs SICBridge (Component handlers phase).
        for comp in list(self._components):
            if comp.scd:
                for bridge in comp.scd.get_transparent_bridges():
                    master_intf = comp.get_interface_by_name(bridge.master_intf_name or "")
                    slave_intf = comp.get_interface_by_name(bridge.slave_intf_name or "")
                    if master_intf is None or slave_intf is None:
                        logger.warning(
                            "Failed to find interfaces for transparent bridge in "
                            "%s (%s)", comp.instance_name, comp.class_name,
                        )
                        continue
                    if master_intf.type != slave_intf.type:
                        logger.warning(
                            "Transparent bridge in %s (%s): master/slave type mismatch",
                            comp.instance_name, comp.class_name,
                        )
                        continue
                    if master_intf.type.name == "STREAMING":
                        # Rewire: create a direct connection from the external master
                        # to the external slave, bypassing this transparent component.
                        from .connection import Connection
                        conn_to_master = slave_intf.connections[0] if slave_intf.connections else None
                        conn_to_slave = master_intf.connections[0] if master_intf.connections else None
                        if conn_to_master and conn_to_slave:
                            new_conn = Connection(
                                conn_to_master.master_interface,
                                conn_to_slave.slave_interface,
                                master_intf.type,
                                connect=True,
                            )
                            _ = new_conn  # registered on the interfaces via connect=True
                            try:
                                conn_to_master.master_interface.connections.remove(conn_to_master)
                            except ValueError:
                                pass
                            try:
                                conn_to_slave.slave_interface.connections.remove(conn_to_slave)
                            except ValueError:
                                pass
                    else:
                        logger.warning(
                            "Transparent bridge in %s (%s) of type %s not yet supported",
                            comp.instance_name, comp.class_name, master_intf.type.name,
                        )

        # --- Remove components whose SCD group is "remove" ---
        i = 0
        while i < len(self._components):
            comp = self._components[i]
            if comp.scd and comp.scd.group.lower() == "remove":
                for intf in list(comp.interfaces):
                    for conn in list(intf.connections):
                        other = (
                            conn.slave_interface if intf.is_master
                            else conn.master_interface
                        )
                        if other is not None:
                            try:
                                other.connections.remove(conn)
                            except ValueError:
                                pass
                    intf.connections.clear()
                self._components.pop(i)
                # do not advance — re-check same index
            else:
                i += 1

        # --- final_check_on_component + optional bridge flattening ---
        lib = SopcComponentLib.get_instance()
        restart = True
        while restart:
            restart = False
            for i, comp in enumerate(list(self._components)):
                checked = lib.final_check_on_component(comp)
                if checked is not comp:
                    self._components.remove(comp)
                    self._components.append(checked)
                    restart = True
                    break
                if comp.remove_from_system_if_possible(self):
                    restart = True
                    break

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"AvalonSystem({self.name!r}, {len(self._components)} components)"
