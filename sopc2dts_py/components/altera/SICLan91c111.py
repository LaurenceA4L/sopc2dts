# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2013 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Port of sopc2dts.lib.components.altera.SICLan91c111."""

from __future__ import annotations

from typing import List, Optional, Union, TYPE_CHECKING

from ...model.component import BasicComponent, SopcComponentDescription
from ..base.SICEthernet import SICEthernet

if TYPE_CHECKING:
    from ...model.connection import Connection


class SICLan91c111(SICEthernet):
    """
    SMSC LAN91C111 ethernet chip — extends SICEthernet, adds registerOffset.
    Port of sopc2dts.lib.components.altera.SICLan91c111.
    """

    def __init__(
        self,
        comp_or_class_name: Union[BasicComponent, str],
        instance_name: Optional[str] = None,
        version: Optional[str] = None,
        scd: Optional[SopcComponentDescription] = None,
    ) -> None:
        super().__init__(comp_or_class_name, instance_name, version, scd)

    def _get_addr_from_connection(self, conn: "Connection") -> List[int]:
        """Override to add registerOffset. Phase 2 helper."""
        try:
            v = self.get_param_val_by_name("registerOffset")
            if v is None:
                v = self.get_param_val_by_name(
                    self.EMBSW_CMACRO + ".LAN91C111_REGISTERS_OFFSET"
                )
            reg_offset = int(v, 0) if v else 0
        except Exception:
            reg_offset = 0
        if conn.conn_value:
            return [x + reg_offset for x in conn.conn_value]
        return [reg_offset]
