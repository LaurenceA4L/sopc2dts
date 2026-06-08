# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.hps.ClockManagerA10 (Arria 10)."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

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


class ClockManagerA10(ClockManager):
    """
    Arria 10 HPS clock manager.
    Port of sopc2dts.lib.components.altera.hps.ClockManagerA10.
    """

    _scdPLL  = SopcComponentDescription("socfpga-a10-pll",      "socfpga-a10-pll",      "altr", "socfpga-a10-pll-clock")
    _scdPClk = SopcComponentDescription("socfpga-a10-perip-clk","socfpga-a10-perip-clk","altr", "socfpga-a10-perip-clk")
    _scdGClk = SopcComponentDescription("socfpga-a10-gate-clk", "socfpga-a10-gate-clk", "altr", "socfpga-a10-gate-clk")

    def __init__(self, bc: BasicComponent) -> None:
        super().__init__(bc)

    def getFirstSupportedVersion(self) -> str:
        return "14.0"

    def preRemovalChecks(self, sys: "AvalonSystem") -> bool:
        hps_name: Optional[str] = None
        for hps in sys.get_components_by_class("altera_arria10_hps"):
            if self.instance_name.startswith(hps.instance_name + "_"):
                hps_name = hps.instance_name
                break

        if hps_name is None:
            logger.warning("%s: failed to determine the HPS_A10 we belong to", self.instance_name)
            return False

        noc_free_clk = ["noc_free_clk"]
        osc1         = hps_name + "_eosc1"
        cb_intosc_ls = hps_name + "_cb_intosc_ls_clk"
        cb_intosc_hs = hps_name + "_cb_intosc_hs_div2_clk"
        f2s_free_clk = hps_name + "_f2s_free_clk"

        self.cmPLLs = [
            ClockManagerPll("main_pll", 0x40,
                [osc1, cb_intosc_ls, f2s_free_clk],
                [
                    ClockManagerPClk("main_mpu_base_clk",    0,    None, [0x140, 0,  11], []),
                    ClockManagerPClk("main_noc_base_clk",    0,    None, [0x144, 0,  11], []),
                    ClockManagerPClk("main_emaca_clk",       0x28, None, None, []),
                    ClockManagerPClk("main_emacb_clk",       0x2c, None, None, []),
                    ClockManagerPClk("main_emac_ptp_clk",    0x30, None, None, []),
                    ClockManagerPClk("main_gpio_db_clk",     0x34, None, None, []),
                    ClockManagerPClk("main_sdmmc_clk",       0x38, None, None, []),
                    ClockManagerPClk("main_s2f_usr0_clk",    0x3c, None, None, []),
                    ClockManagerPClk("main_s2f_usr1_clk",    0x40, None, None, []),
                    ClockManagerPClk("main_hmc_pll_ref_clk", 0x44, None, None, []),
                    ClockManagerPClk("main_periph_ref_clk",  0x5c, None, None, []),
                ],
            ),
            ClockManagerPll("periph_pll", 0xC0,
                [osc1, cb_intosc_ls, f2s_free_clk, "main_periph_ref_clk"],
                [
                    ClockManagerPClk("peri_mpu_base_clk",    0,    None, [0x140, 16, 11], []),
                    ClockManagerPClk("peri_noc_base_clk",    0,    None, [0x144, 16, 11], []),
                    ClockManagerPClk("peri_emaca_clk",       0x28, None, None, []),
                    ClockManagerPClk("peri_emacb_clk",       0x2c, None, None, []),
                    ClockManagerPClk("peri_emac_ptp_clk",    0x30, None, None, []),
                    ClockManagerPClk("peri_gpio_db_clk",     0x34, None, None, []),
                    ClockManagerPClk("peri_sdmmc_clk",       0x38, None, None, []),
                    ClockManagerPClk("peri_s2f_usr0_clk",    0x3c, None, None, []),
                    ClockManagerPClk("peri_s2f_usr1_clk",    0x40, None, None, []),
                    ClockManagerPClk("peri_hmc_pll_ref_clk", 0x44, None, None, []),
                ],
            ),
        ]

        self.cmGGroups = [
            ClockManagerGateGroup(0x48, [
                ClockManagerGateClk("mpu_periph_clk", True, None,              4,    ["mpu_free_clk"]),
                ClockManagerGateClk("l4_main_clk",    True, [0xa8, 0,  2],    None, noc_free_clk),
                ClockManagerGateClk("l4_mp_clk",      True, [0xa8, 8,  2],    None, noc_free_clk),
                ClockManagerGateClk("l4_sp_clk",      True, [0xa8, 16, 2],    None, noc_free_clk),
            ]),
            ClockManagerGateGroup(0xc8, [
                ClockManagerGateClk("emac0_clk",      True, None, None, []),
                ClockManagerGateClk("emac1_clk",      True, None, None, []),
                ClockManagerGateClk("emac2_clk",      True, None, None, []),
                ClockManagerGateClk("emac_ptp_clk",   True, None, None, []),
                ClockManagerGateClk("gpio_db_clk",    True, None, None, []),
                ClockManagerGateClk("sdmmc_clk",      True, None, None, ["sdmmc_free_clk"]),
                ClockManagerGateClk("s2f_user1_clk",  True, None, None, ["peri_s2f_usr1_clk"]),
                ClockManagerGateClk("reserved",       True, None, None, []),
                ClockManagerGateClk("usb_clk",        True, None, None, ["l4_mp_clk"]),
                ClockManagerGateClk("spi_m_clk",      True, None, None, ["l4_main_clk"]),
                ClockManagerGateClk("nand_clk",       True, None, None, ["l4_mp_clk"]),
                ClockManagerGateClk("qspi_clk",       True, None, None, ["l4_main_clk"]),
            ]),
        ]

        self.cmPeripheralClks = [
            ClockManagerPClk("mpu_free_clk",   0x60,  None, None, ["main_mpu_base_clk", "peri_mpu_base_clk", osc1, cb_intosc_hs, f2s_free_clk]),
            ClockManagerPClk("noc_free_clk",   0x64,  None, None, ["main_noc_base_clk", "peri_noc_base_clk", osc1, cb_intosc_hs, f2s_free_clk]),
            ClockManagerPClk("s2f_usr1_clk",   0x104, None, None, ["main_s2f_usr1_clk", "peri_s2f_usr1_clk", osc1, cb_intosc_hs, f2s_free_clk]),
            ClockManagerPClk("sdmmc_free_clk", 0xf8,  4,    None, ["main_sdmmc_clk",    "peri_sdmmc_clk",    osc1, cb_intosc_hs, f2s_free_clk]),
            ClockManagerPClk("l4_sys_free_clk",None,  4,    None, noc_free_clk),
        ]

        return True

    def getSocFpgaPllClock(self, cName, iName, ver):
        return SocFpgaPllClock(cName, iName, ver, self._scdPLL)

    def getSocFpgaPeripClock(self, cName, iName, ver, reg, div, divreg):
        return SocFpgaPeripClock(cName, iName, ver, self._scdPClk, reg, div, divreg)

    def getSocFpgaGateClock(self, cmgClk, ver):
        return SocFpgaGateClock(cmgClk, ver, self._scdGClk)
