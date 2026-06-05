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
Shared enumerations used across the model layer.

Kept in a separate module to avoid circular imports between
component.py, connection.py and system.py.
"""

from enum import Enum, auto


class SystemDataType(Enum):
    """Interface / connection data types — mirrors AvalonSystem.SystemDataType."""
    MEMORY_MAPPED = auto()
    STREAMING = auto()
    INTERRUPT = auto()
    CLOCK = auto()
    CUSTOM_INSTRUCTION = auto()
    RESET = auto()
    CONDUIT = auto()


class ParameterAction(Enum):
    """Controls how sopc-parameters are emitted into DTS — mirrors BasicComponent.parameter_action."""
    NONE = auto()
    CMACRO = auto()
    ALL = auto()
