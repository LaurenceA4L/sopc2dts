# sopc2dts - Devicetree generation for Altera systems
#
# Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for component handler classes (sopc2dts_py/components/base/)."""

import pytest

from sopc2dts_py.model.component import BasicComponent, Interface, SopcComponentDescription
from sopc2dts_py.model.connection import Connection
from sopc2dts_py.model.enums import SystemDataType
from sopc2dts_py.model.system import AvalonSystem
from sopc2dts_py.model.component_lib import SopcComponentLib

from sopc2dts_py.components.base.SICUnknown import SICUnknown
from sopc2dts_py.components.base.SCDSelfDescribing import SCDSelfDescribing
from sopc2dts_py.components.base.SICBridge import SICBridge, BridgeRemovalStrategy
from sopc2dts_py.components.base.SICCpuComponent import SICCpuComponent
from sopc2dts_py.components.base.SICClockSource import SICClockSource, freq_to_string


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_comp(class_name: str, instance_name: str, scd=None) -> BasicComponent:
    return BasicComponent(class_name, instance_name, "1.0", scd)


def _make_intf(name: str, dt: SystemDataType, is_master: bool,
               owner: BasicComponent) -> Interface:
    intf = Interface(name, dt, is_master, owner)
    owner.add_interface(intf)
    return intf


def _connect(master_intf: Interface, slave_intf: Interface,
             dt: SystemDataType, base: int = 0) -> Connection:
    conn = Connection(master_intf, slave_intf, dt, connect=True)
    if base:
        conn.conn_value = [base]
    return conn


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
        from sopc2dts_py.model.parameter import Parameter, DataType
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_VENDOR, "altr", DataType.STRING))
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_GROUP, "misc", DataType.STRING))
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_NAME, "foo", DataType.STRING))
        return comp

    def test_is_self_describing_true(self):
        comp = self._make_sd_comp()
        assert SCDSelfDescribing.is_self_describing(comp)

    def test_is_self_describing_false_no_vendor(self):
        comp = _make_comp("altera_foo", "foo_0")
        from sopc2dts_py.model.parameter import Parameter, DataType
        comp.add_param(Parameter(BasicComponent.EMBSW_DTS_GROUP, "misc", DataType.STRING))
        assert not SCDSelfDescribing.is_self_describing(comp)

    def test_is_self_describing_false_no_group(self):
        comp = _make_comp("altera_foo", "foo_0")
        from sopc2dts_py.model.parameter import Parameter, DataType
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
        from sopc2dts_py.model.parameter import Parameter, DataType
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
        assert cpu._get_addr_from_conn(None) == [2]

    def test_addr_from_conn_uses_conn_value(self):
        base_cpu = _make_comp("altera_nios2", "cpu_0")
        cpu = SICCpuComponent(base_cpu)
        base_slave = _make_comp("altera_avalon_uart", "uart_0")
        m_intf = _make_intf("data_master", SystemDataType.MEMORY_MAPPED, True, base_cpu)
        s_intf = _make_intf("s1", SystemDataType.MEMORY_MAPPED, False, base_slave)
        conn = Connection(m_intf, s_intf, SystemDataType.MEMORY_MAPPED, connect=True)
        conn.conn_value = [0x100]
        assert cpu._get_addr_from_conn(conn) == [0x100]

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
# SICBridge — address translation
# ---------------------------------------------------------------------------

class TestSICBridgeTranslateAddress:
    def _make_bridge(self) -> SICBridge:
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
        # 2-cell master, 1-cell slave
        result = br.translate_address([0x1, 0x0], [0x100])
        assert result == [0x1, 0x100]

    def test_none_master(self):
        br = self._make_bridge()
        assert br.translate_address(None, [0x100]) is None

    def test_none_slave(self):
        br = self._make_bridge()
        assert br.translate_address([0x100], None) is None


# ---------------------------------------------------------------------------
# SICBridge — is_streaming_bridge / is_translating_bridge
# ---------------------------------------------------------------------------

