# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Port of sopc2dts.generators.KernelHeadersGenerator.

Generates a C header file containing CMacro defines for CPU components.
Used by pre-3.38 Nios II kernels that need compile-time hardware constants.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .AbstractSopcGenerator import AbstractSopcGenerator

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo
    from ..model.system import AvalonSystem


class KernelHeadersGenerator(AbstractSopcGenerator):
    """
    Generates altera_cpu.h style kernel header.
    Port of sopc2dts.generators.KernelHeadersGenerator.
    """

    def __init__(self, sys: "AvalonSystem") -> None:
        super().__init__(sys, is_text=True)
        self.minimal: bool = True  # Only dump CPU CMacros when True

    def get_text_output(self, bi: "BoardInfo") -> Optional[str]:
        res: Optional[str] = None

        for comp in self.sys.components:
            if self.minimal and comp.scd.group.lower() != "cpu":
                continue

            if res is None:
                res = (
                    self._copyright_notice
                    + "#ifndef _ALTERA_CPU_H_\n"
                    + "#define _ALTERA_CPU_H_\n\n"
                    + "/*\n"
                    + " * Warning:\n"
                    + " * from kernel 2.6.38 onwards this is not really needed anymore\n"
                    + " * Just choose \"Generic devicetree based NiosII system\" as your \n"
                    + " * target board and you should be fine.\n"
                    + " */\n\n"
                )

            res += (
                f"/*\n"
                f" * Dumping parameters for {comp.instance_name}"
                f" (type {comp.scd.group})\n"
                f" * This is not as clean as I hoped but FDT is just a tad late\n"
                f" */\n"
            )

            for param in comp.params:
                if param.name.upper().startswith("EMBEDDEDSW.CMACRO."):
                    macro = param.name[18:].upper()
                    res += f"#define {macro}\t{param.value}\n"

        if res is not None:
            res += "\n#endif //_ALTERA_CPU_H_\n"

        return res
