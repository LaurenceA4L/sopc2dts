# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2013 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Port of sopc2dts.generators.UBootHeaderGenerator +
sopc2dts.lib.uboot.UBootComponentLib / UBootLibComponent.

Generates a CUSTOM_FPGA_H_ C header suitable for U-Boot board files.
Each component gets CONFIG_SYS_* defines for its base address, IRQ, etc.
The UBootComponentLib mapping is inlined here — it was only ever used
by this generator.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from .AbstractSopcGenerator import AbstractSopcGenerator
from ..model.enums import SystemDataType
from ..model.devicetree import DTHelper
from ..log import logger

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo
    from ..model.system import AvalonSystem
    from ..model.component import BasicComponent, Interface, Connection


# ---------------------------------------------------------------------------
# UBootLibComponent — port of sopc2dts.lib.uboot.UBootLibComponent
# ---------------------------------------------------------------------------

KERNEL_REGION_BASE_NOMMU = 0x00000000
IO_REGION_BASE_NOMMU     = 0x80000000
KERNEL_REGION_BASE_MMU   = 0xC0000000
IO_REGION_BASE_MMU       = 0xE0000000

EMBSW_CMACRO = "embeddedsw.CMacro"


def _is_mmu_enabled(comp: "BasicComponent") -> bool:
    return comp.get_param_by_name(EMBSW_CMACRO + ".MMU_PRESENT") is not None


def _kernel_base(master: "BasicComponent") -> int:
    return KERNEL_REGION_BASE_MMU if _is_mmu_enabled(master) else KERNEL_REGION_BASE_NOMMU


def _io_base(master: "BasicComponent") -> int:
    return IO_REGION_BASE_MMU if _is_mmu_enabled(master) else IO_REGION_BASE_NOMMU


class _UBootLibComponent:
    """Port of UBootLibComponent."""

    def __init__(
        self,
        compatible: Optional[List[str]],
        property_defines: Optional[Dict[str, str]],
        extra_data: Optional[str],
    ) -> None:
        self._compatible = compatible or []
        self._property_defines = property_defines  # None → generic address/IRQ
        self._extra_data = extra_data

    def is_compatible(self, class_name: str) -> bool:
        cn = class_name.lower()
        for pat in self._compatible:
            p = pat.lower()
            if p.startswith("*") and p.endswith("*"):
                if p[1:-1] in cn:
                    return True
            elif p.startswith("*"):
                if cn.endswith(p[1:]):
                    return True
            elif p.endswith("*"):
                if cn.startswith(p[:-1]):
                    return True
            elif p == cn:
                return True
        return False

    def get_headers_for(
        self,
        mem_master: "BasicComponent",
        irq_master: "BasicComponent",
        comp: "BasicComponent",
        if_num: int,
        addr_offset: int,
    ) -> str:
        if comp.scd.group.lower() == "bridge":
            return ""

        res = ""
        if self._property_defines is None:
            res += _memory_defines(mem_master, comp, None, addr_offset | _io_base(irq_master))
            res += _interrupt_defines(irq_master, comp, None)
        else:
            for define, val_spec in self._property_defines.items():
                parts = val_spec.split("|", 1)
                spec_type = parts[0].lower()
                spec_val = parts[1] if len(parts) > 1 else ""
                val: Optional[str] = None

                if spec_type == "prop":
                    val = comp.get_param_val_by_name(spec_val)
                    if val is None:
                        val = f"not found: {spec_val}"
                elif spec_type == "gen":
                    sv = spec_val.lower()
                    if sv == "clk":
                        val = str(comp.get_clock_rate())
                    elif sv.startswith("ioaddr"):
                        idx = int(sv[6]) if len(sv) == 7 else -1
                        res += _memory_defines(
                            mem_master, comp, define,
                            addr_offset | _io_base(irq_master), idx
                        )
                    elif sv == "kerneladdr":
                        res += _memory_defines(
                            mem_master, comp, define,
                            addr_offset | _kernel_base(irq_master)
                        )
                    elif sv == "irq":
                        res += _interrupt_defines(irq_master, comp, define)
                    elif sv.startswith("size"):
                        idx = int(sv[4]) if len(sv) == 5 else if_num
                        slave_ifs = comp.get_interfaces(SystemDataType.MEMORY_MAPPED, False)
                        if idx < len(slave_ifs):
                            val = DTHelper.long_arr_to_hex_string(
                                slave_ifs[idx].interface_value or []
                            )
                        else:
                            val = "0"
                    else:
                        val = f"Don't know how to generate {spec_val}"
                else:
                    val = f"Unsupported type: {spec_type}"

                if val is not None:
                    res += f"#define {define}\t{val}\n"

        if self._extra_data:
            res += self._extra_data
        return res


