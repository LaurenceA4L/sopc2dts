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
    from pathlib import Path

    from .model.system import AvalonSystem
    from .model.boardinfo import BoardInfo, AltrStyle, PovType, SortType
    from .model.enums import ParameterAction
    from .model.component_lib import SopcComponentLib
    from .parsers import (
        load_system,
        load_boardinfo,
        load_component_lib,
        load_component_libs_in_dir,
    )
    from .generators.GeneratorFactory import GeneratorFactory
    from .components.base.SICBridge import SICBridge

    logger.info("sopc2dts %s", __version__)
    AvalonSystem.set_sopc2dts_version(__version__)

    # ------------------------------------------------------------------
    # 1. Load component libraries
    # ------------------------------------------------------------------
    # Bundled XMLs sit alongside the package root (repo root in dev).
    # TODO: move XMLs into sopc2dts_py/data/ and use importlib.resources
    lib_dir = Path(__file__).parent.parent
    try:
        lib = load_component_libs_in_dir(lib_dir)
        logger.debug("Component library loaded from %s", lib_dir)
    except Exception as exc:
        logger.warning("Could not load bundled component libraries: %s", exc)
        lib = SopcComponentLib.get_instance()

    for extra in args.extra_component_libs:
        try:
            load_component_lib(extra, lib)
            logger.info("Loaded extra component lib: %s", extra)
        except Exception as exc:
            logger.error("Failed to load extra component lib '%s': %s", extra, exc)

    # ------------------------------------------------------------------
    # 2. Parse input file
    # ------------------------------------------------------------------
    try:
        system = load_system(args.input)
    except Exception as exc:
        logger.error("Failed to parse '%s': %s", args.input, exc)
        sys.exit(1)
    logger.info("Parsed system '%s' (%d components)", system.name, len(system.components))

    # ------------------------------------------------------------------
    # 3. Build BoardInfo
    # ------------------------------------------------------------------
    bi = BoardInfo()

    for board_file in args.board:
        try:
            bi = load_boardinfo(board_file)
        except Exception as exc:
            logger.error("Failed to load boardinfo '%s': %s", board_file, exc)
            sys.exit(1)

    # Apply CLI overrides — these beat whatever the boardinfo file said
    if args.pov:
        bi.set_pov(args.pov)
    bi.set_pov_type(PovType.PCI if args.pov_type == "pci" else PovType.CPU)

    if args.sort:
        sort_map = {
            "none":    SortType.NONE,
            "address": SortType.ADDRESS,
            "name":    SortType.NAME,
            "label":   SortType.LABEL,
        }
        bi.set_sort_type(sort_map.get(args.sort, SortType.NONE))

    if args.bootargs:
        bi.boot_args = args.bootargs
    if args.exclude_timestamp:
        bi.include_time = False
    if args.show_clocks:
        bi.show_clock_tree = True
    if args.show_conduits:
        bi.show_conduits = True
    if args.show_reset:
        bi.show_resets = True
    if args.show_streaming:
        bi.show_streaming = True

    if args.force_altr_upper:
        bi._altr_style = AltrStyle.FORCE_UPPER
    elif args.force_altr_lower:
        bi._altr_style = AltrStyle.FORCE_LOWER

    param_map = {"all": ParameterAction.ALL, "cmacro": ParameterAction.CMACRO}
    bi._dump_parameters = param_map.get(args.sopc_parameters, ParameterAction.NONE)

    # ------------------------------------------------------------------
    # 4. Bridge removal strategy
    # ------------------------------------------------------------------
    SICBridge.set_removal_strategy(args.bridge_removal.upper())

    # ------------------------------------------------------------------
    # 5. Post-parse cleanup
    # ------------------------------------------------------------------
    system.recheck_components()

    # ------------------------------------------------------------------
    # 6. Select generator
    # ------------------------------------------------------------------
    gen_type = GeneratorFactory.get_type_by_name(args.output_type)
    if gen_type is None:
        logger.error("Unknown output type '%s'", args.output_type)
        sys.exit(1)

    generator = GeneratorFactory.create_generator_for(system, gen_type)
    if generator is None:
        logger.error("Output type '%s' is not yet implemented.", args.output_type)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 7. Generate
    # ------------------------------------------------------------------
    try:
        if generator.is_text_output():
            output = generator.get_text_output(bi)
        else:
            output = generator.get_binary_output(bi)
    except Exception as exc:
        logger.error("Generation failed: %s", exc)
        sys.exit(1)

    if output is None:
        logger.error("Generator returned no output.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 8. Write output
    # ------------------------------------------------------------------
    if args.output:
        out_path = Path(args.output)
        try:
            if isinstance(output, bytes):
                out_path.write_bytes(output)
            else:
                out_path.write_text(output, encoding="utf-8")
            logger.info("Written to %s", out_path)
        except OSError as exc:
            logger.error("Failed to write '%s': %s", args.output, exc)
            sys.exit(1)
    else:
        if isinstance(output, bytes):
            sys.stdout.buffer.write(output)
        else:
            sys.stdout.write(output)


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
