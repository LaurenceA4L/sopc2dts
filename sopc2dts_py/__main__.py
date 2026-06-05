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
Entry point — mirrors the CLI of the original Sopc2DTS.java.

All flags from the Java tool are preserved for drop-in compatibility.
"""

import argparse
import sys
from importlib.metadata import version, PackageNotFoundError

from .log import setup_logging, logger

try:
    __version__ = version("sopc2dts")
except PackageNotFoundError:
    __version__ = "dev"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sopc2dts",
        description="Generate a Linux devicetree from an Altera/Intel sopcinfo or Qsys file.",
    )

    p.add_argument(
        "-i", "--input",
        dest="input",
        metavar="sopcinfo_file",
        help="The sopcinfo or .qsys input file (optional in --gui mode)",
    )
    p.add_argument(
        "-o", "--output",
        dest="output",
        metavar="filename",
        help="Output filename (default: stdout)",
    )
    p.add_argument(
        "-b", "--board",
        dest="board",
        metavar="boardinfo_file",
        action="append",
        default=[],
        help="Board description file (can be specified multiple times)",
    )
    p.add_argument(
        "-t", "--type",
        dest="output_type",
        metavar="type",
        default="dts",
        choices=["dtb", "dtb-hex8", "dtb-hex32", "dtb-char-arr", "dts", "uboot", "kernel"],
        help="Output type (default: dts)",
    )
    p.add_argument(
        "-p", "--pov",
        dest="pov",
        metavar="component_name",
        default="",
        help="Point-of-view component (default: first CPU found)",
    )
    p.add_argument(
        "--pov-type",
        dest="pov_type",
        metavar="type",
        default="cpu",
        choices=["cpu", "pci"],
        help="Point-of-view device type (default: cpu)",
    )
    p.add_argument(
        "-s", "--sort",
        dest="sort",
        metavar="sort",
        default="",
        choices=["", "none", "address", "name", "label"],
        help="Sort components by (none/address/name/label)",
    )
    p.add_argument(
        "--bridge-removal",
        dest="bridge_removal",
        metavar="strategy",
        default="balanced",
        choices=["all", "balanced", "none"],
        help="Bridge removal strategy (default: balanced)",
    )
    p.add_argument(
        "--bridge-ranges",
        dest="bridge_ranges",
        metavar="ranges",
        default="",
        choices=["", "none", "bridge", "child"],
        help="What to describe in bridge address translations",
    )
    p.add_argument(
        "--bootargs",
        dest="bootargs",
        metavar="kernel-args",
        default="",
        help="Default kernel arguments for the 'chosen' section",
    )
    p.add_argument(
        "--sopc-parameters",
        dest="sopc_parameters",
        metavar="mode",
        default="none",
        choices=["none", "cmacro", "all"],
        help="Which sopc-parameters to include in DTS (default: none)",
    )
    p.add_argument(
        "-e", "--extra-component-libs",
        dest="extra_component_libs",
        metavar="sopc_component_xml_file",
        action="append",
        default=[],
        help="Extra component library XML files (can be specified multiple times)",
    )
    p.add_argument(
        "-c", "--clocks",
        dest="show_clocks",
        action="store_true",
        default=False,
        help="Show clocks in DTS / graph",
    )
    p.add_argument(
        "--conduits",
        dest="show_conduits",
        action="store_true",
        default=False,
        help="Show conduit interfaces in graph",
    )
    p.add_argument(
        "--reset",
        dest="show_reset",
        action="store_true",
        default=False,
        help="Show reset interfaces in graph",
    )
    p.add_argument(
        "--streaming",
        dest="show_streaming",
        action="store_true",
        default=False,
        help="Show streaming interfaces in graph",
    )
    p.add_argument(
        "--force-ALTR",
        dest="force_altr_upper",
        action="store_true",
        default=False,
        help="Force uppercase 'ALTR' in compatible strings and property names",
    )
    p.add_argument(
        "--force-altr",
        dest="force_altr_lower",
        action="store_true",
        default=False,
        help="Force lowercase 'altr' in compatible strings and property names",
    )
    p.add_argument(
        "--no-timestamp",
        dest="exclude_timestamp",
        action="store_true",
        default=False,
        help="Don't add a timestamp to generated files",
    )
    p.add_argument(
        "-m", "--mimic-sopc-create-header-files",
        dest="mimic_altera",
        action="store_true",
        default=False,
        help="Try to behave like sopc-create-header-files",
    )
    p.add_argument(
        "-g", "--gui",
        dest="gui",
        action="store_true",
        default=False,
        help="Run in GUI mode (opens browser)",
    )
    p.add_argument(
        "-v", "--verbose",
        dest="verbose",
        action="count",
        default=0,
        help="Increase verbosity (use -v for INFO, -vv for DEBUG)",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"sopc2dts {__version__}",
    )

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.gui:
        _run_gui(args)
        return

    if not args.input:
        parser.error("--input is required unless running in --gui mode")

    _run_cli(args)


def _run_cli(args) -> None:
    logger.info("sopc2dts %s", __version__)
    # TODO Phase 1: wire up parsers, model, generators
    logger.error("CLI generation not yet implemented — work in progress.")
    sys.exit(1)


def _run_gui(args) -> None:
    try:
        from .gui.launcher import launch
    except ImportError:
        logger.error(
            "GUI dependencies not installed. Run: pip install sopc2dts[gui]"
        )
        sys.exit(1)
    launch(input_file=args.input or "")


if __name__ == "__main__":
    main()
