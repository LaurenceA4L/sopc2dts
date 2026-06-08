# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Matthew Gerlach <mgerlach@altera.com>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.InterfaceGenerator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...model.component import BasicComponent, SopcComponentDescription

if TYPE_CHECKING:
    from ...model.system import AvalonSystem

_H2F_USERCLK_SCD = SopcComponentDescription("clock", "clock", "altr", "clock")


class InterfaceGenerator(BasicComponent):
    """
    Extracts h2f_userN_clock interfaces into standalone ClockSource components.
    Port of sopc2dts.lib.components.altera.InterfaceGenerator.
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

    def _extract_user_clock(self, num: int, sys: "AvalonSystem") -> None:
        from ..base.SICClockSource import SICClockSource
        if_name = f"h2f_user{num}_clock"
        intf = self.get_interface_by_name(if_name)
        if intf is not None:
            self._interfaces.remove(intf)
            new_clk = SICClockSource.__new__(SICClockSource)
            BasicComponent.__init__(
                new_clk, if_name, if_name, None, _H2F_USERCLK_SCD
            )
            new_clk._parameters = []
            new_clk._interfaces = []
            new_clk.add_interface(intf)

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        if not self._removed:
            self._removed = True
            for i in range(3):
                self._extract_user_clock(i, sys)
            return True
        return False