# ---------------------------------------------------------------------------
# Define helpers
# ---------------------------------------------------------------------------

def _get_conns_for(
    master: "BasicComponent",
    slave: "BasicComponent",
    dt: SystemDataType,
) -> List["Connection"]:
    """Return slave's connections of type dt that have the given master."""
    result = []
    for intf in slave.interfaces:
        if intf.type != dt or intf.is_master:
            continue
        for conn in intf.connections:
            if conn.master_module is master:
                result.append(conn)
    return result


def _memory_defines(
    master: "BasicComponent",
    slave: "BasicComponent",
    name: Optional[str],
    offset: int,
    index: int = -1,
) -> str:
    conns = _get_conns_for(master, slave, SystemDataType.MEMORY_MAPPED)
    # Remove instruction master connections
    conns = [
        c for c in conns
        if (c.master_interface is None
            or c.master_interface.name.lower() != "instruction_master")
    ]
    if index >= 0 and index < len(conns):
        conns = [conns[index]]

    res = ""
    base_name = name or (AbstractSopcGenerator.definenify(slave.instance_name) + "_BASE")
    for conn in conns:
        addr = DTHelper.long_arr_add(conn.conn_value or [0], offset)
        label = base_name
        if len(conns) > 1 and conn.slave_interface:
            label = (
                AbstractSopcGenerator.definenify(slave.instance_name)
                + "_"
                + AbstractSopcGenerator.definenify(conn.slave_interface.name)
            )
        res += f"#define {label}\t{DTHelper.long_arr_to_hex_string(addr)}\n"
    return res


def _interrupt_defines(
    master: "BasicComponent",
    slave: "BasicComponent",
    name: Optional[str],
) -> str:
    conns = _get_conns_for(master, slave, SystemDataType.INTERRUPT)
    res = ""
    base_name = name or (AbstractSopcGenerator.definenify(slave.instance_name) + "_IRQ")
    for conn in conns:
        irq = DTHelper.long_arr_to_long(conn.conn_value or [0])
        label = base_name
        if len(conns) > 1 and conn.slave_interface:
            label = (
                AbstractSopcGenerator.definenify(slave.instance_name)
                + "_"
                + AbstractSopcGenerator.definenify(conn.slave_interface.name)
            )
        res += f"#define {label}\t{irq}\n"
    return res


# ---------------------------------------------------------------------------
# UBootComponentLib — port of sopc2dts.lib.uboot.UBootComponentLib
# ---------------------------------------------------------------------------

