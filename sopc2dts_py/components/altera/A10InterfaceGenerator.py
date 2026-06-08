# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2015 Matthew Gerlach <mgerlach@opensource.altera.com>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.A10InterfaceGenerator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...log import logger
from ...model.component import BasicComponent, SopcComponentDescription

if TYPE_CHECKING:
    from ...model.system import AvalonSystem


_EMAC_SIGNAL_SUFFIXES = [
    "", "_md_clk", "_rx_clk_in", "_tx_clk_in",
    "_gtx_clk", "_tx_reset", "_rx_reset",
]


class A10InterfaceGenerator(BasicComponent):
    """
    Moves EMAC interfaces from the generator to their associated HPS EMAC component.
    Port of sopc2dts.lib.components.altera.A10InterfaceGenerator.
    """

    def __init__(
        self,
        class_name: str,
        instance_name: str,
        version: str,
        scd: SopcComponentDescription,
    ) -> None:
        super().__init__(class_name, instance_name, version, scd)
        self._removed = False

    def _move_emacs(self, sys: "AvalonSystem") -> None:
        hps_name = None
        for hps in sys.get_components_by_class("altera_arria10_hps"):
            if self.instance_name.startswith(hps.instance_name + "_"):
                hps_name = hps.instance_name
                break
        if hps_name:
            logger.debug("A10InterfaceGenerator: HPS name is %s", hps_name)
        for i in range(3):
            signal_base = f"emac{i}"
            emac_name = f"{hps_name}_i_emac_{signal_base}" if hps_name else None
            emac = sys.get_component_by_name(emac_name) if emac_name else None
            if emac is None:
                logger.debug("A10InterfaceGenerator: could not find %s", emac_name)
                continue
            for suffix in _EMAC_SIGNAL_SUFFIXES:
                signal = signal_base + suffix
                intf = self.get_interface_by_name(signal)
                if intf is not None:
                    logger.debug(
                        "A10InterfaceGenerator: moving %s to %s",
                        intf.name, emac.instance_name,
                    )
                    intf.owner.remove_interface(intf)
                    emac.add_interface(intf)

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if not self._removed:
            self._removed = True
            self._move_emacs(sys)
            return True
        return False
