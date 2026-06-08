# sopc2dts - Devicetree generation for Altera systems
#
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# Tests for Phase 2: BasicComponent.to_dt_node() and generator layer.

"""
test_generators.py — unit tests for:

  - BasicComponent helper methods (to_dt_node, get_clocks_property, etc.)
  - AbstractSopcGenerator (definenify, get_small_copyright_notice, get_pov_component)
  - DTGenerator (get_dt_output — smoke + structure)
  - DTSGenerator2 (get_text_output — smoke)
  - GeneratorFactory (create_generator_for)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import pytest

from sopc2dts_py.model.component import (
    BasicComponent, Interface, SopcComponentDescription,
)
from sopc2dts_py.model.connection import Connection
from sopc2dts_py.model.devicetree import (
    DTNode, DTProperty, DTPropNumVal, DTPropHexNumVal,
    DTPropStringVal, DTPropPHandleVal,
)
from sopc2dts_py.model.enums import SystemDataType, ParameterAction
from sopc2dts_py.model.parameter import Parameter, DataType
from sopc2dts_py.model.system import AvalonSystem
from sopc2dts_py.model.boardinfo import BoardInfo, SortType, PovType, AltrStyle
from sopc2dts_py.generators.AbstractSopcGenerator import AbstractSopcGenerator
from sopc2dts_py.generators.DTGenerator import DTGenerator
from sopc2dts_py.generators.DTSGenerator2 import DTSGenerator2
from sopc2dts_py.generators.GeneratorFactory import GeneratorFactory, GeneratorType


# ===========================================================================
# Helpers to build minimal test fixtures
# ===========================================================================

def _make_scd(
    class_name: str = "test_ip",
    group: str = "unknown",
    vendor: str = "altr",
    device: str = "test-device",
) -> SopcComponentDescription:
    scd = SopcComponentDescription(class_name, group=group, vendor=vendor, device=device)
    scd.add_compatible("altr,test-device-1.0")
    return scd


def _make_comp(
    class_name: str = "test_ip",
    instance_name: str = "comp0",
    version: str = "1.0",
    group: str = "unknown",
    vendor: str = "altr",
    device: str = "test-device",
) -> BasicComponent:
    scd = _make_scd(class_name, group=group, vendor=vendor, device=device)
    return BasicComponent(class_name, instance_name, version, scd)


def _minimal_system(name: str = "test_sys") -> AvalonSystem:
    return AvalonSystem(name, "1.0", Path("test.sopcinfo"))


def _minimal_boardinfo(pov: Optional[str] = None) -> BoardInfo:
    """BoardInfo with minimal settings — no file needed."""
    bi = BoardInfo.__new__(BoardInfo)
    bi._pov: Optional[str] = pov
    bi._pov_type = PovType.CPU
    bi._sort_type = SortType.NONE
    bi._altr_style = AltrStyle.AUTO
    bi._boot_args: Optional[str] = None
    bi._include_time = False
    bi._show_clock_tree = False
    bi._dump_parameters = ParameterAction.NONE
    bi._memory_nodes: Optional[List[str]] = None
    bi._irq_masters: List[str] = []
    bi.bics = []
    bi.source_file: Optional[Path] = None
    return bi


# Monkey-patch the missing methods onto the bare BoardInfo:
def _patch_boardinfo(bi: BoardInfo) -> None:
    """Add simple accessor methods to a bare BoardInfo instance."""
    bi.get_pov = lambda: bi._pov  # type: ignore[method-assign]
    bi.set_pov = lambda v: setattr(bi, '_pov', v)  # type: ignore[method-assign]
    bi.get_pov_type = lambda: bi._pov_type  # type: ignore[method-assign]
    bi.get_sort_type = lambda: bi._sort_type  # type: ignore[method-assign]
    bi.get_altr_style = lambda: bi._altr_style  # type: ignore[method-assign]
    bi.get_boot_args = lambda: bi._boot_args  # type: ignore[method-assign]
    bi.set_boot_args = lambda v: setattr(bi, '_boot_args', v)  # type: ignore[method-assign]
    bi.is_include_time = lambda: bi._include_time  # type: ignore[method-assign]
    bi.is_show_clock_tree = lambda: bi._show_clock_tree  # type: ignore[method-assign]
    bi.get_dump_parameters = lambda: bi._dump_parameters  # type: ignore[method-assign]
    bi.get_memory_nodes = lambda: bi._memory_nodes  # type: ignore[method-assign]
    bi.get_aliases = lambda: []  # type: ignore[method-assign]
    bi.get_alias_refs = lambda: []  # type: ignore[method-assign]
    bi.get_dt_appends = lambda: []  # type: ignore[method-assign]
    bi.is_valid_irq_master = lambda comp: comp.instance_name in bi._irq_masters  # type: ignore[method-assign]


def _make_bi(pov: Optional[str] = None) -> BoardInfo:
    bi = _minimal_boardinfo(pov)
    _patch_boardinfo(bi)
    return bi


def _add_mm_master(comp: BasicComponent, primary_w: int = 1, secondary_w: int = 1) -> Interface:
    intf = Interface("data_master", SystemDataType.MEMORY_MAPPED, True, comp,
                     primary_width=primary_w, secondary_width=secondary_w)
    comp.add_interface(intf)
    return intf


def _add_mm_slave(comp: BasicComponent, size: int = 0x1000,
                  primary_w: int = 1, secondary_w: int = 1) -> Interface:
    intf = Interface("s1", SystemDataType.MEMORY_MAPPED, False, comp,
                     primary_width=primary_w, secondary_width=secondary_w)
    intf.interface_value = [size]
    comp.add_interface(intf)
    return intf


def _connect_mm(
    master_comp: BasicComponent,
    slave_comp: BasicComponent,
    base_addr: int,
    primary_w: int = 1,
    secondary_w: int = 1,
) -> Connection:
    """Wire a memory-mapped master → slave connection at base_addr."""
    m_intf = master_comp.get_interfaces(SystemDataType.MEMORY_MAPPED, True)
    s_intf = slave_comp.get_interfaces(SystemDataType.MEMORY_MAPPED, False)
    assert m_intf, f"{master_comp.instance_name} has no MM master"
    assert s_intf, f"{slave_comp.instance_name} has no MM slave"
    conn = Connection(
        m_intf[0], s_intf[0], SystemDataType.MEMORY_MAPPED, connect=True
    )
    conn.conn_value = [base_addr]
    return conn


# ===========================================================================
# AbstractSopcGenerator helpers
# ===========================================================================

class TestAbstractSopcGeneratorHelpers:
    def test_definenify_basic(self):
        assert AbstractSopcGenerator.definenify("my-signal") == "MY_SIGNAL"

    def test_definenify_spaces(self):
        assert AbstractSopcGenerator.definenify("hello world") == "HELLO_WORLD"

    def test_definenify_already_upper(self):
        assert AbstractSopcGenerator.definenify("NIOS2_CPU") == "NIOS2_CPU"

    def test_small_copyright_no_time(self):
        notice = AbstractSopcGenerator.get_small_copyright_notice("devicetree", include_time=False)
        assert "/*" in notice
        assert "devicetree" in notice
        assert "Walter Goossens" in notice
        assert "sopc2dts version" in notice

    def test_small_copyright_with_time(self):
        notice = AbstractSopcGenerator.get_small_copyright_notice("devicetree", include_time=True)
        assert " on " in notice

    def test_small_copyright_custom_name(self):
        notice = AbstractSopcGenerator.get_small_copyright_notice("kernel-headers", False)
        assert "kernel-headers" in notice


class TestGetPovComponent:
    def test_pov_by_name(self):
        sys = _minimal_system()
        cpu = _make_comp("altera_nios2", "cpu0", group="cpu")
        _add_mm_master(cpu)
        sys.add_component(cpu)
        bi = _make_bi(pov="cpu0")
        gen = DTSGenerator2(sys)
        pov = gen.get_pov_component(bi)
        assert pov is cpu

    def test_pov_auto_finds_cpu_group(self):
        sys = _minimal_system()
        cpu = _make_comp("altera_nios2", "cpu0", group="cpu")
        _add_mm_master(cpu)
        sys.add_component(cpu)
        bi = _make_bi(pov=None)
        gen = DTSGenerator2(sys)
        pov = gen.get_pov_component(bi)
        assert pov is cpu

    def test_pov_fallback_first_master(self):
        sys = _minimal_system()
        comp = _make_comp("some_ip", "master0", group="bridge")
        _add_mm_master(comp)
        sys.add_component(comp)
        bi = _make_bi(pov=None)
        gen = DTSGenerator2(sys)
        pov = gen.get_pov_component(bi)
        assert pov is comp

    def test_pov_none_when_no_masters(self):
        sys = _minimal_system()
        bi = _make_bi(pov=None)
        gen = DTSGenerator2(sys)
        pov = gen.get_pov_component(bi)
        assert pov is None


# ===========================================================================
# BasicComponent.to_dt_node helpers
# ===========================================================================

class TestAddrFromConnection:
    def test_none_connection_returns_zero(self):
        comp = _make_comp()
        assert comp._get_addr_from_connection(None) == [0]

    def test_conn_value_returned(self):
        comp = _make_comp()
        m_intf = _add_mm_master(comp)
        s_comp = _make_comp(instance_name="slave0")
        _add_mm_slave(s_comp)
        conn = Connection(m_intf, s_comp.interfaces[0], SystemDataType.MEMORY_MAPPED, connect=True)
        conn.conn_value = [0x21000000]
        assert comp._get_addr_from_connection(conn) == [0x21000000]

    def test_addr_str_single_cell(self):
        comp = _make_comp()
        m_intf = _add_mm_master(comp)
        s_comp = _make_comp(instance_name="slave0")
        _add_mm_slave(s_comp)
        conn = Connection(m_intf, s_comp.interfaces[0], SystemDataType.MEMORY_MAPPED, connect=True)
        conn.conn_value = [0x21000000]
        assert comp._get_addr_from_connection_str(conn) == "21000000"

    def test_addr_str_multi_cell(self):
        comp = _make_comp()
        m_intf = _add_mm_master(comp, primary_w=2)
        s_comp = _make_comp(instance_name="slave0")
        _add_mm_slave(s_comp, primary_w=2)
        conn = Connection(m_intf, s_comp.interfaces[0], SystemDataType.MEMORY_MAPPED, connect=True)
        conn.conn_value = [0x00000001, 0x00000000]
        assert comp._get_addr_from_connection_str(conn) == "100000000"

    def test_addr_str_none_connection(self):
        comp = _make_comp()
        assert comp._get_addr_from_connection_str(None) == "0"


class TestGetReg:
    def test_slave_reg_collected(self):
        cpu = _make_comp("nios2", "cpu", group="cpu")
        _add_mm_master(cpu)
        periph = _make_comp("uart", "uart0", group="serial")
        _add_mm_slave(periph, size=0x20)
        conn = _connect_mm(cpu, periph, 0x21000000)
        names: List[str] = []
        regs = periph._get_reg(cpu, names)
        assert regs == [0x21000000, 0x20]
        assert names == ["s1"]

    def test_no_connection_to_master_excluded(self):
        cpu1 = _make_comp("nios2", "cpu1", group="cpu")
        _add_mm_master(cpu1)
        cpu2 = _make_comp("nios2", "cpu2", group="cpu")
        _add_mm_master(cpu2)
        periph = _make_comp("uart", "uart0", group="serial")
        _add_mm_slave(periph, size=0x20)
        _connect_mm(cpu1, periph, 0x21000000)
        # cpu2 has no connection to periph
        names: List[str] = []
        regs = periph._get_reg(cpu2, names)
        assert regs == []


class TestGetInterrupts:
    def test_no_irq(self):
        bi = _make_bi()
        comp = _make_comp()
        v_irqs: List[int] = []
        v_names: List[str] = []
        parent = comp._get_interrupts(v_irqs, bi, v_names)
        assert parent is None
        assert v_irqs == []

    def test_irq_connected(self):
        ic = _make_comp("arm_gic", "gic", group="irq")
        ic_intf = Interface("irq_master", SystemDataType.INTERRUPT, True, ic, primary_width=3)
        ic.add_interface(ic_intf)

        periph = _make_comp("timer", "timer0", group="timer")
        p_intf = Interface("irq0", SystemDataType.INTERRUPT, False, periph)
        periph.add_interface(p_intf)

        conn = Connection(ic_intf, p_intf, SystemDataType.INTERRUPT, connect=True)
        conn.conn_value = [42]

        bi = _make_bi()
        bi._irq_masters = ["gic"]

        v_irqs: List[int] = []
        v_names: List[str] = []
        parent = periph._get_interrupts(v_irqs, bi, v_names)

        assert parent is ic
        assert v_irqs == [42]
        assert v_names == ["irq0"]


# ===========================================================================
# BasicComponent.to_dt_node
# ===========================================================================

class TestToDTNode:
    def _make_cpu_system(self):
        """CPU + UART slave + IRQ controller — minimal wired system."""
        cpu = _make_comp("altera_nios2_qsys", "cpu0", group="cpu", vendor="altr", device="nios2-1.0")
        _add_mm_master(cpu)
        clk_slave = Interface("clk", SystemDataType.CLOCK, False, cpu)
        cpu.add_interface(clk_slave)

        periph = _make_comp("altera_avalon_uart", "uart0", group="serial", vendor="altr", device="uart-1.0")
        _add_mm_slave(periph, size=0x20)
        _connect_mm(cpu, periph, 0x21000000)

        return cpu, periph

    def test_node_name_uses_group_and_addr(self):
        cpu, periph = self._make_cpu_system()
        bi = _make_bi("cpu0")
        node = periph.to_dt_node(bi, periph.interfaces[0].connections[0])
        assert node.name == "serial@21000000"

    def test_node_label_is_instance_name(self):
        cpu, periph = self._make_cpu_system()
        bi = _make_bi("cpu0")
        conn = periph.interfaces[0].connections[0]
        node = periph.to_dt_node(bi, conn)
        assert node.label == "uart0"

    def test_compatible_property_present(self):
        cpu, periph = self._make_cpu_system()
        bi = _make_bi("cpu0")
        conn = periph.interfaces[0].connections[0]
        node = periph.to_dt_node(bi, conn)
        compat_prop = node.get_property_by_name("compatible")
        assert compat_prop is not None
        text = compat_prop.to_string()
        assert "altr,uart-1.0" in text

    def test_reg_property_present(self):
        cpu, periph = self._make_cpu_system()
        bi = _make_bi("cpu0")
        conn = periph.interfaces[0].connections[0]
        node = periph.to_dt_node(bi, conn)
        reg = node.get_property_by_name("reg")
        assert reg is not None
        text = reg.to_string()
        assert "0x21000000" in text
        assert "0x00000020" in text

    def test_no_reg_when_no_connection(self):
        comp = _make_comp(group="cpu")
        bi = _make_bi()
        node = comp.to_dt_node(bi, None)
        # No memory slave — no reg property
        assert node.get_property_by_name("reg") is None

    def test_cpu_group_gets_device_type(self):
        comp = _make_comp(group="cpu")
        bi = _make_bi()
        node = comp.to_dt_node(bi, None)
        dt = node.get_property_by_name("device_type")
        assert dt is not None
        assert "cpu" in dt.to_string()

    def test_memory_group_gets_device_type(self):
        comp = _make_comp(group="memory")
        bi = _make_bi()
        node = comp.to_dt_node(bi, None)
        dt = node.get_property_by_name("device_type")
        assert dt is not None
        assert "memory" in dt.to_string()

    def test_interrupt_controller_marked(self):
        ic = _make_comp("arm_gic", "gic", group="irq-controller")
        ic_intf = Interface("irq_master", SystemDataType.INTERRUPT, True, ic, primary_width=3)
        ic.add_interface(ic_intf)
        bi = _make_bi()
        node = ic.to_dt_node(bi, None)
        assert node.get_property_by_name("interrupt-controller") is not None
        cells_prop = node.get_property_by_name("#interrupt-cells")
        assert cells_prop is not None
        assert "3" in cells_prop.to_string()

    def test_irq_properties_added(self):
        ic = _make_comp("arm_gic", "gic", group="irq")
        ic_intf = Interface("irq_master", SystemDataType.INTERRUPT, True, ic, primary_width=1)
        ic.add_interface(ic_intf)

        periph = _make_comp("timer", "timer0", group="timer")
        p_intf = Interface("irq0", SystemDataType.INTERRUPT, False, periph)
        periph.add_interface(p_intf)
        conn = Connection(ic_intf, p_intf, SystemDataType.INTERRUPT, connect=True)
        conn.conn_value = [5]

        bi = _make_bi()
        bi._irq_masters = ["gic"]

        node = periph.to_dt_node(bi, None)
        assert node.get_property_by_name("interrupt-parent") is not None
        assert node.get_property_by_name("interrupts") is not None
        irq_text = node.get_property_by_name("interrupts").to_string()
        assert "5" in irq_text

    def test_auto_param_clock_frequency(self):
        """SICAutoParam dts_name=clock-frequency with no sopc_info_name → uses get_clock_rate()."""
        from sopc2dts_py.model.component import SICAutoParam
        scd = _make_scd(group="serial")
        scd.add_auto_param("clock-frequency", None, None)
        comp = BasicComponent("uart", "uart0", "1.0", scd)
        # No clock slave → clock_rate = 0
        bi = _make_bi()
        node = comp.to_dt_node(bi, None)
        cf = node.get_property_by_name("clock-frequency")
        assert cf is not None

    def test_auto_param_from_parameter(self):
        """SICAutoParam with a matching sopcinfo parameter."""
        from sopc2dts_py.model.component import SICAutoParam
        scd = _make_scd(group="serial")
        scd.add_auto_param("fifo-depth", "embeddedsw.fifo_depth", "unsigned")
        comp = BasicComponent("uart", "uart0", "1.0", scd)
        comp.add_param(Parameter("embeddedsw.fifo_depth", "16", DataType.UNSIGNED))
        bi = _make_bi()
        node = comp.to_dt_node(bi, None)
        prop = node.get_property_by_name("fifo-depth")
        assert prop is not None
        assert "0x00000010" in prop.to_string()

    def test_embsw_dts_compat_extends_compatible(self):
        """embeddedsw.dts.compatible parameter appends to compatible strings."""
        comp = _make_comp(group="serial")
        comp.add_param(Parameter("embeddedsw.dts.compatible", "altr,my-uart", DataType.STRING))
        bi = _make_bi()
        node = comp.to_dt_node(bi, None)
        compat_text = node.get_property_by_name("compatible").to_string()
        assert "altr,my-uart" in compat_text

    def test_embsw_dts_params_adds_property(self):
        """embeddedsw.dts.params.<name> adds a DTS property."""
        comp = _make_comp(group="serial")
        comp.add_param(Parameter("embeddedsw.dts.params.my-flag", "1", DataType.UNSIGNED))
        bi = _make_bi()
        node = comp.to_dt_node(bi, None)
        assert node.get_property_by_name("my-flag") is not None


# ===========================================================================
# Clock helper methods
# ===========================================================================

class TestClocksProperty:
    def test_no_clock_slaves_returns_empty(self):
        comp = _make_comp()
        assert comp.get_clocks_property() == []

    def test_clock_master_ph_single_output(self):
        clk_src = _make_comp("clock_source", "clk0", group="clock")
        cm = Interface("clk_out", SystemDataType.CLOCK, True, clk_src)
        clk_src.add_interface(cm)
        phvs = clk_src.get_clock_master_ph(cm)
        assert len(phvs) == 1
        assert isinstance(phvs[0], DTPropPHandleVal)
        assert phvs[0].label == "clk0"

    def test_clock_master_ph_multi_output(self):
        clk_src = _make_comp("pll", "pll0", group="clock")
        cm0 = Interface("clk_out0", SystemDataType.CLOCK, True, clk_src)
        cm1 = Interface("clk_out1", SystemDataType.CLOCK, True, clk_src)
        clk_src.add_interface(cm0)
        clk_src.add_interface(cm1)
        phvs = clk_src.get_clock_master_ph(cm1)
        assert len(phvs) == 2
        assert isinstance(phvs[1], DTPropNumVal)
        assert phvs[1].val == 1

    def test_clocks_property_built(self):
        """A periph with one clock slave should get a 'clocks' property."""
        clk_src = _make_comp("clock_source", "clk0", group="clock")
        cm = Interface("clk_out", SystemDataType.CLOCK, True, clk_src)
        clk_src.add_interface(cm)

        periph = _make_comp("timer", "timer0", group="timer")
        cs = Interface("clk_in", SystemDataType.CLOCK, False, periph)
        periph.add_interface(cs)

        clk_conn = Connection(cm, cs, SystemDataType.CLOCK, connect=True)
        clk_conn.conn_value = [50_000_000]

        props = periph.get_clocks_property()
        assert len(props) == 1
        assert props[0].name == "clocks"

    def test_clocks_property_multi_clock(self):
        """Multiple clock slaves → clocks + clock-names."""
        clk_src = _make_comp("pll", "pll0", group="clock")
        cm0 = Interface("clk_out0", SystemDataType.CLOCK, True, clk_src)
        cm1 = Interface("clk_out1", SystemDataType.CLOCK, True, clk_src)
        clk_src.add_interface(cm0)
        clk_src.add_interface(cm1)

        periph = _make_comp("eth", "eth0", group="ethernet")
        cs0 = Interface("clk_in0", SystemDataType.CLOCK, False, periph)
        cs1 = Interface("clk_in1", SystemDataType.CLOCK, False, periph)
        periph.add_interface(cs0)
        periph.add_interface(cs1)

        conn0 = Connection(cm0, cs0, SystemDataType.CLOCK, connect=True)
        conn1 = Connection(cm1, cs1, SystemDataType.CLOCK, connect=True)
        conn0.conn_value = [50_000_000]
        conn1.conn_value = [100_000_000]

        props = periph.get_clocks_property()
        names = [p.name for p in props]
        assert "clocks" in names
        assert "clock-names" in names


# ===========================================================================
# DTGenerator — get_dt_output
# ===========================================================================

def _build_nios2_system():
    """Minimal Nios II + UART + SDRAM system for smoke testing the generator."""
    from sopc2dts_py.components.base.SICCpuComponent import SICCpuComponent

    sys = _minimal_system("nios2_system")

    # --- CPU ---
    scd_cpu = SopcComponentDescription("altera_nios2_qsys", group="cpu",
                                        vendor="altr", device="nios2")
    scd_cpu.add_compatible("altr,nios2-1.0")
    cpu_base = BasicComponent("altera_nios2_qsys", "cpu0", "1.0", scd_cpu)
    cpu = SICCpuComponent(cpu_base)
    _add_mm_master(cpu)
    sys.add_component(cpu)

    # --- UART ---
    uart = _make_comp("altera_avalon_jtag_uart", "jtag_uart0", group="serial",
                      vendor="altr", device="jtag-uart")
    _add_mm_slave(uart, size=0x08)
    _connect_mm(cpu, uart, 0x21000000)
    sys.add_component(uart)

    # --- SDRAM (memory) ---
    sdram_scd = SopcComponentDescription("altera_avalon_new_sdram_controller",
                                          group="memory", vendor="altr", device="sdram")
    sdram = BasicComponent("altera_avalon_new_sdram_controller", "sdram0", "1.0", sdram_scd)
    _add_mm_slave(sdram, size=0x8000000)
    _connect_mm(cpu, sdram, 0x00000000)
    sys.add_component(sdram)

    return sys


class TestDTGeneratorOutput:
    def test_get_dt_output_returns_dtnode(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        assert isinstance(root, DTNode)
        assert root.name == "/"

    def test_root_has_model_and_compatible(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        assert root.get_property_by_name("model") is not None
        assert root.get_property_by_name("compatible") is not None
        model_text = root.get_property_by_name("model").to_string()
        assert "nios2_system" in model_text

    def test_address_cells_and_size_cells(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        assert root.get_property_by_name("#address-cells") is not None
        assert root.get_property_by_name("#size-cells") is not None

    def test_cpus_node_present(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        cpu_nodes = [c for c in root.children if c.name == "cpus"]
        assert len(cpu_nodes) == 1

    def test_memory_node_present(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        mem_nodes = [c for c in root.children if c.name == "memory"]
        assert len(mem_nodes) == 1

    def test_sopc_node_present(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        sopc_nodes = [c for c in root.children if c.name.startswith("sopc")]
        assert len(sopc_nodes) == 1

    def test_sopc_node_has_avalon_compatible(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        sopc = next(c for c in root.children if c.name.startswith("sopc"))
        compat = sopc.get_property_by_name("compatible")
        assert compat is not None
        compat_text = compat.to_string()
        assert "ALTR,avalon" in compat_text
        assert "simple-bus" in compat_text

    def test_chosen_node_present(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        chosen = [c for c in root.children if c.name == "chosen"]
        assert len(chosen) == 1
        bootargs = chosen[0].get_property_by_name("bootargs")
        assert bootargs is not None

    def test_uart_in_sopc_node(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        sopc = next(c for c in root.children if c.name.startswith("sopc"))
        # uart0 should appear as a child of sopc
        uart_nodes = [c for c in sopc.children if c.label == "jtag_uart0"]
        assert len(uart_nodes) == 1

    def test_no_pov_produces_root_node(self):
        """Empty system — no POV component. Should still return a DTNode."""
        sys = _minimal_system()
        bi = _make_bi()
        gen = DTSGenerator2(sys)
        root = gen.get_dt_output(bi)
        assert isinstance(root, DTNode)


# ===========================================================================
# DTSGenerator2.get_text_output
# ===========================================================================

class TestDTSGenerator2TextOutput:
    def test_output_starts_with_dts_header(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        text = gen.get_text_output(bi)
        assert text is not None
        assert "/dts-v1/;" in text

    def test_output_contains_copyright(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        text = gen.get_text_output(bi)
        assert "/*" in text
        assert "sopc2dts" in text

    def test_output_contains_root_node(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        text = gen.get_text_output(bi)
        assert "/ {" in text

    def test_output_is_text(self):
        gen = DTSGenerator2(_minimal_system())
        assert gen.is_text_output() is True

    def test_binary_output_is_encoded_text(self):
        sys = _build_nios2_system()
        bi = _make_bi("cpu0")
        bi._memory_nodes = ["sdram0"]
        gen = DTSGenerator2(sys)
        binary = gen.get_binary_output(bi)
        text = gen.get_text_output(bi)
        assert binary is not None
        assert text is not None
        assert binary == text.encode("utf-8")


# ===========================================================================
# ALTR/altr normalisation
# ===========================================================================

class TestAltrCompatibleNormalisation:
    def _make_comp_with_altr_compat(self, grp="serial"):
        scd = SopcComponentDescription("test_ip", group=grp, vendor="altr", device="uart")
        scd.add_compatible("altr,uart-1.0")
        return BasicComponent("test_ip", "uart0", "1.0", scd)

    def test_force_lower_converts_ALTR_to_altr(self):
        from sopc2dts_py.generators.DTGenerator import DTGenerator
        node = DTNode("root")
        prop = DTProperty.from_strings("compatible", ["ALTR,uart-1.0", "simple-bus"])
        node.add_property(prop)
        DTGenerator._fix_altr_compatible_mess(node, "altr")
        compat_text = node.get_property_by_name("compatible").to_string()
        assert "altr,uart-1.0" in compat_text
        assert "ALTR,uart-1.0" not in compat_text

    def test_force_upper_converts_altr_to_ALTR(self):
        from sopc2dts_py.generators.DTGenerator import DTGenerator
        node = DTNode("root")
        prop = DTProperty.from_strings("compatible", ["altr,uart-1.0", "simple-bus"])
        node.add_property(prop)
        DTGenerator._fix_altr_compatible_mess(node, "ALTR")
        compat_text = node.get_property_by_name("compatible").to_string()
        assert "ALTR,uart-1.0" in compat_text
        assert '"altr,uart-1.0"' not in compat_text

    def test_property_name_normalised(self):
        from sopc2dts_py.generators.DTGenerator import DTGenerator
        node = DTNode("root")
        node.add_property(DTProperty.from_long("altr,fifo-depth", 16))
        DTGenerator._fix_altr_compatible_mess(node, "ALTR")
        assert node.get_property_by_name("ALTR,fifo-depth") is not None

    def test_recursive_normalisation(self):
        from sopc2dts_py.generators.DTGenerator import DTGenerator
        parent = DTNode("parent")
        child = DTNode("child")
        child.add_property(DTProperty.from_strings("compatible", ["altr,uart-1.0"]))
        parent.add_child(child)
        DTGenerator._fix_altr_compatible_mess(parent, "ALTR")
        compat_text = child.get_property_by_name("compatible").to_string()
        assert "ALTR,uart-1.0" in compat_text


# ===========================================================================
# GeneratorFactory
# ===========================================================================

class TestGeneratorFactory:
    def test_dts_type_returns_dts_generator(self):
        sys = _minimal_system()
        gen = GeneratorFactory.create_generator_for(sys, GeneratorType.DTS)
        assert isinstance(gen, DTSGenerator2)

    def test_dts_generator_is_text(self):
        sys = _minimal_system()
        gen = GeneratorFactory.create_generator_for(sys, GeneratorType.DTS)
        assert gen.is_text_output()

    def test_unsupported_type_returns_none(self):
        sys = _minimal_system()
        gen = GeneratorFactory.create_generator_for(sys, GeneratorType.GRAPH)
        assert gen is None

    def test_get_type_by_name_dts(self):
        assert GeneratorFactory.get_type_by_name("dts") == GeneratorType.DTS

    def test_get_type_by_name_case_insensitive(self):
        assert GeneratorFactory.get_type_by_name("DTS") == GeneratorType.DTS

    def test_get_type_by_name_unknown(self):
        assert GeneratorFactory.get_type_by_name("unknown_type") is None


# ===========================================================================
# AvalonSystem.get_connection_path
# ===========================================================================

class TestGetConnectionPath:
    def test_direct_connection(self):
        sys = _minimal_system()
        cpu = _make_comp("nios2", "cpu", group="cpu")
        _add_mm_master(cpu)
        uart = _make_comp("uart", "uart0", group="serial")
        _add_mm_slave(uart)
        _connect_mm(cpu, uart, 0x21000000)
        sys.add_component(cpu)
        sys.add_component(uart)

        path = sys.get_connection_path(cpu, uart, SystemDataType.MEMORY_MAPPED)
        assert len(path) == 1
        assert path[0].slave_module is uart

    def test_no_path_returns_empty(self):
        sys = _minimal_system()
        cpu = _make_comp("nios2", "cpu", group="cpu")
        _add_mm_master(cpu)
        uart = _make_comp("uart", "uart0", group="serial")
        _add_mm_slave(uart)
        # Not connected
        sys.add_component(cpu)
        sys.add_component(uart)

        path = sys.get_connection_path(cpu, uart, SystemDataType.MEMORY_MAPPED)
        assert path == []

    def test_path_through_bridge(self):
        sys = _minimal_system()
        cpu = _make_comp("nios2", "cpu", group="cpu")
        _add_mm_master(cpu)

        bridge = _make_comp("hps_bridge", "bridge0", group="bridge")
        _add_mm_slave(bridge)
        _add_mm_master(bridge)
        _connect_mm(cpu, bridge, 0xFF200000)

        uart = _make_comp("uart", "uart0", group="serial")
        _add_mm_slave(uart)
        _connect_mm(bridge, uart, 0x00000000)

        sys.add_component(cpu)
        sys.add_component(bridge)
        sys.add_component(uart)

        path = sys.get_connection_path(cpu, uart, SystemDataType.MEMORY_MAPPED)
        assert len(path) == 2
        assert path[0].slave_module is bridge
        assert path[1].slave_module is uart
