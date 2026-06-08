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
Port of sopc2dts.generators.DTGenerator — the core DTS tree builder.
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from .AbstractSopcGenerator import AbstractSopcGenerator
from ..log import logger
from ..model.enums import SystemDataType

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo, BICDTAppend, SortType
    from ..model.component import BasicComponent
    from ..model.connection import Connection
    from ..model.devicetree import DTNode


_BOARD_INFO_COMMENT = "appended from boardinfo"


class DTGenerator(AbstractSopcGenerator):
    """
    Abstract DT generator — builds the in-memory DTNode tree.
    Subclasses implement get_text_output / get_binary_output.
    Port of sopc2dts.generators.DTGenerator.
    """

    def __init__(self, sys, is_text: bool) -> None:
        super().__init__(sys, is_text)
        self._v_handled: List["BasicComponent"] = []

    # ------------------------------------------------------------------
    # Core tree builder
    # ------------------------------------------------------------------

    def get_dt_output(self, bi: "BoardInfo") -> "DTNode":
        """Port of DTGenerator.getDTOutput."""
        from ..model.boardinfo import PovType, AltrStyle
        from ..model.devicetree import (
            DTNode, DTProperty, DTPropStringVal,
        )

        self._v_handled = []
        root_node = DTNode("/")
        pov_component = self.get_pov_component(bi)
        clocks_node: Optional[DTNode] = None

        if pov_component is None:
            self._do_dt_append(root_node, bi)
            return root_node

        mm_masters = pov_component.get_interfaces(SystemDataType.MEMORY_MAPPED, True)
        if not mm_masters:
            logger.error(
                "POV component %s has no memory-mapped master interfaces.",
                pov_component.instance_name,
            )
            self._do_dt_append(root_node, bi)
            return root_node

        addr_cells = mm_masters[0].get_primary_width()
        size_cells = mm_masters[0].get_secondary_width()

        if bi.get_pov_type() == PovType.CPU:
            cpu_node = self._get_cpu_nodes(bi, pov_component)
            mem_node = self._get_memory_node(bi, pov_component, addr_cells, size_cells)
            alias_node: Optional[DTNode] = None
            sopc_node = DTNode("sopc@0", label="sopc0")
            chosen_node: Optional[DTNode] = self._get_chosen_node(bi)
            clocks_node = self._get_clocks_node(bi)

            root_node.add_property(
                DTProperty.from_string("model", "ALTR," + self.sys.name)
            )
            root_node.add_property(
                DTProperty.from_string("compatible", "ALTR," + self.sys.name)
            )
            root_node.add_property(DTProperty.from_long("#address-cells", addr_cells))
            root_node.add_property(DTProperty.from_long("#size-cells", size_cells))

            # aliases from boardinfo (plain string refs)
            v_aliases = bi.get_aliases()
            if v_aliases:
                alias_node = DTNode("aliases")
                for p in v_aliases:
                    alias_node.add_property(DTProperty.from_string(p.name, p.value))

            # alias-refs (component path lookups)
            v_alias_refs = bi.get_alias_refs()
            if v_alias_refs:
                if alias_node is None:
                    alias_node = DTNode("aliases")
                from ..model.devicetree import DTHelper
                for p in v_alias_refs:
                    slave = self.sys.get_component_by_name(p.value)
                    if slave is not None:
                        v_conn = self.sys.get_connection_path(
                            pov_component, slave, SystemDataType.MEMORY_MAPPED
                        )
                        path = "/" + sopc_node.name
                        for c in v_conn:
                            sm = c.slave_module
                            if sm is not None:
                                path += (
                                    "/" + sm.scd.group
                                    + "@" + DTHelper.long_arr_to_hex_string(
                                        c.conn_value or [0]
                                    )
                                )
                        if path:
                            alias_node.add_property(DTProperty.from_string(p.name, path))
                        else:
                            logger.warning(
                                "Failed to find path for alias '%s' -> '%s'",
                                p.name, p.value,
                            )
                    else:
                        logger.warning(
                            "Failed to find component '%s' for alias '%s'",
                            p.value, p.name,
                        )

            if alias_node is not None:
                root_node.add_child(alias_node)
            if cpu_node is not None:
                root_node.add_child(cpu_node)
            if mem_node is not None:
                root_node.add_child(mem_node)
            sopc_node.add_property(DTProperty.from_string("device_type", "soc"))
        else:
            # PCI POV — sopc_node IS root_node
            sopc_node = root_node
            chosen_node = None

        sopc_node = self._get_slaves_for(bi, pov_component, sopc_node)
        sopc_node.add_property(DTProperty("ranges"))
        sopc_node.add_property(DTProperty.from_long("#address-cells", addr_cells))
        sopc_node.add_property(DTProperty.from_long("#size-cells", size_cells))
        sopc_node.add_property(
            DTProperty.from_strings("compatible", ["ALTR,avalon", "simple-bus"])
        )
        sopc_node.add_property(DTProperty.from_long("bus-frequency", pov_component.get_clock_rate()))

        if bi.get_pov_type() == PovType.CPU:
            if clocks_node is not None:
                root_node.add_child(clocks_node)
            root_node.add_child(sopc_node)
            if chosen_node is not None:
                root_node.add_child(chosen_node)

        self._do_dt_append(root_node, bi)

        if bi.get_altr_style() != AltrStyle.AUTO:
            a_lt_r = "altr" if bi.get_altr_style() == AltrStyle.FORCE_LOWER else "ALTR"
            self._fix_altr_compatible_mess(root_node, a_lt_r)

        return root_node

    # ------------------------------------------------------------------
    # Sub-tree builders
    # ------------------------------------------------------------------

    def _get_chosen_node(self, bi: "BoardInfo") -> "DTNode":
        """Port of DTGenerator.getChosenNode."""
        from ..model.devicetree import DTNode, DTProperty
        chosen = DTNode("chosen")
        boot_args = bi.get_boot_args()
        if not boot_args:
            bi.set_boot_args("debug console=ttyAL0,115200")
        else:
            bi.set_boot_args(boot_args.replace('"', ''))
        chosen.add_property(DTProperty.from_string("bootargs", bi.get_boot_args()))
        return chosen

    def _get_clocks_node(self, bi: "BoardInfo") -> Optional["DTNode"]:
        """Port of DTGenerator.getClocksNode."""
        from ..model.devicetree import DTNode, DTProperty
        if not bi.is_show_clock_tree():
            return None
        from ..components.base.SICClockSource import SICClockSource
        cn = DTNode("clocks")
        for comp in self.sys.components:
            if isinstance(comp, SICClockSource):
                if not cn.properties:
                    cn.add_property(DTProperty.from_long("#address-cells", 1))
                    cn.add_property(DTProperty.from_long("#size-cells", 1))
                cn.add_child(comp.to_dt_node(bi, None))
                self._v_handled.append(comp)
        return cn

    def _get_cpu_nodes(
        self,
        bi: "BoardInfo",
        pov_comp: "BasicComponent",
    ) -> Optional["DTNode"]:
        """Port of DTGenerator.getCpuNodes."""
        from ..model.boardinfo import PovType
        from ..model.devicetree import DTNode, DTProperty
        from ..components.base.SICCpuComponent import SICCpuComponent

        if bi.get_pov_type() != PovType.CPU:
            return None

        cpu_node = DTNode("cpus")
        num_cpus = 0
        first_cpu: Optional[SICCpuComponent] = None

        if isinstance(pov_comp, SICCpuComponent):
            first_cpu = pov_comp

        cpu_node.add_property(DTProperty.from_long("#address-cells", 1))
        cpu_node.add_property(DTProperty.from_long("#size-cells", 0))

        for comp in self.sys.components:
            if isinstance(comp, SICCpuComponent):
                cpu = comp
                if (first_cpu is None
                        or first_cpu is cpu
                        or first_cpu.is_smp_capable_with(cpu)):
                    if bi.get_pov() is None:
                        bi.set_pov(comp.instance_name)
                    if first_cpu is None:
                        first_cpu = cpu
                    cpu.cpu_index = num_cpus
                    cpu_node.add_child(comp.to_dt_node(bi, None))
                    num_cpus += 1
                self._v_handled.append(comp)

        if not cpu_node.children:
            return None
        return cpu_node

    def _get_memory_node(
        self,
        bi: "BoardInfo",
        master: Optional["BasicComponent"],
        addr_cells: int,
        size_cells: int,
    ) -> Optional["DTNode"]:
        """Port of DTGenerator.getMemoryNode."""
        from ..model.devicetree import DTNode, DTProperty

        mem_node = DTNode("memory")
        dtp_reg = DTProperty("reg")
        dtp_reg.set_num_values_per_row(addr_cells + size_cells)
        mem_node.add_property(DTProperty.from_string("device_type", "memory"))
        mem_node.add_property(dtp_reg)

        if master is not None:
            v_memory_mapped = bi.get_memory_nodes()
            if v_memory_mapped:
                for intf in master.interfaces:
                    if not intf.is_memory_master():
                        continue
                    for mem in intf.get_memory_map():
                        if mem.owner.instance_name in v_memory_mapped:
                            comp = mem.owner
                            if comp is not None and comp not in self._v_handled:
                                dtp_reg.add_hex_values(mem.base)
                                dtp_reg.add_hex_values(mem.size)
                                self._v_handled.append(comp)

            if not dtp_reg.values:
                logger.info(
                    "dts memory section: No memory nodes specified. Blindly adding them all."
                )
                seen: List[str] = []
                for intf in master.interfaces:
                    if not intf.is_memory_master():
                        continue
                    for mem in intf.get_memory_map():
                        if mem.owner.instance_name not in seen:
                            comp = mem.owner
                            if comp is not None and comp.scd.group.lower() == "memory":
                                dtp_reg.add_hex_values(mem.base)
                                dtp_reg.add_hex_values(mem.size)
                                seen.append(mem.owner.instance_name)
                                self._v_handled.append(comp)

        if not dtp_reg.values:
            return None
        return mem_node

    def _get_slaves_for(
        self,
        bi: "BoardInfo",
        master_comp: Optional["BasicComponent"],
        master_node: "DTNode",
    ) -> "DTNode":
        """Port of DTGenerator.getSlavesFor — recursive slave walker."""
        if master_comp is None:
            return master_node

        slave_conns = master_comp.get_connections(SystemDataType.MEMORY_MAPPED, True)
        self._sort_slaves(slave_conns, bi.get_sort_type())

        for conn in slave_conns:
            slave = conn.slave_module
            if slave is None or slave in self._v_handled:
                continue
            self._v_handled.append(slave)
            if slave.scd.group == "bridge":
                bridge_node = self._get_slaves_for(bi, slave, slave.to_dt_node(bi, conn))
                if bridge_node.children:
                    master_node.add_child(bridge_node)
            else:
                master_node.add_child(slave.to_dt_node(bi, conn))

        return master_node

    # ------------------------------------------------------------------
    # Board-info DT appends
    # ------------------------------------------------------------------

    def _do_dt_append(self, root_node: "DTNode", bi: "BoardInfo") -> None:
        """Port of DTGenerator.doDTAppend."""
        from ..model.boardinfo import DTAppendType, DTAppendAction
        from ..model.devicetree import (
            DTNode, DTProperty, DTHelper,
            DTPropNumVal, DTPropHexNumVal, DTPropByteVal,
            DTPropStringVal, DTPropPHandleVal,
        )

        for dta in bi.get_dt_appends():
            parent: Optional[DTNode] = None

            # Locate parent by label
            if dta.parent_label is not None:
                if dta.parent_label == "":
                    parent = root_node
                else:
                    parent = DTHelper.get_child_by_label(root_node, dta.parent_label)

            # Locate parent by path
            if parent is None and dta.parent_path is not None:
                parent = root_node
                for node_str in dta.parent_path:
                    next_parent: Optional[DTNode] = None
                    for child in parent.children:
                        if child.name.lower() == node_str.lower():
                            next_parent = child
                            break
                    parent = next_parent
                    if parent is None:
                        break

            if parent is None:
                label_desc = dta.parent_label if dta.parent_label is not None else "null"
                logger.warning(
                    "DTAppend: Unable to find parent '%s' for '%s'. Adding to root.",
                    label_desc, dta.instance_name,
                )
                parent = root_node

            v_types = dta.types
            if v_types and v_types[0] == DTAppendType.NODE:
                parent.add_child(DTNode(dta.instance_name, label=dta.label))
            else:
                v_values = dta.values
                if len(v_values) != len(v_types):
                    logger.error(
                        "doDTAppend size mismatch: values=%d types=%d for '%s'",
                        len(v_values), len(v_types), dta.instance_name,
                    )
                    continue

                prop = parent.get_property_by_name(dta.instance_name)
                if dta.action == DTAppendAction.REMOVE:
                    if prop is not None:
                        parent.remove_property(prop)
                else:
                    if dta.action == DTAppendAction.REPLACE or prop is None:
                        prop = DTProperty(
                            dta.instance_name,
                            label=dta.label,
                            comment=_BOARD_INFO_COMMENT,
                        )
                    for i, t in enumerate(v_types):
                        val_str = v_values[i]
                        if t == DTAppendType.PROP_NUMBER:
                            prop.add_value(DTPropNumVal(int(val_str, 0)))
                        elif t == DTAppendType.PROP_HEX:
                            prop.add_value(DTPropHexNumVal(int(val_str, 0)))
                        elif t == DTAppendType.PROP_BYTE:
                            prop.add_value(DTPropByteVal(int(val_str, 0)))
                        elif t == DTAppendType.PROP_STRING:
                            prop.add_value(DTPropStringVal(val_str))
                        elif t == DTAppendType.PROP_PHANDLE:
                            prop.add_value(DTPropPHandleVal(val_str, 0))
                        # PROP_BOOL has no value
                    parent.add_property(prop, replace_existing=True)

    # ------------------------------------------------------------------
    # ALTR/altr compatible normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _fix_altr_compatible_mess(node: "DTNode", a_lt_r: str) -> None:
        """Port of DTGenerator.fixALTRaltrCompatibleMess."""
        from ..model.devicetree import DTPropStringVal
        for prop in node.properties:
            if len(prop.name) > 5 and prop.name[:5].lower() == "altr,":
                prop.name = a_lt_r + prop.name[4:]
            if prop.name == "compatible":
                for v in prop.values:
                    if isinstance(v, DTPropStringVal):
                        if len(v.value) > 5 and v.value[:5].lower() == "altr,":
                            v.value = a_lt_r + v.value[4:]
        for child in node.children:
            DTGenerator._fix_altr_compatible_mess(child, a_lt_r)

    # ------------------------------------------------------------------
    # Slave sort
    # ------------------------------------------------------------------

    @staticmethod
    def _sort_slaves(v_conn: List["Connection"], sort: "SortType") -> None:
        """Port of DTGenerator.sortSlaves."""
        from ..model.boardinfo import SortType
        from ..model.devicetree import DTHelper

        if sort == SortType.NONE:
            return

        def key_fn(conn: "Connection"):
            slave = conn.slave_module
            if sort == SortType.ADDRESS:
                return conn.conn_value or [0]
            elif sort == SortType.NAME:
                group = slave.scd.group.lower() if slave else ""
                label = slave.instance_name.lower() if slave else ""
                return (group, label)
            else:  # LABEL
                return slave.instance_name.lower() if slave else ""

        v_conn.sort(key=key_fn)
