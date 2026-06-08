# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Tests for all component handler classes (sopc2dts_py/components/).

Covers:
  Base handlers: SICUnknown, SCDSelfDescribing, SICBridge, SICCpuComponent,
                 SICClockSource, InterruptReceiver
  Altera:        TSEMonolithic, SICSgdma, SICEpcs, SICLan91c111,
                 InterruptBridge, InterruptLatencyCounter, MultiBridge,
                 GenericTristateController, InterfaceGenerator,
                 A10InterfaceGenerator, VIPFrameBuffer, VIPMixer,
                 PCIeCompiler, PCIeRootPort
  Altera HPS:    VirtualClockElement, SocFpgaPeripClock, SocFpgaPllClock,
                 SocFpgaGateClock, ClockManagerV, ClockManagerA10
  ARM:           CortexA9GIC
  Synopsys:      DwGpio
  LabX:          LabXEthernet
  NXP:           USBHostControllerISP1xxx
  component_lib: class-name dispatch, group dispatch
"""

import pytest
from pathlib import Path

from sopc2dts_py.model.component import BasicComponent, Interface, SopcComponentDescription
from sopc2dts_py.model.connection import Connection
from sopc2dts_py.model.enums import SystemDataType
from sopc2dts_py.model.system import AvalonSystem
from sopc2dts_py.model.component_lib import SopcComponentLib
from sopc2dts_py.model.parameter import Parameter, DataType

from sopc2dts_py.components.base.SICUnknown import SICUnknown
from sopc2dts_py.components.base.SCDSelfDescribing import SCDSelfDescribing
from sopc2dts_py.components.base.SICBridge import SICBridge, BridgeRemovalStrategy
from sopc2dts_py.components.base.SICCpuComponent import SICCpuComponent
from sopc2dts_py.components.base.SICClockSource import SICClockSource, freq_to_string


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_comp(class_name, instance_name, scd=None):
    return BasicComponent(class_name, instance_name, "1.0", scd)


def _make_intf(name, dt, is_master, owner):
    intf = Interface(name, dt, is_master, owner)
    owner.add_interface(intf)
    return intf


def _connect(master_intf, slave_intf, dt, base=0):
    conn = Connection(master_intf, slave_intf, dt, connect=True)
    if base:
        conn.conn_value = [base]
    return conn


def _comp(cn, iname, group="misc", scd=None):
    if scd is None:
        scd = SopcComponentDescription(cn, group, "altr", cn)
    return BasicComponent(cn, iname, "1.0", scd)


def _intf(name, dt, is_master, owner):
    intf = Interface(name, dt, is_master, owner)
    owner.add_interface(intf)
    return intf


def _sys(*comps):
    sys = AvalonSystem("test", "1.0", Path("test.sopcinfo"))
    for c in comps:
        sys.add_component(c)
    return sys


# ---------------------------------------------------------------------------
# SICUnknown
# ---------------------------------------------------------------------------

class TestSICUnknown:
    def test_is_scd_subclass(self):
        u = SICUnknown("my_ip")
        assert isinstance(u, SopcComponentDescription)

    def test_class_name(self):
        u = SICUnknown("my_ip")
        assert u.class_name == "my_ip"

    def test_group_unknown(self):
        u = SICUnknown("my_ip")
        assert u.group == "unknown"

    def test_vendor_unknown(self):
        u = SICUnknown("my_ip")
        assert u.vendor == "unknown"


# ---------------------------------------------------------------------------
# SCDSelfDescribing
# ---------------------------------------------------------------------------

class TestSCDSelfDescribing:
    def _make_sd_comp(self):
        comp = _make_comp("altera_foo", "foo_0")
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_VENDOR, "altr", DataType.STRING))
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_GROUP, "misc", DataType.STRING))
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_NAME, "foo", DataType.STRING))
        return comp

    def test_is_self_describing_true(self):
        comp = self._make_sd_comp()
        assert SCDSelfDescribing.is_self_describing(comp)

    def test_is_self_describing_false_no_vendor(self):
        comp = _make_comp("altera_foo", "foo_0")
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_GROUP, "misc", DataType.STRING))
        assert not SCDSelfDescribing.is_self_describing(comp)

    def test_is_self_describing_false_no_group(self):
        comp = _make_comp("altera_foo", "foo_0")
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_VENDOR, "altr", DataType.STRING))
        assert not SCDSelfDescribing.is_self_describing(comp)

    def test_builds_scd_from_params(self):
        comp = self._make_sd_comp()
        scd = SCDSelfDescribing(comp)
        assert scd.vendor == "altr"
        assert scd.group == "misc"
        assert scd.device == "foo"

    def test_device_falls_back_to_class_name(self):
        comp = _make_comp("altera_bar", "bar_0")
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_VENDOR, "altr", DataType.STRING))
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_GROUP, "misc", DataType.STRING))
        scd = SCDSelfDescribing(comp)
        assert scd.device == "altera_bar"


# ---------------------------------------------------------------------------
# SICCpuComponent
# ---------------------------------------------------------------------------

class TestSICCpuComponent:
    def test_is_basic_component_subclass(self):
        base = _make_comp("altera_nios2", "cpu_0")
        cpu = SICCpuComponent(base)
        assert isinstance(cpu, BasicComponent)

    def test_default_cpu_index(self):
        base = _make_comp("altera_nios2", "cpu_0")
        cpu = SICCpuComponent(base)
        assert cpu.cpu_index == 0

    def test_set_cpu_index(self):
        base = _make_comp("altera_nios2", "cpu_0")
        cpu = SICCpuComponent(base)
        cpu.cpu_index = 3
        assert cpu.cpu_index == 3

    def test_addr_from_conn_none_returns_cpu_index(self):
        base = _make_comp("altera_nios2", "cpu_0")
        cpu = SICCpuComponent(base)
        cpu.cpu_index = 2
        assert cpu._get_addr_from_connection(None) == [2]

    def test_addr_from_conn_uses_conn_value(self):
        base_cpu = _make_comp("altera_nios2", "cpu_0")
        cpu = SICCpuComponent(base_cpu)
        base_slave = _make_comp("altera_avalon_uart", "uart_0")
        m_intf = _make_intf("data_master", SystemDataType.MEMORY_MAPPED, True, base_cpu)
        s_intf = _make_intf("s1", SystemDataType.MEMORY_MAPPED, False, base_slave)
        conn = Connection(m_intf, s_intf, SystemDataType.MEMORY_MAPPED, connect=True)
        conn.conn_value = [0x100]
        assert cpu._get_addr_from_connection(conn) == [0x100]

    def test_is_smp_capable_same_arm(self):
        b1 = _make_comp("arm_a9", "cpu_0", SopcComponentDescription("arm_a9", "cpu"))
        b2 = _make_comp("arm_a9", "cpu_1", SopcComponentDescription("arm_a9", "cpu"))
        c1 = SICCpuComponent(b1)
        c2 = SICCpuComponent(b2)
        assert c1.is_smp_capable_with(c2)

    def test_is_smp_nios_blacklisted(self):
        b1 = _make_comp("altera_nios2", "cpu_0", SopcComponentDescription("altera_nios2", "cpu"))
        b2 = _make_comp("altera_nios2", "cpu_1", SopcComponentDescription("altera_nios2", "cpu"))
        c1 = SICCpuComponent(b1)
        c2 = SICCpuComponent(b2)
        assert not c1.is_smp_capable_with(c2)


# ---------------------------------------------------------------------------
# SICBridge - address translation
# ---------------------------------------------------------------------------

class TestSICBridgeTranslateAddress:
    def _make_bridge(self):
        scd = SopcComponentDescription("altera_avalon_pipeline_bridge", "bridge",
                                       "altr", "pipeline-bridge")
        scd.add_compatible("altr,avalon-pipeline-bridge")
        base = _make_comp("altera_avalon_pipeline_bridge", "bridge_0", scd)
        return SICBridge(base)

    def test_equal_lengths(self):
        br = self._make_bridge()
        assert br.translate_address([0x100], [0x20]) == [0x120]

    def test_master_wider(self):
        br = self._make_bridge()
        result = br.translate_address([0x1, 0x0], [0x100])
        assert result == [0x1, 0x100]

    def test_none_master(self):
        br = self._make_bridge()
        assert br.translate_address(None, [0x100]) is None

    def test_none_slave(self):
        br = self._make_bridge()
        assert br.translate_address([0x100], None) is None


# ---------------------------------------------------------------------------
# SICBridge - is_streaming_bridge / is_translating_bridge
# ---------------------------------------------------------------------------

class TestSICBridgePredicates:
    def _make_streaming_bridge(self):
        scd = SopcComponentDescription("altera_avalon_st_pipeline_bridge", "bridge")
        base = _make_comp("altera_avalon_st_pipeline_bridge", "st_bridge_0", scd)
        _make_intf("in", SystemDataType.STREAMING, False, base)
        _make_intf("out", SystemDataType.STREAMING, True, base)
        return SICBridge(base)

    def _make_mm_bridge(self):
        scd = SopcComponentDescription(
            "altera_avalon_pipeline_bridge,altera_avalon_clock_crossing",
            "bridge", "altr", "pipeline-bridge"
        )
        base = _make_comp("altera_avalon_pipeline_bridge", "bridge_0", scd)
        _make_intf("s0", SystemDataType.MEMORY_MAPPED, False, base)
        _make_intf("m0", SystemDataType.MEMORY_MAPPED, True, base)
        return SICBridge(base)

    def test_streaming_bridge_detected(self):
        br = self._make_streaming_bridge()
        assert br.is_streaming_bridge()

    def test_mm_bridge_not_streaming(self):
        br = self._make_mm_bridge()
        assert not br.is_streaming_bridge()

    def test_not_translating_when_zero_base(self):
        br = self._make_mm_bridge()
        slave_intf = br.get_interfaces(SystemDataType.MEMORY_MAPPED, False)[0]
        upstream = _make_comp("cpu_0", "cpu_0")
        m_intf = _make_intf("data_master", SystemDataType.MEMORY_MAPPED, True, upstream)
        conn = Connection(m_intf, slave_intf, SystemDataType.MEMORY_MAPPED, connect=True)
        conn.conn_value = [0x0]
        assert not br.is_translating_bridge()

    def test_translating_when_nonzero_base(self):
        br = self._make_mm_bridge()
        slave_intf = br.get_interfaces(SystemDataType.MEMORY_MAPPED, False)[0]
        upstream = _make_comp("cpu_0", "cpu_0")
        m_intf = _make_intf("data_master", SystemDataType.MEMORY_MAPPED, True, upstream)
        conn = Connection(m_intf, slave_intf, SystemDataType.MEMORY_MAPPED, connect=True)
        conn.conn_value = [0x100]
        assert br.is_translating_bridge()


# ---------------------------------------------------------------------------
# SICBridge - MM removal
# ---------------------------------------------------------------------------

class TestSICBridgeMMRemoval:
    def _build_system_with_bridge(self):
        scd_bridge = SopcComponentDescription(
            "altera_avalon_pipeline_bridge,altera_avalon_clock_crossing",
            "bridge", "altr", "pipeline-bridge",
        )
        scd_cpu = SopcComponentDescription("altera_nios2_qsys", "cpu")
        scd_uart = SopcComponentDescription("altera_avalon_uart", "misc")

        cpu = BasicComponent("altera_nios2_qsys", "cpu_0", "1.0", scd_cpu)
        bridge = BasicComponent("altera_avalon_pipeline_bridge", "bridge_0", "1.0", scd_bridge)
        uart = BasicComponent("altera_avalon_uart", "uart_0", "1.0", scd_uart)

        cpu_m = _make_intf("data_master", SystemDataType.MEMORY_MAPPED, True, cpu)
        br_s = _make_intf("s0", SystemDataType.MEMORY_MAPPED, False, bridge)
        br_m = _make_intf("m0", SystemDataType.MEMORY_MAPPED, True, bridge)
        uart_s = _make_intf("s1", SystemDataType.MEMORY_MAPPED, False, uart)
        uart_s.interface_value = [0x20]

        c1 = Connection(cpu_m, br_s, SystemDataType.MEMORY_MAPPED, connect=True)
        c1.conn_value = [0x0]
        c2 = Connection(br_m, uart_s, SystemDataType.MEMORY_MAPPED, connect=True)
        c2.conn_value = [0x1000]

        sys = AvalonSystem("test", "1.0", Path("test.sopcinfo"))
        sys._components = [cpu, bridge, uart]

        return sys, cpu, bridge, uart, cpu_m, uart_s

    def test_bridge_removed_from_system(self):
        SICBridge.set_removal_strategy(BridgeRemovalStrategy.BALANCED)
        sys, cpu, bridge, uart, cpu_m, uart_s = self._build_system_with_bridge()
        br_comp = SICBridge(bridge)
        sys._components[1] = br_comp

        result = br_comp.remove_from_system_if_possible(sys)

        assert result is True
        names = {c.instance_name for c in sys.components}
        assert "bridge_0" not in names
        assert "cpu_0" in names
        assert "uart_0" in names

    def test_bridge_removal_translates_address(self):
        SICBridge.set_removal_strategy(BridgeRemovalStrategy.BALANCED)
        sys, cpu, bridge, uart, cpu_m, uart_s = self._build_system_with_bridge()
        br_comp = SICBridge(bridge)
        sys._components[1] = br_comp

        br_comp.remove_from_system_if_possible(sys)

        assert len(cpu_m.connections) == 1
        assert cpu_m.connections[0].conn_value == [0x1000]
        assert cpu_m.connections[0].slave_interface is uart_s

    def test_bridge_not_removed_strategy_none(self):
        SICBridge.set_removal_strategy(BridgeRemovalStrategy.NONE)
        sys, cpu, bridge, uart, cpu_m, uart_s = self._build_system_with_bridge()
        br_comp = SICBridge(bridge)
        sys._components[1] = br_comp

        result = br_comp.remove_from_system_if_possible(sys)

        assert result is False
        assert len(sys.components) == 3

    def test_bridge_removed_strategy_all(self):
        SICBridge.set_removal_strategy(BridgeRemovalStrategy.ALL)
        sys, cpu, bridge, uart, cpu_m, uart_s = self._build_system_with_bridge()
        scd_other = SopcComponentDescription(
            "altera_avalon_some_other_bridge", "bridge", "altr", "other-bridge"
        )
        other_bridge = BasicComponent(
            "altera_avalon_some_other_bridge", "bridge_0", "1.0", scd_other
        )
        other_bridge._interfaces = bridge._interfaces
        for intf in other_bridge._interfaces:
            intf.owner = other_bridge
        br_comp = SICBridge(other_bridge)
        sys._components[1] = br_comp

        result = br_comp.remove_from_system_if_possible(sys)
        assert result is True

    def test_reset_strategy_after_tests(self):
        SICBridge.set_removal_strategy(BridgeRemovalStrategy.BALANCED)


# ---------------------------------------------------------------------------
# SopcComponentLib - base group dispatch
# ---------------------------------------------------------------------------

class TestComponentLibDispatch:
    def _lib_with_scd(self, group, class_name):
        lib = SopcComponentLib()
        scd = SopcComponentDescription(class_name, group, "altr", "test")
        lib._lib_components.append(scd)
        return lib

    def test_bridge_group_returns_sicbridge(self):
        lib = self._lib_with_scd("bridge", "altera_avalon_pipeline_bridge")
        comp = lib.get_component_for_class("altera_avalon_pipeline_bridge", "br_0", "1.0")
        assert isinstance(comp, SICBridge)

    def test_cpu_group_returns_cpucomponent(self):
        lib = self._lib_with_scd("cpu", "altera_nios2_qsys")
        comp = lib.get_component_for_class("altera_nios2_qsys", "cpu_0", "1.0")
        assert isinstance(comp, SICCpuComponent)

    def test_clock_group_returns_clocksource(self):
        lib = self._lib_with_scd("clock", "altera_clock_bridge")
        comp = lib.get_component_for_class("altera_clock_bridge", "clk_0", "1.0")
        assert isinstance(comp, SICClockSource)

    def test_unknown_class_gets_sicunknown_scd(self):
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("totally_unknown_ip", "foo_0", "1.0")
        assert isinstance(comp.scd, SICUnknown)

    def test_self_describing_upgrades_scd(self):
        lib = SopcComponentLib()
        comp = BasicComponent("custom_ip", "custom_0", "1.0", SICUnknown("custom_ip"))
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_VENDOR, "altr", DataType.STRING))
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_GROUP, "misc", DataType.STRING))

        result = lib.final_check_on_component(comp)
        assert isinstance(result.scd, SCDSelfDescribing)
        assert result.scd.vendor == "altr"


# ---------------------------------------------------------------------------
# freq_to_string
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("freq,expected_suffix", [
    (50_000_000, "MHz"),
    (1_500_000_000, "GHz"),
    (100_000, "kHz"),
    (500, "Hz"),
])
def test_freq_to_string(freq, expected_suffix):
    result = freq_to_string(freq)
    assert expected_suffix in result


# ---------------------------------------------------------------------------
# component_lib dispatch - class-name routes
# ---------------------------------------------------------------------------

class TestComponentLibClassNameDispatch:
    def test_arm_gic(self):
        from sopc2dts_py.components.arm.CortexA9GIC import CortexA9GIC
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("cortex_a9_arm_gic", "gic_0", "1.0")
        assert isinstance(comp, CortexA9GIC)

    def test_arm_gic_variant(self):
        from sopc2dts_py.components.arm.CortexA9GIC import CortexA9GIC
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("arm_gic", "gic_0", "1.0")
        assert isinstance(comp, CortexA9GIC)

    def test_tse_monolithic(self):
        from sopc2dts_py.components.altera.TSEMonolithic import TSEMonolithic
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("triple_speed_ethernet", "tse_0", "14.0")
        assert isinstance(comp, TSEMonolithic)

    def test_tse_altera_variant(self):
        from sopc2dts_py.components.altera.TSEMonolithic import TSEMonolithic
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("altera_eth_tse", "tse_0", "14.0")
        assert isinstance(comp, TSEMonolithic)

    def test_sgdma(self):
        from sopc2dts_py.components.altera.SICSgdma import SICSgdma
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("altera_avalon_sgdma", "sgdma_0", "14.0")
        assert isinstance(comp, SICSgdma)

    def test_epcs(self):
        from sopc2dts_py.components.altera.SICEpcs import SICEpcs
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("altera_avalon_epcs_flash_controller", "epcs_0", "14.0")
        assert isinstance(comp, SICEpcs)

    def test_lan91c111(self):
        from sopc2dts_py.components.altera.SICLan91c111 import SICLan91c111
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("altera_avalon_lan91c111", "eth_0", "1.0")
        assert isinstance(comp, SICLan91c111)

    def test_irq_bridge(self):
        from sopc2dts_py.components.altera.InterruptBridge import InterruptBridge
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("altera_irq_bridge", "irq_0", "1.0")
        assert isinstance(comp, InterruptBridge)

    def test_interrupt_latency_counter(self):
        from sopc2dts_py.components.altera.InterruptLatencyCounter import InterruptLatencyCounter
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("interrupt_latency_counter", "ilc_0", "1.0")
        assert isinstance(comp, InterruptLatencyCounter)

    def test_vip_mix(self):
        from sopc2dts_py.components.altera.VIPMixer import VIPMixer
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("alt_vip_mix", "vip_0", "1.0")
        assert isinstance(comp, VIPMixer)

    def test_vip_switch(self):
        from sopc2dts_py.components.altera.VIPMixer import VIPMixer
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("alt_vip_switch", "vip_0", "1.0")
        assert isinstance(comp, VIPMixer)

    def test_usb_isp116x(self):
        from sopc2dts_py.components.nxp.USBHostControllerISP1xxx import USBHostControllerISP1xxx
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("isp116x", "usb_0", "1.0")
        assert isinstance(comp, USBHostControllerISP1xxx)

    def test_usb_isp1362(self):
        from sopc2dts_py.components.nxp.USBHostControllerISP1xxx import USBHostControllerISP1xxx
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("ISP1362_CTRL", "usb_0", "1.0")
        assert isinstance(comp, USBHostControllerISP1xxx)

    def test_generic_tristate(self):
        from sopc2dts_py.components.altera.GenericTristateController import GenericTristateController
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("altera_generic_tristate_controller", "tc_0", "1.0")
        assert isinstance(comp, GenericTristateController)

    def test_labx_ethernet(self):
        from sopc2dts_py.components.labx.LabXEthernet import LabXEthernet
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("labx_ethernet", "eth_0", "1.0")
        assert isinstance(comp, LabXEthernet)

    def test_hps_bridge_avalon(self):
        from sopc2dts_py.components.altera.MultiBridge import MultiBridge
        lib = SopcComponentLib()
        comp = lib.get_component_for_class("hps_bridge_avalon", "hps_br_0", "1.0")
        assert isinstance(comp, MultiBridge)


# ---------------------------------------------------------------------------
# component_lib dispatch - group routes
# ---------------------------------------------------------------------------

class TestComponentLibGroupDispatch:
    def test_clkmgr_v_for_regular(self):
        from sopc2dts_py.components.altera.hps.ClockManagerV import ClockManagerV
        lib = SopcComponentLib()
        scd = SopcComponentDescription("hps_clk_mgr", "clkmgr", "altr", None)
        lib._lib_components.append(scd)
        comp = lib.get_component_for_class("hps_clk_mgr", "clk_0", "14.0")
        assert isinstance(comp, ClockManagerV)

    def test_clkmgr_a10_for_baum(self):
        from sopc2dts_py.components.altera.hps.ClockManagerA10 import ClockManagerA10
        lib = SopcComponentLib()
        scd = SopcComponentDescription("baum_clkmgr", "clkmgr", "altr", None)
        lib._lib_components.append(scd)
        comp = lib.get_component_for_class("baum_clkmgr", "clk_0", "14.0")
        assert isinstance(comp, ClockManagerA10)

    def test_dw_gpio_dispatch(self):
        from sopc2dts_py.components.snps.DwGpio import DwGpio
        lib = SopcComponentLib()
        scd = SopcComponentDescription("dw_gpio", "gpio", "snps", "gpio")
        lib._lib_components.append(scd)
        comp = lib.get_component_for_class("dw_gpio", "gpio_0", "1.0")
        assert isinstance(comp, DwGpio)

    def test_pcie_dispatches_via_group(self):
        lib = SopcComponentLib()
        scd = SopcComponentDescription("altera_pcie_a10_hip", "pcie", "altr", "pcie-root-port")
        lib._lib_components.append(scd)
        comp = lib.get_component_for_class("altera_pcie_a10_hip", "pcie_0", "14.0")
        from sopc2dts_py.components.altera.PCIeRootPort import PCIeRootPort
        assert isinstance(comp, PCIeRootPort)


# ---------------------------------------------------------------------------
# InterruptReceiver base
# ---------------------------------------------------------------------------

class TestInterruptReceiver:
    def _make_ir(self):
        from sopc2dts_py.components.base.InterruptReceiver import InterruptReceiver

        class ConcreteIR(InterruptReceiver):
            pass

        scd = SopcComponentDescription("altera_irq_bridge", "ignore", "altr", None)
        ir = ConcreteIR("altera_irq_bridge", "irq_0", "1.0", scd)
        irq_m = Interface("irq_master", SystemDataType.INTERRUPT, True, ir)
        ir.add_interface(irq_m)
        return ir, irq_m

    def test_remove_disconnects_irq_connections(self):
        ir, irq_m = self._make_ir()
        sender = _comp("altera_uart", "uart_0")
        irq_s = _intf("irq", SystemDataType.INTERRUPT, False, sender)
        conn = Connection(irq_m, irq_s, SystemDataType.INTERRUPT, connect=True)
        conn.conn_value = [0]

        sys = _sys(ir, sender)
        result = ir.remove_from_system_if_possible(sys)
        assert result is True
        assert len(irq_m.connections) == 0

    def test_remove_twice_returns_false(self):
        ir, irq_m = self._make_ir()
        sys = _sys(ir)
        ir.remove_from_system_if_possible(sys)
        assert ir.remove_from_system_if_possible(sys) is False


# ---------------------------------------------------------------------------
# CortexA9GIC - IRQ renumbering
# ---------------------------------------------------------------------------

class TestCortexA9GIC:
    def test_irqs_renumbered_on_remove(self):
        from sopc2dts_py.components.arm.CortexA9GIC import CortexA9GIC, GIC_IRQ_CLASS_SPI, GIC_IRQ_TYPE_HIGH

        gic = CortexA9GIC("gic_0", "1.0")
        irq_m = Interface("irq_master", SystemDataType.INTERRUPT, True, gic)
        gic.add_interface(irq_m)

        slave = _comp("altera_uart", "uart_0")
        irq_s = _intf("irq", SystemDataType.INTERRUPT, False, slave)

        conn = Connection(irq_m, irq_s, SystemDataType.INTERRUPT, connect=True)
        conn.conn_value = [0, 0, 42]

        sys = _sys(gic, slave)
        result = gic.remove_from_system_if_possible(sys)

        assert result is False
        assert conn.conn_value == [GIC_IRQ_CLASS_SPI, 42, GIC_IRQ_TYPE_HIGH]

    def test_remove_called_twice_is_idempotent(self):
        from sopc2dts_py.components.arm.CortexA9GIC import CortexA9GIC

        gic = CortexA9GIC("gic_0", "1.0")
        irq_m = Interface("irq_master", SystemDataType.INTERRUPT, True, gic)
        gic.add_interface(irq_m)
        slave = _comp("altera_uart", "uart_0")
        irq_s = _intf("irq", SystemDataType.INTERRUPT, False, slave)
        conn = Connection(irq_m, irq_s, SystemDataType.INTERRUPT, connect=True)
        conn.conn_value = [0, 0, 7]

        sys = _sys(gic, slave)
        gic.remove_from_system_if_possible(sys)
        saved = list(conn.conn_value)
        gic.remove_from_system_if_possible(sys)
        assert conn.conn_value == saved


# ---------------------------------------------------------------------------
# SICSgdma
# ---------------------------------------------------------------------------

class TestSICSgdma:
    def test_constructs_without_error(self):
        from sopc2dts_py.components.altera.SICSgdma import SICSgdma
        scd = SopcComponentDescription("altera_avalon_sgdma", "dma", "altr", "sgdma")
        sgdma = SICSgdma("altera_avalon_sgdma", "sgdma_0", "14.0", scd)
        assert isinstance(sgdma, BasicComponent)
        # transferMode absent by default
        assert sgdma.get_param_val_by_name("transferMode") is None

    def test_param_accessible(self):
        from sopc2dts_py.components.altera.SICSgdma import SICSgdma
        scd = SopcComponentDescription("altera_avalon_sgdma", "dma", "altr", "sgdma")
        sgdma = SICSgdma("altera_avalon_sgdma", "sgdma_0", "14.0", scd)
        sgdma.add_param(Parameter("embeddedsw.CMacro.DESCRIPTOR_MEMORY", "SGDMA", DataType.STRING))
        assert sgdma.get_param_val_by_name("embeddedsw.CMacro.DESCRIPTOR_MEMORY") == "SGDMA"


# ---------------------------------------------------------------------------
# VIPFrameBuffer
# ---------------------------------------------------------------------------

class TestVIPFrameBuffer:
    def test_dma_engine_none_initially(self):
        from sopc2dts_py.components.altera.VIPFrameBuffer import VIPFrameBuffer
        scd = SopcComponentDescription("altera_avalon_video_sync_generator", "vip", "altr", None)
        vfb = VIPFrameBuffer("altera_avalon_video_sync_generator", "vfb_0", "1.0", scd)
        assert vfb._dma_engine is None

    def test_remove_finds_sgdma_on_in_interface(self):
        from sopc2dts_py.components.altera.VIPFrameBuffer import VIPFrameBuffer
        from sopc2dts_py.components.altera.SICSgdma import SICSgdma

        scd_vfb = SopcComponentDescription("altera_avalon_video_sync_generator", "vip", "altr", None)
        scd_sgdma = SopcComponentDescription("altera_avalon_sgdma", "dma", "altr", "sgdma")
        vfb = VIPFrameBuffer("altera_avalon_video_sync_generator", "vfb_0", "1.0", scd_vfb)
        sgdma = SICSgdma("altera_avalon_sgdma", "sgdma_0", "14.0", scd_sgdma)

        sgdma_out = _intf("out", SystemDataType.STREAMING, True, sgdma)
        vfb_in = _intf("in", SystemDataType.STREAMING, False, vfb)
        Connection(sgdma_out, vfb_in, SystemDataType.STREAMING, connect=True)

        sys = _sys(vfb, sgdma)
        vfb.remove_from_system_if_possible(sys)
        assert vfb._dma_engine is sgdma


# ---------------------------------------------------------------------------
# VIPMixer
# ---------------------------------------------------------------------------

class TestVIPMixer:
    def test_remove_cross_connects_streams(self):
        from sopc2dts_py.components.altera.VIPMixer import VIPMixer

        scd = SopcComponentDescription("alt_vip_mix", "vip-mix", "altr", None)
        mixer = VIPMixer("alt_vip_mix", "mixer_0", "1.0", scd)

        # VIPMixer looks for its master output interface named "dout"
        in0 = _intf("in0", SystemDataType.STREAMING, False, mixer)
        in1 = _intf("in1", SystemDataType.STREAMING, False, mixer)
        dout = _intf("dout", SystemDataType.STREAMING, True, mixer)

        src0 = _comp("src", "src_0")
        src1 = _comp("src", "src_1")
        s0_out = _intf("out", SystemDataType.STREAMING, True, src0)
        s1_out = _intf("out", SystemDataType.STREAMING, True, src1)
        Connection(s0_out, in0, SystemDataType.STREAMING, connect=True)
        Connection(s1_out, in1, SystemDataType.STREAMING, connect=True)

        sink = _comp("sink", "sink_0")
        sink_in = _intf("in", SystemDataType.STREAMING, False, sink)
        Connection(dout, sink_in, SystemDataType.STREAMING, connect=True)

        sys = _sys(mixer, src0, src1, sink)
        mixer.remove_from_system_if_possible(sys)

        assert any(c.slave_interface is sink_in for c in s0_out.connections)
        assert any(c.slave_interface is sink_in for c in s1_out.connections)


# ---------------------------------------------------------------------------
# PCIeCompiler / PCIeRootPort
# ---------------------------------------------------------------------------

class TestPCIeCompiler:
    def test_returns_root_port_for_pcie_device(self):
        from sopc2dts_py.components.altera.PCIeCompiler import PCIeCompiler
        from sopc2dts_py.components.altera.PCIeRootPort import PCIeRootPort

        scd = SopcComponentDescription("altera_pcie_a10_hip", "pcie", "altr", "pcie-root-port")
        bc = _comp("altera_pcie_a10_hip", "pcie_0", scd=scd)
        result = PCIeCompiler.get_pcie_component(bc)
        assert isinstance(result, PCIeRootPort)

    def test_returns_basic_for_non_root_port(self):
        from sopc2dts_py.components.altera.PCIeCompiler import PCIeCompiler
        from sopc2dts_py.components.altera.PCIeRootPort import PCIeRootPort

        scd = SopcComponentDescription("altera_pcie_a10_hip", "pcie", "altr", "pcie-endpoint")
        bc = _comp("altera_pcie_a10_hip", "pcie_0", scd=scd)
        result = PCIeCompiler.get_pcie_component(bc)
        assert not isinstance(result, PCIeRootPort)


# ---------------------------------------------------------------------------
# HPS clock tree - VirtualClockElement
# ---------------------------------------------------------------------------

class TestVirtualClockElement:
    def test_has_mm_slave_and_clock_output(self):
        from sopc2dts_py.components.altera.hps.VirtualClockElement import VirtualClockElement

        class ConcreteVCE(VirtualClockElement):
            def to_dt_node(self, bi, conn):
                raise NotImplementedError

        scd = SopcComponentDescription("test_vce", "clock", "altr", None)
        vce = ConcreteVCE("test_vce", "vce_0", "1.0", scd)

        assert vce.get_reg_interface(False) is not None
        assert vce.get_clock_interface(True) is not None

    def test_reg_offset_stored(self):
        from sopc2dts_py.components.altera.hps.SocFpgaPeripClock import SocFpgaPeripClock

        scd = SopcComponentDescription("socfpga-perip-clk", "clock", "altr", None)
        pclk = SocFpgaPeripClock("socfpga-perip-clk", "mpuclk", "1.0", scd, reg=0x08)
        assert pclk.reg_offset == 0x08

    def test_add_clock_input_creates_interface(self):
        from sopc2dts_py.components.altera.hps.SocFpgaPeripClock import SocFpgaPeripClock
        from sopc2dts_py.components.altera.hps.SocFpgaPllClock import SocFpgaPllClock

        scd_pll = SopcComponentDescription("socfpga-pll", "clock", "altr", None)
        scd_pclk = SopcComponentDescription("socfpga-perip-clk", "clock", "altr", None)

        pll = SocFpgaPllClock("socfpga-pll", "main_pll", "1.0", scd_pll)
        pclk = SocFpgaPeripClock("socfpga-perip-clk", "mpuclk", "1.0", scd_pclk, reg=0x08)

        pclk.add_clock_input(pll.get_clock_interface(True))
        assert len(pclk.get_interfaces(SystemDataType.CLOCK, False)) == 1


# ---------------------------------------------------------------------------
# HPS clock tree - ClockManagerV
# ---------------------------------------------------------------------------

class TestClockManagerV:
    def _build_hps_system(self):
        from sopc2dts_py.components.altera.hps.ClockManagerV import ClockManagerV

        scd_hps = SopcComponentDescription("altera_hps", "ignore", "altr", None)
        hps = _comp("altera_hps", "hps_0", scd=scd_hps)

        scd_clk = SopcComponentDescription("hps_clk_mgr", "clkmgr", "altr", None)
        bc_clk = _comp("hps_clk_mgr", "hps_0_clk_0", scd=scd_clk)

        clk_mgr = ClockManagerV(bc_clk)
        sys = _sys(hps, clk_mgr)
        return sys, clk_mgr

    def test_first_supported_version(self):
        from sopc2dts_py.components.altera.hps.ClockManagerV import ClockManagerV
        scd = SopcComponentDescription("hps_clk_mgr", "clkmgr", "altr", None)
        bc = _comp("hps_clk_mgr", "hps_0_clk_0", scd=scd)
        assert ClockManagerV(bc).getFirstSupportedVersion() == "14.0"

    def test_remove_creates_virtual_components(self):
        sys, clk_mgr = self._build_hps_system()
        clk_mgr.version = "14.0"
        assert clk_mgr.remove_from_system_if_possible(sys) is True
        assert len(sys.components) > 2

    def test_remove_idempotent(self):
        sys, clk_mgr = self._build_hps_system()
        clk_mgr.version = "14.0"
        clk_mgr.remove_from_system_if_possible(sys)
        count = len(sys.components)
        assert clk_mgr.remove_from_system_if_possible(sys) is False
        assert len(sys.components) == count

    def test_remove_skipped_for_old_version(self):
        sys, clk_mgr = self._build_hps_system()
        clk_mgr.version = "13.0"
        assert clk_mgr.remove_from_system_if_possible(sys) is False
        assert len(sys.components) == 2

    def test_pll_names_created(self):
        sys, clk_mgr = self._build_hps_system()
        clk_mgr.version = "14.0"
        clk_mgr.remove_from_system_if_possible(sys)
        names = {c.instance_name for c in sys.components}
        assert {"main_pll", "periph_pll", "sdram_pll"} <= names

    def test_gate_clock_names_created(self):
        sys, clk_mgr = self._build_hps_system()
        clk_mgr.version = "14.0"
        clk_mgr.remove_from_system_if_possible(sys)
        names = {c.instance_name for c in sys.components}
        assert "l4_main_clk" in names
        assert "h2f_user0_clock" in names


# ---------------------------------------------------------------------------
# HPS clock tree - ClockManagerA10
# ---------------------------------------------------------------------------

class TestClockManagerA10:
    def _build_a10_system(self):
        from sopc2dts_py.components.altera.hps.ClockManagerA10 import ClockManagerA10

        scd_hps = SopcComponentDescription("altera_arria10_hps", "ignore", "altr", None)
        hps = _comp("altera_arria10_hps", "hps_0", scd=scd_hps)

        scd_clk = SopcComponentDescription("baum_clkmgr", "clkmgr", "altr", None)
        bc_clk = _comp("baum_clkmgr", "hps_0_clk_0", scd=scd_clk)

        clk_mgr = ClockManagerA10(bc_clk)
        sys = _sys(hps, clk_mgr)
        return sys, clk_mgr

    def test_first_supported_version(self):
        from sopc2dts_py.components.altera.hps.ClockManagerA10 import ClockManagerA10
        scd = SopcComponentDescription("baum_clkmgr", "clkmgr", "altr", None)
        bc = _comp("baum_clkmgr", "hps_0_clk_0", scd=scd)
        assert ClockManagerA10(bc).getFirstSupportedVersion() == "14.0"

    def test_remove_creates_a10_plls(self):
        sys, clk_mgr = self._build_a10_system()
        clk_mgr.version = "14.0"
        clk_mgr.remove_from_system_if_possible(sys)
        names = {c.instance_name for c in sys.components}
        assert {"main_pll", "periph_pll"} <= names

    def test_a10_gate_clocks_created(self):
        sys, clk_mgr = self._build_a10_system()
        clk_mgr.version = "14.0"
        clk_mgr.remove_from_system_if_possible(sys)
        names = {c.instance_name for c in sys.components}
        assert "emac0_clk" in names
        assert "l4_main_clk" in names


# ---------------------------------------------------------------------------
# DwGpio
# ---------------------------------------------------------------------------

class TestDwGpio:
    def test_copy_constructor(self):
        from sopc2dts_py.components.snps.DwGpio import DwGpio
        from sopc2dts_py.components.base.SICGpioController import SICGpioController

        scd = SopcComponentDescription("dw_gpio", "gpio", "snps", "gpio")
        bc = _comp("dw_gpio", "gpio_0", scd=scd)
        gpio = DwGpio(bc)
        assert isinstance(gpio, SICGpioController)
        assert gpio.instance_name == "gpio_0"

    def test_regular_constructor(self):
        from sopc2dts_py.components.snps.DwGpio import DwGpio

        scd = SopcComponentDescription("dw_gpio", "gpio", "snps", "gpio")
        gpio = DwGpio("dw_gpio", "gpio_0", "1.0", scd)
        assert gpio.class_name == "dw_gpio"


# ---------------------------------------------------------------------------
# LabXEthernet
# ---------------------------------------------------------------------------

class TestLabXEthernet:
    def test_constructor(self):
        from sopc2dts_py.components.labx.LabXEthernet import LabXEthernet
        from sopc2dts_py.components.base.SICEthernet import SICEthernet

        scd = SopcComponentDescription("labx_ethernet", "ethernet", "labx", "labx_ethernet")
        eth = LabXEthernet("labx_ethernet", "eth_0", "1.0", scd)
        assert isinstance(eth, SICEthernet)

    def test_phy_mode_unknown_without_mac(self):
        from sopc2dts_py.components.labx.LabXEthernet import LabXEthernet

        scd = SopcComponentDescription("labx_ethernet", "ethernet", "labx", "labx_ethernet")
        eth = LabXEthernet("labx_ethernet", "eth_0", "1.0", scd)
        assert eth._get_phy_mode_string() == "UNKNOWN"

    def test_max_frame_size_is_vlan(self):
        from sopc2dts_py.components.labx.LabXEthernet import LabXEthernet

        scd = SopcComponentDescription("labx_ethernet", "ethernet", "labx", "labx_ethernet")
        eth = LabXEthernet("labx_ethernet", "eth_0", "1.0", scd)
        assert eth._get_max_frame_size() == 1522


# ---------------------------------------------------------------------------
# USBHostControllerISP1xxx
# ---------------------------------------------------------------------------

class TestUSBHostControllerISP1xxx:
    def test_constructor(self):
        from sopc2dts_py.components.nxp.USBHostControllerISP1xxx import USBHostControllerISP1xxx

        scd = SopcComponentDescription("isp116x", "isp1161a", "nxp", "isp1161a")
        usb = USBHostControllerISP1xxx("isp116x", "usb_0", "1.0", scd)
        assert usb.class_name == "isp116x"
        assert isinstance(usb, BasicComponent)


# ---------------------------------------------------------------------------
# system.add_system_component
# ---------------------------------------------------------------------------

class TestSystemAddSystemComponent:
    def test_add_system_component_appends(self):
        sys = _sys()
        c1 = _comp("foo", "foo_0")
        c2 = _comp("bar", "bar_0")
        sys.add_system_component(c1)
        sys.add_system_component(c2)
        assert c1 in sys.components
        assert c2 in sys.components
        assert len(sys.components) == 2
