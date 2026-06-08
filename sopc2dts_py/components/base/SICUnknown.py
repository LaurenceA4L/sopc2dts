# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.base.SICUnknown."""

from __future__ import annotations

from ...model.component import SopcComponentDescription


class SICUnknown(SopcComponentDescription):
    """
    Sentinel SCD used when no library entry matches a component's class name.
    Port of sopc2dts.lib.components.base.SICUnknown.
    """

    def __init__(self, sopc_class_name: str) -> None:
        super().__init__(sopc_class_name, group="unknown", vendor="unknown")

    def __repr__(self) -> str:
        return f"SICUnknown({self.class_name!r})"
