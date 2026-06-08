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
Port of sopc2dts.lib.components.base.SICBridge.

Handles bridge flattening / removal from an AvalonSystem and (Phase 2)
the DT ranges property generation.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from ...log import logger
from ...model.component import BasicComponent, Interface, MemoryBlock
from ...model.connection import Connection
from ...model.enums import SystemDataType

if TYPE_CHECKING:
    from ...model.system import AvalonSystem


class BridgeRemovalStrategy(Enum):
    ALL = "ALL"
    BALANCED = "BALANCED"
    NONE = "NONE"


class SICBridge(BasicComponent):
    """
    A bridge/passthrough component that can optionally be removed from the
    system graph to simplify the device tree.
    Port of sopc2dts.lib.components.base.SICBridge.
    """

    # Class-level removal strategy (mirrors Java static field)
    _removal_strategy: BridgeRemovalStrategy = BridgeRemovalStrategy.BALANCED

    # Loop-detection sentinel (mirrors Java static field)
    _loop_check: Optional["SICBridge"] = None

    def __init__(self, comp: BasicComponent) -> None:
        # Copy-constructor path: take over the existing component's data.
        super().__init__(
            comp.class_name,
            comp.instance_name,
            comp.version,
            comp.scd,
        )
        # Share the same parameter and interface lists (mirrors Java super(comp))
        self._parameters = comp._parameters
        self._interfaces = comp._interfaces
        for intf in self._interfaces:
            intf.owner = self

    # ------------------------------------------------------------------
    # Class-level strategy setter
    # ------------------------------------------------------------------

    @classmethod
    def set_removal_strategy(cls, strategy: "str | BridgeRemovalStrategy") -> None:
        if isinstance(strategy, str):
            cls._removal_strategy = BridgeRemovalStrategy[strategy.upper()]
        else:
            cls._removal_strategy = strategy

    # ------------------------------------------------------------------
    # Address translation helpers (mirrors Java translateAddress)
    # ------------------------------------------------------------------

    @staticmethod
    def _add_arrays(a: List[int], b: List[int]) -> List[int]:
        """Element-wise addition of two int arrays of equal length."""
        return [x + y for x, y in zip(a, b)]

    def translate_address(
        self,
        master_val: Optional[List[int]],
        slave_val: Optional[List[int]],
    ) -> Optional[List[int]]:
        if master_val is None or slave_val is None:
            return None
        m, s = list(master_val), list(slave_val)
        if len(m) == len(s):
            return self._add_arrays(m, s)
        elif len(m) > len(s):
            pad = len(m) - len(s)
            ns = [0] * pad + s
            return self._add_arrays(m, ns)
        else:
            logger.error(
                "Cannot translate address — master width %d > slave width %d on %s",
                len(m), len(s), self.instance_name,
            )
            return None

    def translate_address_from_conns(
        self, master_conn: Connection, slave_conn: Connection
    ) -> Optional[List[int]]:
        return self.translate_address(master_conn.conn_value, slave_conn.conn_value)

    # ------------------------------------------------------------------
    # Cell-count helpers
    # ------------------------------------------------------------------

    def _get_address_cell_count(self, master_side: bool) -> int:
        for intf in self._interfaces:
            if intf.is_memory() and intf.is_master == master_side:
                return intf.get_primary_width()
        return 1

    def _get_size_cell_count(self, master_side: bool) -> int:
        for intf in self._interfaces:
            if intf.is_memory() and intf.is_master == master_side:
                return intf.get_secondary_width()
        return 1

    def get_bridged_interface(self, intf: Interface) -> Optional[Interface]:
        """Return the opposite-side interface for a given interface."""
        results = self.get_interfaces(intf.type, not intf.is_master)
        if not results:
            return None
        if len(results) > 1:
            logger.warning(
                "%s: getBridgedInterface found %d %s ports; using first",
                self.instance_name, len(results),
                "slave" if intf.is_master else "master",
            )
        return results[0]

    # ------------------------------------------------------------------
    # Predicates
    # ------------------------------------------------------------------

    def is_streaming_bridge(self) -> bool:
        """True if this bridge is a 1:1 streaming passthrough (no MM slave)."""
        num_stream_masters = 0
        num_stream_slaves = 0
        for intf in self._interfaces:
            if intf.is_memory_slave():
                return False
            if intf.type == SystemDataType.STREAMING:
                if intf.is_master:
                    num_stream_masters += 1
                else:
                    num_stream_slaves += 1
        return num_stream_masters == 1 and num_stream_slaves == 1

    def is_translating_bridge(self) -> bool:
        """True if any slave connection has a non-zero base address."""
        for intf in self._interfaces:
            if intf.is_memory_slave():
                for conn in intf.connections:
                    cv = conn.conn_value
                    if cv and any(v != 0 for v in cv):
                        return True
        return False

    # ------------------------------------------------------------------
    # System removal — MM case
    # ------------------------------------------------------------------

    def _remove_from_system_mm(self, sys: "AvalonSystem") -> bool:
        logger.info("Trying to eliminate bridge: %s (%s)", self.instance_name, self.class_name)
        master_intf: Optional[Interface] = None
        slave_intf: Optional[Interface] = None

        for intf in self._interfaces:
            if intf.is_clock_slave():
                # Disconnect clock connections to this bridge
                for conn in list(intf.connections):
                    try:
                        conn.master_interface.connections.remove(conn)
                    except (AttributeError, ValueError):
                        pass
            elif intf.is_memory_master():
                master_intf = intf
            elif intf.is_memory_slave():
                slave_intf = intf

        if master_intf is None or slave_intf is None:
            logger.warning(
                "Bridge %s: missing master_intf=%s slave_intf=%s",
                self.instance_name, master_intf, slave_intf,
            )
            return False

        is_addr_span_extender = (
            self.class_name.lower() == "altera_address_span_extender"
        )

        # For each upstream master connection (something that drives slave_intf)
        while slave_intf.connections:
            master_conn = slave_intf.connections[0]
            logger.debug(
                "Master of bridge: %s.%s",
                master_conn.master_module.instance_name,
                master_conn.master_interface.name,
            )
            logger.debug(
                "Slave of bridge: %s  num_downstream=%d",
                master_intf.name, len(master_intf.connections),
            )

            # For each downstream slave connection, create a bypass connection
            for slave_conn in list(master_intf.connections):
                new_conn = Connection(
                    master_conn.master_interface,
                    slave_conn.slave_interface,
                    slave_conn.type,
                    connect=True,
                )
                if is_addr_span_extender:
                    slave_conn.slave_interface.interface_value = (
                        list(slave_intf.interface_value)
                        if slave_intf.interface_value else None
                    )
                new_conn.conn_value = self.translate_address(
                    master_conn.conn_value, slave_conn.conn_value
                )

            # Remove the upstream connection
            try:
                slave_intf.connections.remove(master_conn)
            except ValueError:
                pass
            try:
                master_conn.master_interface.connections.remove(master_conn)
            except ValueError:
                pass

        # Remove all downstream slave connections
        while master_intf.connections:
            slave_conn = master_intf.connections[0]
            try:
                master_intf.connections.remove(slave_conn)
            except ValueError:
                break
            try:
                slave_conn.slave_interface.connections.remove(slave_conn)
            except (AttributeError, ValueError):
                pass

        sys.remove_component(self)
        return True

    # ------------------------------------------------------------------
    # System removal — streaming case
    # ------------------------------------------------------------------

    def _remove_from_system_streaming(self, sys: "AvalonSystem") -> bool:
        stream_masters = self.get_interfaces(SystemDataType.STREAMING, True)
        stream_slaves = self.get_interfaces(SystemDataType.STREAMING, False)
        if not stream_masters or not stream_slaves:
            return False
        master_intf = stream_masters[0]
        slave_intf = stream_slaves[0]

        if not slave_intf.connections or not master_intf.connections:
            return False

        conn = slave_intf.connections[0]   # external → this bridge
        old_conn = master_intf.connections[0]  # this bridge → external slave

        # Remove clock connections
        for clk_intf in self.get_interfaces(SystemDataType.CLOCK, False):
            for clk_conn in list(clk_intf.connections):
                try:
                    clk_conn.master_interface.connections.remove(clk_conn)
                except (AttributeError, ValueError):
                    pass

        # Rewire: conn now goes directly to old_conn's slave
        new_slave_intf = old_conn.slave_interface
        try:
            new_slave_intf.connections.remove(old_conn)
        except (AttributeError, ValueError):
            pass
        conn.slave_interface = new_slave_intf
        if new_slave_intf is not None:
            new_slave_intf.connections.append(conn)

        sys.remove_component(self)
        return True

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if self.is_streaming_bridge():
            return self._remove_from_system_streaming(sys)

        remove = False
        scd = self.scd

        # Tristate bridges are always removed
        if scd and scd.is_supporting_class_name("altera_avalon_tri_state_bridge"):
            remove = True
        else:
            strategy = SICBridge._removal_strategy
            if strategy == BridgeRemovalStrategy.ALL:
                remove = True
            elif strategy == BridgeRemovalStrategy.NONE:
                remove = False
            elif strategy == BridgeRemovalStrategy.BALANCED:
                if scd and (
                    scd.is_supporting_class_name("altera_avalon_pipeline_bridge")
                    or scd.is_supporting_class_name("altera_avalon_clock_crossing")
                    or scd.is_supporting_class_name("altera_avalon_half_rate_bridge")
                ) and not self.is_translating_bridge():
                    remove = True

        if remove:
            return self._remove_from_system_mm(sys)
        return False

    # ------------------------------------------------------------------
    # Memory map (Phase 2 helper, used by Interface.get_memory_map)
    # ------------------------------------------------------------------

    def get_memory_map(self, conn: Connection) -> List[MemoryBlock]:
        """Walk downstream connections, translating addresses through this bridge."""
        result: List[MemoryBlock] = []

        # Loop detection
        if SICBridge._loop_check is None:
            SICBridge._loop_check = self
        elif SICBridge._loop_check is self:
            logger.warning("Bridge loop detected on %s — skipping", self.instance_name)
            return result

        for bridge_master in self.get_interfaces(SystemDataType.MEMORY_MAPPED, True):
            result.extend(bridge_master.get_memory_map())

        for mb in result:
            mb.base = self.translate_address(
                conn.conn_value if conn.conn_value else [],
                mb.base,
            )

        if SICBridge._loop_check is self:
            SICBridge._loop_check = None

        return result

    # ------------------------------------------------------------------
    # DT node (Phase 2 — calls super once BasicComponent.to_dt_node exists)
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: Optional[Connection]) -> object:
        # Phase 2: uncomment once BasicComponent.to_dt_node is implemented
        # from ...model.devicetree import DTProperty
        # dtn = super().to_dt_node(board_info, conn)
        # ranges = self._get_dt_ranges(conn, board_info.ranges_style)
        # dtn.add_property(DTProperty("#address-cells", self._get_address_cell_count(True)))
        # dtn.add_property(DTProperty("#size-cells", self._get_size_cell_count(True)))
        # if not ranges:
        #     dtn.add_property(DTProperty("ranges"))
        # else:
        #     p = DTProperty("ranges")
        #     p.add_hex_values(ranges)
        #     p.set_num_values_per_row(
        #         self._get_address_cell_count(True)
        #         + self._get_address_cell_count(False)
        #         + self._get_size_cell_count(True)
        #     )
        #     dtn.add_property(p)
        # return dtn
        raise NotImplementedError("SICBridge.to_dt_node — Phase 2")
