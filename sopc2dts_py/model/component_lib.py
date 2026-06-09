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
Port of sopc2dts.lib.SopcComponentLib — the singleton registry that maps IP
component class names to SopcComponentDescription objects loaded from
``sopc_components_*.xml`` library files.

Java ran the library XML through a SAX ContentHandler. Here we parse each
file with ElementTree and walk the tree once, matching the same data model.

``get_component_for_class`` and ``cast_to_group_specific_object`` reference
many specialised BasicComponent subclasses (TSEMonolithic, SICSgdma,
CortexA9GIC, etc.) that are not yet ported. Those paths fall back to plain
BasicComponent with TODO comments; they will be wired up during the
Component handlers phase.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET

from ..log import logger
from .component import BasicComponent, SopcComponentDescription


class SopcComponentLib:
    """
    Singleton registry of known IP component descriptions.
    Port of sopc2dts.lib.SopcComponentLib.

    Usage::

        lib = SopcComponentLib.get_instance()
        lib.load_component_libs_in_dir(Path("."))
        comp = lib.get_component_for_class("altera_nios2", "cpu_0", "13.0")
    """

    _instance: Optional["SopcComponentLib"] = None

    def __init__(self) -> None:
        self._lib_components: List[SopcComponentDescription] = []

    @classmethod
    def get_instance(cls) -> "SopcComponentLib":
        """Return the process-wide singleton, creating it if needed."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_component_lib(self, path: Path) -> int:
        """
        Parse one ``sopc_components_*.xml`` file and add its entries to the
        registry. Returns the number of new SCDs added.
        Port of SopcComponentLib.loadComponentLib.
        """
        old_size = len(self._lib_components)
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            self._parse_lib_root(root)
        except ET.ParseError as e:
            logger.exception("XML parse error in %s: %s", path, e)
        except OSError as e:
            logger.exception("Could not read %s: %s", path, e)
        added = len(self._lib_components) - old_size
        logger.debug("Loaded %d components from %s", added, path)
        return added

    def load_component_libs_in_dir(self, directory: Path) -> None:
        """
        Scan *directory* for ``sopc_components_*.xml`` files and load each.
        Port of SopcComponentLib.loadComponentLibsInWorkDir.
        """
        directory = Path(directory)
        if not directory.is_dir():
            logger.warning("Component lib directory not found: %s", directory)
            return
        for xml_file in sorted(directory.glob("sopc_components_*.xml")):
            self.load_component_lib(xml_file)

    def _parse_lib_root(self, root: ET.Element) -> None:
        """
        Walk the parsed XML tree replicating the SAX start/end element
        logic from the Java ContentHandler implementation.
        """
        if root.tag.upper() != "SOPC2DTS_COMPONENTLIB":
            logger.debug("Skipping non-componentlib root element: %s", root.tag)
            return

        vendor = root.get("vendor", "unknown")

        for elem in root:
            if elem.tag.lower() == "s2dcomponent":
                scd = self._parse_s2d_component(elem, vendor)
                if scd is not None:
                    self._lib_components.append(scd)
            else:
                logger.debug("Component lib: unexpected top-level element %s", elem.tag)

    def _parse_s2d_component(self, elem: ET.Element, vendor: str) -> Optional[SopcComponentDescription]:
        """Parse one <S2DComponent> element into a SopcComponentDescription."""
        class_name = elem.get("classname")
        if not class_name:
            logger.warning("S2DComponent missing classname attribute")
            return None

        scd = SopcComponentDescription(
            class_name,
            group=elem.get("group", "unknown"),
            vendor=vendor,
            device=elem.get("compatDevice"),
        )

        for child in elem:
            tag = child.tag.lower()
            if tag == "compatible":
                name = child.get("name")
                if name:
                    scd.add_compatible(name)
            elif tag == "parameter":
                # dtsName takes precedence; dtsVName is prefixed with vendor
                dts_name = child.get("dtsName")
                if dts_name is None:
                    dts_v_name = child.get("dtsVName")
                    if dts_v_name is not None:
                        dts_name = f"{vendor},{dts_v_name}"
                if dts_name is not None:
                    scd.add_auto_param(
                        dts_name,
                        child.get("sopcName"),
                        child.get("forceType"),
                    )
            elif tag == "requiredparameter":
                name = child.get("name")
                value = child.get("value")
                if name is not None and value is not None:
                    scd.add_required_param(name, value)
            elif tag == "compatibleversion":
                value = child.get("value")
                if value is not None:
                    scd.add_compatible_version(value)
            elif tag == "overrideversion":
                value = child.get("value")
                if value is not None:
                    scd.add_override_version(value)
            elif tag == "transparentinterfacebridge":
                from .component import TransparentInterfaceBridge
                scd.get_transparent_bridges().append(
                    TransparentInterfaceBridge(child.get("master"), child.get("slave"))
                )
            else:
                logger.debug("S2DComponent: unknown child element %s", child.tag)

        return scd

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_scd_by_class_name(self, class_name: str) -> Optional[SopcComponentDescription]:
        """
        Find the first SCD that handles the given IP class name.
        Port of SopcComponentLib.getScdByClassName.
        """
        for scd in self._lib_components:
            if scd.is_supporting_class_name(class_name):
                return scd
        return None

    @property
    def lib_components(self) -> List[SopcComponentDescription]:
        return self._lib_components

    # ------------------------------------------------------------------
    # Component factory
    # ------------------------------------------------------------------

    def get_component_for_class(
        self, class_name: str, instance_name: str, version: str
    ) -> BasicComponent:
        """
        Return the most specific BasicComponent subclass for *class_name*.
        Port of SopcComponentLib.getComponentForClass.

        NOTE — most specialised subclasses (TSEMonolithic, SICSgdma,
        CortexA9GIC, etc.) are not yet ported. Those branches are stubs that
        fall back to a plain BasicComponent and will be replaced during the
        Component handlers phase.
        """
        from ..components.base.SICUnknown import SICUnknown as _SICUnknown
        scd = self.get_scd_by_class_name(class_name)
        if scd is None:
            scd = _SICUnknown(class_name)

        cn = class_name.lower()

        if cn in ("triple_speed_ethernet", "altera_eth_tse"):
            from ..components.altera.TSEMonolithic import TSEMonolithic
            return TSEMonolithic(class_name, instance_name, version, scd)
        elif cn == "altera_avalon_sgdma":
            from ..components.altera.SICSgdma import SICSgdma
            return SICSgdma(class_name, instance_name, version, scd)
        elif cn == "altera_avalon_epcs_flash_controller":
            from ..components.altera.SICEpcs import SICEpcs
            return SICEpcs(class_name, instance_name, version)
        elif cn == "altera_avalon_lan91c111":
            from ..components.altera.SICLan91c111 import SICLan91c111
            return SICLan91c111(class_name, instance_name, version, scd)
        elif cn == "altera_avalon_video_sync_generator":
            from ..components.altera.VIPFrameBuffer import VIPFrameBuffer
            return VIPFrameBuffer(class_name, instance_name, version, scd)
        elif cn == "altera_interface_generator":
            from ..components.altera.InterfaceGenerator import InterfaceGenerator
            return InterfaceGenerator(class_name, instance_name, version, scd)
        elif cn == "altera_arria10_interface_generator":
            from ..components.altera.A10InterfaceGenerator import A10InterfaceGenerator
            return A10InterfaceGenerator(class_name, instance_name, version, scd)
        elif cn == "intel_agilex_interface_generator":
            from ..components.altera.AgilexInterfaceGenerator import AgilexInterfaceGenerator
            return AgilexInterfaceGenerator(class_name, instance_name, version, scd)
        elif cn == "altera_irq_bridge":
            from ..components.altera.InterruptBridge import InterruptBridge
            return InterruptBridge(class_name, instance_name, version, scd)
        elif cn == "interrupt_latency_counter":
            from ..components.altera.InterruptLatencyCounter import InterruptLatencyCounter
            return InterruptLatencyCounter(class_name, instance_name, version, scd)
        elif cn in ("alt_vip_mix", "alt_vip_switch"):
            from ..components.altera.VIPMixer import VIPMixer
            return VIPMixer(class_name, instance_name, version, scd)
        elif cn in ("isp116x", "isp1362_ctrl"):
            from ..components.nxp.USBHostControllerISP1xxx import USBHostControllerISP1xxx
            return USBHostControllerISP1xxx(class_name, instance_name, version, scd)
        elif cn == "altera_generic_tristate_controller":
            from ..components.altera.GenericTristateController import GenericTristateController
            return GenericTristateController(class_name, instance_name, version)
        elif cn.endswith("arm_gic"):
            from ..components.arm.CortexA9GIC import CortexA9GIC
            return CortexA9GIC(instance_name, version)
        elif cn == "labx_ethernet":
            from ..components.labx.LabXEthernet import LabXEthernet
            return LabXEthernet(class_name, instance_name, version, scd)
        elif cn.endswith("hps_bridge_avalon"):
            from ..components.altera.MultiBridge import MultiBridge
            return MultiBridge(class_name, instance_name, version, scd)

        comp = BasicComponent(class_name, instance_name, version, scd)
        return self._cast_to_group_specific_object(comp)

    def _cast_to_group_specific_object(self, comp: BasicComponent) -> BasicComponent:
        """
        Promote a generic BasicComponent to a group-specific subclass based
        on the group field of its SCD. Port of castToGroupSpecificObject.
        """
        scd = comp.scd
        if scd is None:
            return comp

        grp = (scd.group or "").lower()

        if grp == "bridge":
            from ..components.base.SICBridge import SICBridge
            if not isinstance(comp, SICBridge):
                return SICBridge(comp)
        elif grp == "cpu":
            from ..components.base.SICCpuComponent import SICCpuComponent
            if not isinstance(comp, SICCpuComponent):
                return SICCpuComponent(comp)
        elif grp in ("clock", "clock_source"):
            from ..components.base.SICClockSource import SICClockSource
            if not isinstance(comp, SICClockSource):
                return SICClockSource(comp)
        elif grp == "clkmgr":
            from ..components.altera.hps.ClockManager import ClockManager
            if not isinstance(comp, ClockManager):
                # Java: "baum_clkmgr" → A10, anything else → V
                if comp.class_name.lower() == "baum_clkmgr":
                    from ..components.altera.hps.ClockManagerA10 import ClockManagerA10
                    return ClockManagerA10(comp)
                else:
                    from ..components.altera.hps.ClockManagerV import ClockManagerV
                    return ClockManagerV(comp)
        elif grp == "flash":
            from ..components.base.SICFlash import SICFlash
            if not isinstance(comp, SICFlash):
                return SICFlash(comp)
        elif grp == "i2c":
            from ..components.base.SICI2CMaster import SICI2CMaster
            if not isinstance(comp, SICI2CMaster):
                return SICI2CMaster(comp)
        elif grp == "mailbox":
            from ..components.base.SICMailBox import SICMailBox
            if not isinstance(comp, SICMailBox):
                return SICMailBox(comp)
        elif grp == "spi":
            from ..components.base.SICSpiMaster import SICSpiMaster
            if not isinstance(comp, SICSpiMaster):
                return SICSpiMaster(comp)
        elif grp == "ethernet":
            from ..components.base.SICEthernet import SICEthernet
            if not isinstance(comp, SICEthernet):
                return SICEthernet(comp)
        elif grp == "gpio":
            from ..components.base.SICGpioController import SICGpioController
            if not isinstance(comp, SICGpioController):
                if comp.class_name.lower() == "dw_gpio":
                    from ..components.snps.DwGpio import DwGpio
                    return DwGpio(comp)
                return SICGpioController(comp)
        elif grp == "pcie":
            from ..components.altera.PCIeCompiler import PCIeCompiler
            return PCIeCompiler.get_pcie_component(comp)

        return comp

    def final_check_on_component(self, comp: BasicComponent) -> BasicComponent:
        """
        Post-parse validation pass. Port of SopcComponentLib.finalCheckOnComponent.

        The SCDSelfDescribing / SICUnknown paths are stubs until those classes
        are ported during the Component handlers phase; the required-params
        check is fully implemented.
        """
        from ..components.base.SICUnknown import SICUnknown
        from ..components.base.SCDSelfDescribing import SCDSelfDescribing

        if SCDSelfDescribing.is_self_describing(comp) and \
                not isinstance(comp.scd, SCDSelfDescribing):
            if isinstance(comp.scd, SICUnknown) or \
                    not (comp.scd and comp.scd.is_overridden_version(comp.version)):
                comp.scd = SCDSelfDescribing(comp)
                comp = self._cast_to_group_specific_object(comp)
            else:
                logger.info(
                    "Component %s of class %s is self-describing but the "
                    "lib-version overrides version '%s'",
                    comp.instance_name, comp.class_name, comp.version,
                )
        elif isinstance(comp.scd, SICUnknown):
            logger.warning(
                "Component %s of class %s is unknown",
                comp.instance_name, comp.class_name,
            )

        # Required-params check: if the current SCD requires params this
        # component doesn't have, find a better-matching SCD.
        if comp.scd is not None:
            if not comp.scd.is_required_params_ok(comp):
                class_name = comp.class_name
                for scd in self._lib_components:
                    if scd.is_supporting_class_name(class_name):
                        if scd.is_required_params_ok(comp):
                            comp.scd = scd
                            return comp
                comp.scd = None

        return comp