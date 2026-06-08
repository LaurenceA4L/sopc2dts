# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2011-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Port of sopc2dts.generators.GeneratorFactory.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional, TYPE_CHECKING

from .AbstractSopcGenerator import AbstractSopcGenerator

if TYPE_CHECKING:
    from ..model.system import AvalonSystem


class GeneratorType(Enum):
    """Port of GeneratorFactory.GeneratorType."""
    DTS            = auto()
    DTB            = auto()
    DTB_IHEX8      = auto()
    DTB_IHEX32     = auto()
    DTB_CHAR_ARR   = auto()
    GRAPH          = auto()
    U_BOOT         = auto()
    KERNEL_HEADERS = auto()
    SOPC_HEADER    = auto()   # SopcCreateHeaderFilesImitator (--mimic-sopc-create-header-files)


class GeneratorFactory:
    """
    Factory that maps a GeneratorType to a concrete generator instance.
    Port of sopc2dts.generators.GeneratorFactory.
    """

    @staticmethod
    def create_generator_for(
        sys: "AvalonSystem",
        gen_type: GeneratorType,
    ) -> Optional[AbstractSopcGenerator]:
        """Port of GeneratorFactory.createGeneratorFor."""
        from .DTSGenerator2 import DTSGenerator2
        from .DTBGenerator2 import DTBGenerator2
        from .DTBHex8Generator import DTBHex8Generator
        from .DTBHex32Generator import DTBHex32Generator
        from .DTBCCharArray import DTBCCharArray
        from .KernelHeadersGenerator import KernelHeadersGenerator
        from .UBootHeaderGenerator import UBootHeaderGenerator
        from .SopcCreateHeaderFilesImitator import SopcCreateHeaderFilesImitator
        from .GraphGenerator import GraphGenerator

        return {
            GeneratorType.DTS:            DTSGenerator2(sys),
            GeneratorType.DTB:            DTBGenerator2(sys),
            GeneratorType.DTB_IHEX8:      DTBHex8Generator(sys),
            GeneratorType.DTB_IHEX32:     DTBHex32Generator(sys),
            GeneratorType.DTB_CHAR_ARR:   DTBCCharArray(sys),
            GeneratorType.KERNEL_HEADERS: KernelHeadersGenerator(sys),
            GeneratorType.U_BOOT:         UBootHeaderGenerator(sys),
            GeneratorType.SOPC_HEADER:    SopcCreateHeaderFilesImitator(sys),
            GeneratorType.GRAPH:          GraphGenerator(sys),
        }.get(gen_type)

    @staticmethod
    def get_type_by_name(name: str) -> Optional[GeneratorType]:
        """Lookup GeneratorType by case-insensitive name."""
        name_upper = name.upper().replace("-", "_")
        try:
            return GeneratorType[name_upper]
        except KeyError:
            return None
