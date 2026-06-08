# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.hps.ClockManagerV (Cyclone V / Arria 5)."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from ....log import logger
from ....model.component import BasicComponent, SopcComponentDescription
from .ClockManager import (
    ClockManager,
    ClockManagerGateClk,
    ClockManagerGateGroup,
    ClockManagerPClk,
    ClockManagerPll,
)
from .SocFpgaGateClock import SocFpgaGateClock
from .SocFpgaPeripClock import SocFpgaPeripClock
from .SocFpgaPllClock import SocFpgaPllClock

if TYPE_CHECKING:
    from ....model.system import AvalonSystem


class ClockManagerV(ClockManager):
    """
    Cyclone V / Arria 5 HPS clock manager.
    Port of sopc2dts.lib.components.altera.hps.ClockManagerV.
    """

    _scdPLL = SopcComponentDescription("socfpga-pll", "socfpga-pll", "altr", "socfpga-pll-clock")
    _scdPClk = SopcComponentDescription("socfpga-perip-clk", "socfpga-perip-clk", "altr", "socfpga-perip-clk")
    _scdGClk = SopcComponentDescription("socfpga-gate-clk", "socfpga-gate-clk", "altr", "socfpga-gate-clk")

    def __init__(self, bc: BasicComponent) -> None:
        super().__init__(bc)

    def getFirstSupportedVersion(self) -> str:
        return "14.0"

    def preRemovalChecks(self, sys: "AvalonSystem") -> bool:
        hps_name: Optional[str] = None
        for hps in sys.get_components_by_class("altera_hps"):
            if self.instance_name.startswith(hps.instance_name + "_"):
                hps_name = hps.instance_name
                break

        if hps_name is None:
            logger.warning("%s: failed to determine the HPS we belong to", self.instance_name)
            return False

        self.cmPLLs = [
            ClockManagerPll("sdram_pll", 0xC0,
                [hps_name + "_eosc1", hps_name + "_eosc2", hps_name + "_f2s_sdram_ref_clk"],
                [
                    ClockManagerPClk("ddr_dqs_clk",     0x08, None, None, []),
                    ClockManagerPClk("ddr_2x_dqs_clk",  0x0C, None, None, []),
                    ClockManagerPClk("ddr_dq_clk",      0x10, None, None, []),
                    ClockManagerPClk("s2f_usr2_clk",    0x14, None, None, []),
                ],
            ),
            ClockManagerPll("periph_pll", 0x80,
                [hps_name + "_eosc1", hps_name + "_eosc2", hps_name + "_f2s_periph_ref_clk"],
                [
                    ClockManagerPClk("per_nand_mmc_clk", 0x14, None, None, []),
                    ClockManagerPClk("per_base_clk",     0x18, None, None, []),
                    ClockManagerPClk("per_qspi_clk",     0x10, None, None, []),
                    ClockManagerPClk("s2f_usr1_clk",     0x1C, None, None, []),
                    ClockManagerPClk("emac0_clk",        0x08, None, None, []),
                    ClockManagerPClk("emac1_clk",        0x0C, None, None, []),
                ],
            ),
            ClockManagerPll("main_pll", 0x40,
                [hps_name + "_eosc1"],
                [
                    ClockManagerPClk("cfg_s2f_usr0_clk",     0x1C, None, None, []),
                    ClockManagerPClk("main_qspi_clk",        0x14, None, None, []),
                    ClockManagerPClk("dbg_base_clk",         0x10, None, [0xe8, 0, 9], [hps_name + "_eosc1"]),
                    ClockManagerPClk("mpuclk",               0x08, None, [0xe0, 0, 9], []),
                    ClockManagerPClk("mainclk",              0x0C, None, [0xe4, 0, 9], []),
                    ClockManagerPClk("main_nand_sdmmc_clk",  0x18, None, None, []),
                ],
            ),
        ]

        self.cmGGroups = [
            ClockManagerGateGroup(0x60, [
                ClockManagerGateClk("mpu_l2_ram_clk",  False, None,              2,    ["mpuclk"]),
                ClockManagerGateClk("l4_main_clk",     True,  None,              None, ["mainclk"]),
                ClockManagerGateClk("l3_mp_clk",       True,  [0x64, 0x00, 0x02],None, ["mainclk"]),
                ClockManagerGateClk("l3_sp_clk",       False, [0x64, 0x02, 0x02],None, ["l3_mp_clk"]),
                ClockManagerGateClk("l4_mp_clk",       True,  [0x64, 0x04, 0x03],None, ["mainclk", "per_base_clk"]),
                ClockManagerGateClk("l4_sp_clk",       True,  [0x64, 0x07, 0x03],None, ["mainclk", "per_base_clk"]),
                ClockManagerGateClk("dbg_at_clk",      True,  [0x68, 0x00, 0x02],None, ["dbg_base_clk"]),
                ClockManagerGateClk("dbg_clk",         True,  [0x68, 0x02, 0x02],None, ["dbg_at_clk"]),
                ClockManagerGateClk("dbg_trace_clk",   True,  [0x6C, 0x00, 0x03],None, ["dbg_base_clk"]),
                ClockManagerGateClk("dbg_timer_clk",   True,  None,              None, ["dbg_base_clk"]),
                ClockManagerGateClk("cfg_clk",         True,  None,              None, ["cfg_s2f_usr0_clk"]),
                ClockManagerGateClk("h2f_user0_clock", True,  None,              None, ["cfg_s2f_usr0_clk"]),
            ]),
            ClockManagerGateGroup(0xA0, [
                ClockManagerGateClk("emac_0_clk",      True,  None,              None, ["emac0_clk"]),
                ClockManagerGateClk("emac_1_clk",      True,  None,              None, ["emac1_clk"]),
                ClockManagerGateClk("usb_mp_clk",      True,  [0xA4, 0x00, 0x03],None, ["per_base_clk"]),
                ClockManagerGateClk("spi_m_clk",       True,  [0xA4, 0x03, 0x03],None, ["per_base_clk"]),
                ClockManagerGateClk("can0_clk",        True,  [0xA4, 0x06, 0x03],None, ["per_base_clk"]),
                ClockManagerGateClk("can1_clk",        True,  [0xA4, 0x09, 0x03],None, ["per_base_clk"]),
                ClockManagerGateClk("gpio_db_clk",     True,  [0xA8, 0x00, 0x18],None, ["per_base_clk"]),
                ClockManagerGateClk("h2f_user1_clock", True,  None,              None, ["s2f_usr1_clk"]),
                ClockManagerGateClk("sdmmc_clk",       True,  None,              None, [hps_name + "_f2s_periph_ref_clk", "main_nand_sdmmc_clk", "per_nand_mmc_clk"]),
                ClockManagerGateClk("nand_x_clk",      True,  None,              None, [hps_name + "_f2s_periph_ref_clk", "main_nand_sdmmc_clk", "per_nand_mmc_clk"]),
                ClockManagerGateClk("nand_clk",        True,  None,              4,    [hps_name + "_f2s_periph_ref_clk", "main_nand_sdmmc_clk", "per_nand_mmc_clk"]),
                ClockManagerGateClk("qspi_clk",        True,  None,              None, [hps_name + "_f2s_periph_ref_clk", "main_qspi_clk", "per_qspi_clk"]),
            ]),
            ClockManagerGateGroup(0xD8, [
                ClockManagerGateClk("ddr_dqs_clk_gate",    True,  None, None, ["ddr_dqs_clk"]),
                ClockManagerGateClk("ddr_2x_dqs_clk_gate", True,  None, None, ["ddr_2x_dqs_clk"]),
                ClockManagerGateClk("ddr_dq_clk_gate",     True,  None, None, ["ddr_dq_clk"]),
                ClockManagerGateClk("h2f_user2_clock",     True,  None, None, ["s2f_usr2_clk"]),
                ClockManagerGateClk("l3_main_clk",         False, None, None, ["mainclk"]),
            ]),
        ]

        self.cmPeripheralClks = [
            ClockManagerPClk("mpu_periph_clk", 0, 4, None, ["mpuclk"]),
        ]

        return True

    def getSocFpgaPllClock(self, cName, iName, ver):
        return SocFpgaPllClock(cName, iName, ver, self._scdPLL)

    def getSocFpgaPeripClock(self, cName, iName, ver, reg, div, divreg):
        return SocFpgaPeripClock(cName, iName, ver, self._scdPClk, reg, div, divreg)

    def getSocFpgaGateClock(self, cmgClk, ver):
        return SocFpgaGateClock(cmgClk, ver, self._scdGClk)
