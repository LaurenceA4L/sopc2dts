# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2013 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.GenericTristateController."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...log import logger
from ...model.component import BasicComponent
from ..base.SICUnknown import SICUnknown

if TYPE_CHECKING:
    from ...model.system import AvalonSystem


class GenericTristateController(BasicComponent):
    """
    Detects connected chip type (CFI flash or LAN91C111) and self-replaces.
    Port of sopc2dts.lib.components.altera.GenericTristateController.
    """

    def __init__(self, class_name: str, instance_name: str, version: str) -> None:
        super().__init__(class_name, instance_name, version, SICUnknown(class_name))

    def remove_from_system_if_possible(self, sys: "AvalonSystem") -> bool:
        driver_type = self.get_param_val_by_name(self.EMBSW_CONF + ".softwareDriver")
        if driver_type is None:
            driver_type = self.get_param_val_by_name(
                self.EMBSW_CONF + ".hwClassnameDriverSupportDefault"
            )
        if driver_type is None:
            logger.warning(
                "GenericTristateController: %s failed to detect driver type",
                self.instance_name,
            )
            return False

        dl = driver_type.lower()
        if dl in ("altera_avalon_cfi_flash_driver", "altera_avalon_cfi_flash"):
            logger.info(
                "GenericTristateController: %s is CFI-Flash", self.instance_name
            )
            from ..base.SICFlash import SICFlash
            from ...model.component_lib import SopcComponentLib
            flash = SICFlash(self)
            flash.scd = SopcComponentLib.get_instance().get_scd_by_class_name(
                "altera_avalon_cfi_flash"
            )
            sys.remove_component(self)
            sys.add_component(flash)
            return True

        if dl == "altera_avalon_lan91c111":
            logger.info(
                "GenericTristateController: %s is SMSC LAN91C111", self.instance_name
            )
            from .SICLan91c111 import SICLan91c111
            from ...model.component_lib import SopcComponentLib
            lan = SICLan91c111(self)
            lan.scd = SopcComponentLib.get_instance().get_scd_by_class_name(
                "altera_avalon_lan91c111"
            )
            sys.remove_component(self)
            sys.add_component(lan)
            return True

        logger.warning(
            "GenericTristateController: %s unsupported driver type: %s",
            self.instance_name, driver_type,
        )
        return False
