# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2014 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Port of sopc2dts.generators.GraphGenerator.

Emits a Graphviz dot file visualising system components and connections.
Render with: dot -Tsvg system.dot -o system.svg
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .AbstractSopcGenerator import AbstractSopcGenerator
from ..model.enums import SystemDataType
from ..model.devicetree import DTHelper

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo
    from ..model.system import AvalonSystem
    from ..model.component import Interface


# Mapping from SystemDataType to dot colour (None = hidden by default)
_COLOR_MAP = {
    SystemDataType.MEMORY_MAPPED:     "blue",
    SystemDataType.INTERRUPT:         "pink",
    SystemDataType.CUSTOM_INSTRUCTION:"seagreen",
}
_OPTIONAL_COLOR_MAP = {
    SystemDataType.CLOCK:    ("show_clock_tree",  "green"),
    SystemDataType.CONDUIT:  ("show_conduits",    "salmon"),
    SystemDataType.RESET:    ("show_resets",      "gray"),
    SystemDataType.STREAMING:("show_streaming",   "yellow"),
}


class GraphGenerator(AbstractSopcGenerator):
    """
    Graphviz dot graph of the system.
    Port of sopc2dts.generators.GraphGenerator.
    """

    def __init__(self, sys: "AvalonSystem") -> None:
        super().__init__(sys, is_text=True)

    def get_text_output(self, bi: "BoardInfo") -> Optional[str]:
        res = 'digraph sopc2dot {\n  node [shape=rect]\n'

        # Node declarations
        for comp in self.sys.components:
            res += (
                f'  {comp.instance_name} [label=<<table border="0">\n'
                f'\t<tr><td port="name" bgcolor="lightgray">'
                f'{comp.instance_name}</td></tr>\n'
                f'\t<tr><td port="class">Class: {comp.class_name}</td></tr>\n'
            )
            for intf in comp.interfaces:
                color = self._color_for(intf, bi)
                if color is not None:
                    ud = _undashify(intf.name)
                    res += (
                        f'\t<tr><td port="{ud}" bgcolor="light{color}">'
                        f' {intf.name}</td></tr>\n'
                    )
            res += '\t</table>>]\n'

        # Edges
        for comp in self.sys.components:
            for master_if in comp.interfaces:
                color = self._color_for(master_if, bi)
                if not master_if.is_master or color is None:
                    continue
                for conn in master_if.connections:
                    slave_if = conn.slave_interface
                    if slave_if is None:
                        continue
                    src = f'{comp.instance_name}:{_undashify(master_if.name)}'
                    dst = (
                        f'{slave_if.owner.instance_name}:'
                        f'{_undashify(slave_if.name)}'
                    )
                    edge = f'{src} -> {dst} [color="{color}"'
                    if conn.type == SystemDataType.MEMORY_MAPPED:
                        addr = DTHelper.long_arr_to_hex_string(conn.conn_value or [])
                        edge += f' label="{addr}"'
                    elif conn.type == SystemDataType.INTERRUPT:
                        irq = DTHelper.long_arr_to_long(conn.conn_value or [0])
                        edge += f' label="{irq}"'
                    edge += ']\n'
                    res += edge

        res += '}\n'
        return res

    def _color_for(self, intf: "Interface", bi: "BoardInfo") -> Optional[str]:
        dt = intf.type
        if dt in _COLOR_MAP:
            return _COLOR_MAP[dt]
        if dt in _OPTIONAL_COLOR_MAP:
            attr, color = _OPTIONAL_COLOR_MAP[dt]
            return color if getattr(bi, attr, False) else None
        return None


def _undashify(name: str) -> str:
    """Graphviz HTML port names can't contain - or _, replace with letters."""
    return name.replace('-', 'd').replace('_', 'u')