class TestSICBridgePredicates:
    def _make_streaming_bridge(self) -> SICBridge:
        scd = SopcComponentDescription("altera_avalon_st_pipeline_bridge", "bridge")
        base = _make_comp("altera_avalon_st_pipeline_bridge", "st_bridge_0", scd)
        _make_intf("in", SystemDataType.STREAMING, False, base)
        _make_intf("out", SystemDataType.STREAMING, True, base)
        return SICBridge(base)

    def _make_mm_bridge(self) -> SICBridge:
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
# SICBridge — MM removal (BALANCED strategy, non-translating pipeline bridge)
# ---------------------------------------------------------------------------

class TestSICBridgeMMRemoval:
    def _build_system_with_bridge(self):
        """
        CPU -> (avalon) -> bridge -> (avalon) -> uart

        Bridge is altera_avalon_pipeline_bridge (BALANCED removes it).
        After removal: CPU -> uart with translated address.
        """
        from pathlib import Path

        scd_bridge = SopcComponentDescription(
            "altera_avalon_pipeline_bridge,altera_avalon_clock_crossing",
            "bridge", "altr", "pipeline-bridge",
        )
        scd_cpu = SopcComponentDescription("altera_nios2_qsys", "cpu")
        scd_uart = SopcComponentDescription("altera_avalon_uart", "misc")

        cpu = BasicComponent("altera_nios2_qsys", "cpu_0", "1.0", scd_cpu)
        bridge = BasicComponent(
            "altera_avalon_pipeline_bridge", "bridge_0", "1.0", scd_bridge
        )
        uart = BasicComponent("altera_avalon_uart", "uart_0", "1.0", scd_uart)

        # Interfaces
        cpu_m = _make_intf("data_master", SystemDataType.MEMORY_MAPPED, True, cpu)
        br_s = _make_intf("s0", SystemDataType.MEMORY_MAPPED, False, bridge)
        br_m = _make_intf("m0", SystemDataType.MEMORY_MAPPED, True, bridge)
        uart_s = _make_intf("s1", SystemDataType.MEMORY_MAPPED, False, uart)
        uart_s.interface_value = [0x20]  # size

        # cpu_m -> br_s: window base 0x0 (non-translating bridge); br_m -> uart_s @ 0x1000
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

        # cpu_m should now connect directly to uart_s at 0x0 + 0x1000 = 0x1000
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
        # Use a non-pipeline bridge that BALANCED would skip
        from sopc2dts_py.model.component import SopcComponentDescription
        scd_other = SopcComponentDescription(
            "altera_avalon_some_other_bridge", "bridge", "altr", "other-bridge"
        )
        other_bridge = BasicComponent(
            "altera_avalon_some_other_bridge", "bridge_0", "1.0", scd_other
        )
        # Copy the interfaces from the original bridge
        other_bridge._interfaces = bridge._interfaces
        for intf in other_bridge._interfaces:
            intf.owner = other_bridge
        br_comp = SICBridge(other_bridge)
        sys._components[1] = br_comp

        result = br_comp.remove_from_system_if_possible(sys)
        assert result is True

    def test_reset_strategy_after_tests(self):
        # Reset to BALANCED so other tests are unaffected
        SICBridge.set_removal_strategy(BridgeRemovalStrategy.BALANCED)


# ---------------------------------------------------------------------------
# SopcComponentLib group dispatch
# ---------------------------------------------------------------------------

class TestComponentLibDispatch:
    def _lib_with_scd(self, group: str, class_name: str) -> SopcComponentLib:
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
        lib = SopcComponentLib()  # empty - no lib loaded
        comp = lib.get_component_for_class("totally_unknown_ip", "foo_0", "1.0")
        assert isinstance(comp.scd, SICUnknown)

    def test_self_describing_upgrades_scd(self):
        """Component with embeddedsw.dts.* params gets SCDSelfDescribing in final_check."""
        from sopc2dts_py.model.parameter import Parameter, DataType

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
