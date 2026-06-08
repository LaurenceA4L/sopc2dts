# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2016 Tien Hock Loh <thloh@altera.com>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.PCIeCompiler."""

from __future__ import annotations

from ...model.component import BasicComponent

_PCIE_CLASS_NAMES = frozenset({
    "altera_pcie_a10_hip",
    "altera_pcie_cv_hip_avmm",
    "altera_pcie_av_hip_avmm",
})


class PCIeCompiler:
    """
    Static factory: returns PCIeRootPort when the SCD device is 'pcie-root-port'.
    Port of sopc2dts.lib.components.altera.PCIeCompiler.
    """

    @staticmethod
    def get_pcie_component(comp: BasicComponent) -> BasicComponent:
        if comp.class_name.lower() in _PCIE_CLASS_NAMES:
            if comp.scd and comp.scd.device and \
                    comp.scd.device.lower() == "pcie-root-port":
                from .PCIeRootPort import PCIeRootPort
                return PCIeRootPort(comp)
        return comp