def _build_lib() -> List[_UBootLibComponent]:
    E = EMBSW_CMACRO
    lib = []

    lib.append(_UBootLibComponent(
        ["altera_nios2", "altera_nios2_qsys"],
        {
            "CONFIG_SYS_CLK_FREQ":       f"gen|clk",
            "CONFIG_SYS_RESET_ADDR":     f"prop|{E}.RESET_ADDR",
            "CONFIG_SYS_EXCEPTION_ADDR": f"prop|{E}.EXCEPTION_ADDR",
            "CONFIG_SYS_ICACHE_SIZE":    f"prop|{E}.ICACHE_SIZE",
            "CONFIG_SYS_ICACHELINE_SIZE":f"prop|{E}.ICACHE_LINE_SIZE",
            "CONFIG_SYS_DCACHE_SIZE":    f"prop|{E}.DCACHE_SIZE",
            "CONFIG_SYS_DCACHELINE_SIZE":f"prop|{E}.DCACHE_LINE_SIZE",
        },
        f"#define IO_REGION_BASE\t0x{IO_REGION_BASE_MMU:08X}\n",
    ))
    lib.append(_UBootLibComponent(
        ["altera_avalon_sysid", "altera_avalon_sysid_qsys"],
        {"CONFIG_SYS_SYSID_BASE": "gen|ioaddr"},
        None,
    ))
    lib.append(_UBootLibComponent(
        ["gpio"],
        {"CONFIG_SYS_GPIO_BASE": "gen|ioaddr"},
        None,
    ))
    lib.append(_UBootLibComponent(
        ["altera_avalon_jtag_uart"],
        {"CONFIG_SYS_JTAG_UART_BASE": "gen|ioaddr"},
        None,
    ))
    lib.append(_UBootLibComponent(
        ["altera_avalon_uart", "fifoed_avalon_uart_classic"],
        {
            "CONFIG_SYS_UART_BASE": "gen|ioaddr",
            "CONFIG_SYS_UART_FREQ": "gen|clk",
            "CONFIG_SYS_UART_BAUD": f"prop|{E}.BAUD",
        },
        None,
    ))
    lib.append(_UBootLibComponent(
        ["altera_avalon_timer"],
        {
            "CONFIG_SYS_TIMER_BASE": "gen|ioaddr",
            "CONFIG_SYS_TIMER_IRQ":  "gen|irq",
            "CONFIG_SYS_TIMER_FREQ": "gen|clk",
        },
        None,
    ))
    lib.append(_UBootLibComponent(
        ["altera_avalon_cf"],
        {"CONFIG_SYS_ATA_BASE_ADDR": "gen|ioaddr"},
        (
            "#define CONFIG_CMD_IDE\n"
            "#define CONFIG_IDE_RESET\n"
            "#define CONFIG_CMD_FAT\n"
            "#define CONFIG_DOS_PARTITION\n"
            "#define CONFIG_SYS_PIO_MODE 1\n"
            "#define CONFIG_SYS_IDE_MAXBUS 1\n"
            "#define CONFIG_SYS_IDE_MAXDEVICE 1\n"
            "#define CONFIG_SYS_ATA_STRIDE 4\n"
            "#define CONFIG_SYS_ATA_DATA_OFFSET 0x0\n"
            "#define CONFIG_SYS_ATA_REG_OFFSET 0x0\n"
            "#define CONFIG_SYS_ATA_ALT_OFFSET 0x20\n"
        ),
    ))
    lib.append(_UBootLibComponent(
        ["eth_ocm"],
        {"CONFIG_SYS_ETHOC_BASE": "gen|ioaddr"},
        "#define CONFIG_ETHOC",
    ))
    lib.append(_UBootLibComponent(
        ["altera_avalon_cfi_flash"],
        {"CONFIG_SYS_FLASH_BASE": "gen|ioaddr"},
        (
            "#define CONFIG_FLASH_CFI_DRIVER\n"
            "#define CONFIG_SYS_CFI_FLASH_STATUS_POLL /* fix amd flash issue */\n"
            "#define CONFIG_SYS_FLASH_CFI\n"
            "#define CONFIG_SYS_FLASH_USE_BUFFER_WRITE\n"
            "#define CONFIG_SYS_FLASH_PROTECTION\n"
            "#define CONFIG_SYS_MAX_FLASH_BANKS 1\n"
            "#define CONFIG_SYS_MAX_FLASH_SECT 1024\n"
        ),
    ))
    lib.append(_UBootLibComponent(
        [
            "ddr_sdram_component_classic",
            "*altera_avalon_new_sdram_controller*",
            "*altmemddr*",
            "altera_mem_if_ddr*",
        ],
        {
            "CONFIG_SYS_SDRAM_BASE": "gen|kerneladdr",
            "CONFIG_SYS_SDRAM_SIZE": "gen|size",
        },
        None,
    ))
    lib.append(_UBootLibComponent(
        ["triple_speed_ethernet"],
        {
            "CONFIG_SYS_ALTERA_TSE_MAC_BASE":      "gen|ioaddr0",
            "CONFIG_SYS_ALTERA_TSE_SGDMA_RX_BASE": "gen|ioaddr1",
            "CONFIG_SYS_ALTERA_TSE_SGDMA_TX_BASE": "gen|ioaddr2",
            "CONFIG_SYS_ALTERA_TSE_DESC_BASE":     "gen|ioaddr3",
            "CONFIG_SYS_ALTERA_TSE_DESC_SIZE":     "gen|size3",
            "CONFIG_SYS_ALTERA_TSE_RX_FIFO":       f"prop|{E}.RECEIVE_FIFO_DEPTH",
            "CONFIG_SYS_ALTERA_TSE_TX_FIFO":       f"prop|{E}.TRANSMIT_FIFO_DEPTH",
        },
        (
            "#define CONFIG_ALTERA_TSE\n"
            "#define CONFIG_MII\n"
            "#define CONFIG_CMD_MII\n"
            "#define CONFIG_SYS_ALTERA_TSE_PHY_ADDR 1\n"
            "#define CONFIG_SYS_ALTERA_TSE_FLAGS 0\n"
        ),
    ))
    return lib


