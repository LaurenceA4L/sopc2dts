# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.base.SCDSelfDescribing."""

from __future__ import annotations

from ...model.component import SopcComponentDescription, BasicComponent


class SCDSelfDescribing(SopcComponentDescription):
    """
    SCD built from a component's own embeddedsw.dts.* parameters so the tool
    can produce output without an XML library entry.
    Port of sopc2dts.lib.components.base.SCDSelfDescribing.
    """

    def __init__(self, comp: BasicComponent) -> None:
        group = comp.get_param_val_by_name(BasicComponent.EMBSW_DTS_GROUP) or "unknown"
        vendor = comp.get_param_val_by_name(BasicComponent.EMBSW_DTS_VENDOR) or "unknown"
        device = comp.get_param_val_by_name(BasicComponent.EMBSW_DTS_NAME) or comp.class_name
        super().__init__(comp.class_name, group=group, vendor=vendor)
        self.device = device

    @staticmethod
    def is_self_describing(comp: BasicComponent) -> bool:
        """Return True iff comp has the mandatory embeddedsw DTS vendor + group params."""
        vendor = comp.get_param_val_by_name(BasicComponent.EMBSW_DTS_VENDOR)
        if not vendor:
            return False
        group = comp.get_param_val_by_name(BasicComponent.EMBSW_DTS_GROUP)
        if not group:
            return False
        return True

    def __repr__(self) -> str:
        return f"SCDSelfDescribing({self.class_name!r}, group={self.group!r})"
