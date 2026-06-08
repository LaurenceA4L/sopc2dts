# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Matthew Gerlach <mgerlach@altera.com>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.snps.DwGpio."""

from __future__ import annotations

from typing import Optional, Union

from ...model.component import BasicComponent, SopcComponentDescription
from ..base.SICGpioController import SICGpioController


class DwGpio(SICGpioController):
    """
    Synopsys DesignWare APB GPIO controller.
    Dual constructor: copy-constructor (BasicComponent) or regular.
    Port of sopc2dts.lib.components.snps.DwGpio.
    """

    def __init__(
        self,
        comp_or_class_name: Union[BasicComponent, str],
        instance_name: Optional[str] = None,
        version: Optional[str] = None,
        scd: Optional[SopcComponentDescription] = None,
    ) -> None:
        if isinstance(comp_or_class_name, BasicComponent):
            # SICGpioController is copy-constructor-only; pass BasicComponent directly.
            super().__init__(comp_or_class_name)
        else:
            # Regular constructor: wrap in BasicComponent first.
            bc = BasicComponent(comp_or_class_name, instance_name, version or "", scd)
            super().__init__(bc)

    # ------------------------------------------------------------------
    # Phase 2 stub
    # ------------------------------------------------------------------

    def to_dt_node(self, board_info: object, conn: object) -> object:
        raise NotImplementedError("DwGpio.to_dt_node — Phase 2")