_UBOOT_LIB: Optional[List[_UBootLibComponent]] = None


def _get_lib() -> List[_UBootLibComponent]:
    global _UBOOT_LIB
    if _UBOOT_LIB is None:
        _UBOOT_LIB = _build_lib()
    return _UBOOT_LIB


def _get_comp_for(comp: "BasicComponent") -> _UBootLibComponent:
    for lc in _get_lib():
        if lc.is_compatible(comp.class_name):
            return lc
    return _UBootLibComponent(None, None, None)


# ---------------------------------------------------------------------------
# UBootHeaderGenerator
# ---------------------------------------------------------------------------

class UBootHeaderGenerator(AbstractSopcGenerator):
    """
    Generates U-Boot CUSTOM_FPGA_H_ header.
    Port of sopc2dts.generators.UBootHeaderGenerator.
    """

    def __init__(self, sys: "AvalonSystem") -> None:
        super().__init__(sys, is_text=True)
        self._handled: Set[int] = set()

    def get_text_output(self, bi: "BoardInfo") -> Optional[str]:
        source_name = self.sys.source_file.name if self.sys.source_file else "unknown"
        res = (
            self.get_small_copyright_notice("header", bi.is_include_time())
            + "#ifndef CUSTOM_FPGA_H_\n"
            + "#define CUSTOM_FPGA_H_\n\n"
            + f"/* generated from {source_name} */\n\n"
        )

        self._handled = set()
        pov = self._get_pov_cpu(bi.get_pov())
        if pov is None:
            logger.error(
                "Unable to find a CPU. U-Boot works best when run on a cpu."
            )
        else:
            intf = pov.get_interface_by_name("data_master")
            if intf is None:
                mm_masters = pov.get_interfaces(SystemDataType.MEMORY_MAPPED, True)
                intf = mm_masters[0] if mm_masters else None
            if intf is not None:
                res += self._get_info_for_slaves_of(intf, 0, pov)

        res += "\n#endif\t//CUSTOM_FPGA_H_\n"
        return res

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_pov_cpu(self, name: Optional[str]) -> Optional["BasicComponent"]:
        if name:
            comp = self.sys.get_component_by_name(name)
            if comp is not None:
                if comp.scd.group.lower() == "cpu":
                    return comp
                logger.warning(
                    "Chosen pov-component '%s' is not a cpu. Trying to find a random cpu.",
                    name,
                )
            else:
                logger.warning(
                    "Chosen pov-component '%s' not found. Trying to find a random cpu.",
                    name,
                )
        for comp in self.sys.get_master_components():
            if comp.scd.group.lower() == "cpu":
                return comp
        return None

    def _get_info_for_slaves_of(
        self,
        master: "Interface",
        offset: int,
        irq_master: "BasicComponent",
    ) -> str:
        res = ""
        for conn in master.connections:
            slave_if = conn.slave_interface
            if slave_if is None:
                continue
            comp = slave_if.owner
            if not res:
                res = (
                    f"/* Dumping slaves of "
                    f"{master.owner.instance_name}.{master.name}*/\n"
                )
            if id(comp) not in self._handled:
                res += "\n" + self._get_info_for(
                    master.owner, irq_master, slave_if, offset
                )
            # Recurse into bridges
            from ..components.base.SICBridge import SICBridge
            if isinstance(comp, SICBridge):
                for intf in comp.interfaces:
                    if intf.is_memory_master():
                        res += self._get_info_for_slaves_of(
                            intf,
                            offset + DTHelper.long_arr_to_long(conn.conn_value or [0]),
                            irq_master,
                        )
        return res

    def _get_info_for(
        self,
        mem_master: "BasicComponent",
        irq_master: "BasicComponent",
        intf: "Interface",
        offset: int,
    ) -> str:
        comp = intf.owner
        self._handled.add(id(comp))
        if_idx = list(comp.interfaces).index(intf) if intf in comp.interfaces else 0
        res = (
            f"/* {comp.instance_name}.{intf.name}"
            f" is a {comp.class_name} */\n"
        )
        res += _get_comp_for(comp).get_headers_for(
            mem_master, irq_master, comp, if_idx, offset
        )
        return res
