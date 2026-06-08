# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Base component handler classes."""

from .SICBridge import SICBridge, BridgeRemovalStrategy
from .SICClockSource import SICClockSource, freq_to_string
from .SICCpuComponent import SICCpuComponent
from .SICEthernet import SICEthernet, PhyMode
from .SICFlash import SICFlash
from .SICGpioController import SICGpioController
from .SICI2CMaster import SICI2CMaster
from .SICMailBox import SICMailBox
from .SICSpiMaster import SICSpiMaster
from .SICUnknown import SICUnknown
from .SCDSelfDescribing import SCDSelfDescribing

__all__ = [
    "BridgeRemovalStrategy",
    "freq_to_string",
    "PhyMode",
    "SCDSelfDescribing",
    "SICBridge",
    "SICClockSource",
    "SICCpuComponent",
    "SICEthernet",
    "SICFlash",
    "SICGpioController",
    "SICI2CMaster",
    "SICMailBox",
    "SICSpiMaster",
    "SICUnknown",
]
