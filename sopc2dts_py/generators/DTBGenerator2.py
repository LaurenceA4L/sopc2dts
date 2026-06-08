# sopc2dts - Devicetree generation for Altera systems
#
# Original work Copyright (C) 2012-2015 Walter Goossens <waltergoossens@home.nl>
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Port of sopc2dts.generators.DTBGenerator2.

Produces a binary FDT (.dtb) by piping DTS output through `dtc`.
Falls back to the built-in DTBlob serialiser if dtc is not found.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .DTGenerator import DTGenerator
from ..log import logger

if TYPE_CHECKING:
    from ..model.boardinfo import BoardInfo
    from ..model.system import AvalonSystem


class DTBGenerator2(DTGenerator):
    """
    Binary DTB generator.
    Port of sopc2dts.generators.DTBGenerator2.

    Preferred path: pipe DTS through `dtc -O dtb` (validates output,
    universally available on Linux build hosts).
    Fallback: built-in DTBlob serialiser (no external dependency, works
    on Windows / offline environments).
    """

    def __init__(self, sys: "AvalonSystem") -> None:
        super().__init__(sys, is_text=False)

    # ------------------------------------------------------------------
    # AbstractSopcGenerator interface
    # ------------------------------------------------------------------

    def get_text_output(self, bi: "BoardInfo") -> Optional[str]:
        return None

    def get_binary_output(self, bi: "BoardInfo") -> Optional[bytes]:
        # Try dtc first
        dtb = self._dtc_compile(bi)
        if dtb is not None:
            return dtb
        # Fallback: built-in serialiser
        logger.warning("dtc not found — using built-in DTB serialiser (no validation)")
        return self._builtin_compile(bi)

    # ------------------------------------------------------------------
    # dtc path
    # ------------------------------------------------------------------

    def _dtc_compile(self, bi: "BoardInfo") -> Optional[bytes]:
        """Generate DTS then compile via dtc.  Returns None if dtc unavailable."""
        from .DTSGenerator2 import DTSGenerator2
        dts_gen = DTSGenerator2(self.sys)
        dts_text = dts_gen.get_text_output(bi)
        if dts_text is None:
            return None

        try:
            result = subprocess.run(
                ["dtc", "-O", "dtb", "-I", "dts", "-q", "-"],
                input=dts_text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            logger.error("dtc timed out")
            return None

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            logger.error("dtc failed (rc=%d): %s", result.returncode, stderr)
            return None

        if result.stderr:
            logger.debug("dtc warnings: %s", result.stderr.decode("utf-8", errors="replace"))

        return result.stdout

    # ------------------------------------------------------------------
    # Built-in fallback
    # ------------------------------------------------------------------

    def _builtin_compile(self, bi: "BoardInfo") -> Optional[bytes]:
        """Compile DTB using the built-in DTBlob serialiser."""
        from ..model.devicetree import DTBlob
        from ..model.boardinfo import PovType

        phandle_offset = 0x100 if bi.get_pov_type() != PovType.CPU else 0
        dtb = DTBlob(phandle_offset)
        root = self.get_dt_output(bi)
        if root is None:
            return None
        root.name = ""
        dtb.set_root_node(root)
        return dtb.get_bytes()
