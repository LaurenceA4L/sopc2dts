# sopc2dts — Java to Python Porting Tracker

Migration of sopc2dts from Java (Swing GUI) to Python (FastAPI + HTMX web GUI).  
I will tick the boxes off as each item lands on `main`.

---

## Guiding Principles

- Port behaviour faithfully before extending it. The Java tool is the reference.
- Each phase should leave the tool in a working, testable state.
- GUI comes last. The CLI must be solid first.
- Future plans to ADD Agilex7 / Agilex5 support is an extension layer on top of a clean port.
- I will NOT mix the two until Phase 1–3 are done.

---

## Known Porting Deviations

Places where the Python port intentionally does *not* replicate Java
behaviour, because that behaviour was a bug rather than a design choice.
Each entry should explain what the Java code actually did and why the fix
is safe.

- **`SpiSlave` cpol/cpha/csHigh always False** — `boardinfo.py`. The Java
  constructor read these via `Boolean.getBoolean(atts.getValue("cpol"))`.
  `Boolean.getBoolean` doesn't parse its argument — it looks up a *JVM
  system property* of that name — so for a normal XML attribute value it
  always returns `false`. These flags were therefore permanently stuck at
  `False` in the Java tool no matter what the boardinfo file said. The
  Python port (`_parse_bool` in `boardinfo.py`) parses `"true"/"false"`
  attribute values properly.

---

## Phase 1 — Core Model + Parsers (CLI parity)

Goal: `sopc2dts -i foo.sopcinfo -o foo.dts` produces identical output in Python.

### Project skeleton
- [x] `pyproject.toml` with `[project]` metadata, `scripts = {sopc2dts = "sopc2dts.__main__:main"}`
- [x] Package layout: `sopc2dts_py/{model,parsers,components,generators,gui}/`
- [x] `logging` integration replacing `Logger` / `LogListener` / `LogEntry`
- [x] Basic `argparse` CLI in `__main__.py` (all flags from `Sopc2DTS.java`)

### Model layer (`sopc2dts_py/model/`)
- [x] `parameter.py` — `Parameter` dataclass (name, value, type)
- [x] `connection.py` — `Connection` dataclass (master iface → slave iface)
- [x] `component.py` — `BasicComponent`, `Interface`, `MemoryBlock`, `SopcComponentDescription`
- [x] `system.py` — `AvalonSystem` (component registry, master/slave lookups)
- [x] `enums.py` — `SystemDataType`, `ParameterAction` (added to avoid circular imports)
- [x] `boardinfo.py` — `BoardInfo` + boardinfo XML components (Ethernet, I2C, SPI, Flash, DTAppend)
- [x] `devicetree.py` — `DTNode`, `DTProperty`, `DTPropVal` subtypes, `DTBlob`, `DTHelper`
- [x] `component_lib.py` — `SopcComponentLib` equivalent (XML-driven component registry)

### Parsers (`sopc2dts/parsers/`)
- [x] `sopcinfo.py` — port `SopcInfoSystemLoader` (SAX → `ElementTree`)
- [x] `qsys.py` — port `QSysSystemLoader`
- [x] `boardinfo_xml.py` — port `BoardInfo.load()` (boardinfo XML → `BoardInfo`)
- [x] `component_xml.py` — port component library XML loader (`sopc_components_*.xml`)

### Component handlers (`sopc2dts/components/`)
- [x] `base/SICBridge.py` — `SICBridge` + removal strategies (all / balanced / none)
- [x] `base/SICCpuComponent.py` — `SICCpuComponent`
- [x] `base/SICEthernet.py` — `SICEthernet`
- [x] `base/SICFlash.py` — `SICFlash`
- [x] `base/SICI2CMaster.py` — `SICI2CMaster`
- [x] `base/SICSpiMaster.py` — `SICSpiMaster`
- [x] `base/SICGpioController.py` — `SICGpioController`
- [x] `base/SICClockSource.py` — `SICClockSource`
- [x] `base/SICUnknown.py` — `SICUnknown` (passthrough fallback)
- [x] `base/SCDSelfDescribing.py` — `SCDSelfDescribing` (self-describing via embeddedsw.dts.* params)
- [x] `base/InterruptReceiver.py` — `InterruptReceiver` (abstract IRQ bridge base)
- [x] `altera/hps/VirtualClockElement.py` — `VirtualClockElement`
- [x] `altera/hps/SocFpgaPeripClock.py` — `SocFpgaPeripClock`
- [x] `altera/hps/SocFpgaGateClock.py` — `SocFpgaGateClock`
- [x] `altera/hps/SocFpgaPllClock.py` — `SocFpgaPllClock`
- [x] `altera/hps/ClockManager.py` — `ClockManager` (abstract HPS clock manager base)
- [x] `altera/hps/ClockManagerV.py` — `ClockManagerV` (Cyclone V / Arria 5)
- [x] `altera/hps/ClockManagerA10.py` — `ClockManagerA10` (Arria 10)
- [x] `altera/SICTrippleSpeedEthernet.py` — `SICTrippleSpeedEthernet`
- [x] `altera/TSEMonolithic.py` — `TSEMonolithic`
- [x] `altera/PCIeCompiler.py` — `PCIeCompiler` (static factory)
- [x] `altera/PCIeRootPort.py` — `PCIeRootPort`
- [x] `altera/SICSgdma.py` — `SICSgdma`
- [x] `altera/SICEpcs.py` — `SICEpcs`
- [x] `altera/SICLan91c111.py` — `SICLan91c111`
- [x] `altera/InterruptBridge.py` — `InterruptBridge`
- [x] `altera/InterruptLatencyCounter.py` — `InterruptLatencyCounter`
- [x] `altera/MultiBridge.py` — `MultiBridge`
- [x] `altera/GenericTristateController.py` — `GenericTristateController`
- [x] `altera/InterfaceGenerator.py` — `InterfaceGenerator`
- [x] `altera/A10InterfaceGenerator.py` — `A10InterfaceGenerator`
- [x] `altera/VIPFrameBuffer.py` — `VIPFrameBuffer`
- [x] `altera/VIPMixer.py` — `VIPMixer`
- [x] `arm/CortexA9GIC.py` — `CortexA9GIC`
- [x] `snps/DwGpio.py` — `DwGpio`
- [x] `labx/LabXEthernet.py` — `LabXEthernet`
- [x] `nxp/USBHostControllerISP1xxx.py` — `USBHostControllerISP1xxx`

### Verification

See [docs/TESTING.md](TESTING.md) for the full test strategy (unit → component → golden diff).

**Step 1 — component tests (Phase 1 only, no generator needed)**
- [x] `tests/fixtures/` populated with real `.sopcinfo` files (see below)
- [x] `sopc_components_*.xml` files all load without errors
- [x] CV SoC GHRD parses cleanly; expected HPS component types present
- [ ] A10 SoC GHRD parses cleanly; `ClockManagerA10` / `DwGpio` present
- [x] NEEK design parses cleanly; Nios II + TSE + SGDMA present

**Fixtures to acquire and commit to `tests/fixtures/`:**
- [x] `cv_soc_ghrd.sopcinfo` — Cyclone V SoC GHRD
- [x] `de0_nano_soc_ghrd.sopcinfo` — DE0-Nano SoC GHRD
- [x] `neek.sopcinfo` — NEEK reference design (synthetic, pairs with `boardinfo_neek.xml`)
- [x] `boardinfo_neek.xml` — original bundled board file (`pov` corrected to `cpu_0` for fixture)
- [ ] `a10_soc_system.sopcinfo` — Arria 10 SoC GHRD (rocketboards.org)
- [ ] `synthetic_vip.sopcinfo` — hand-crafted, covers `VIPFrameBuffer` / `VIPMixer`
- [ ] `synthetic_pcie.sopcinfo` — hand-crafted, covers `PCIeRootPort`
- [ ] `synthetic_labx.sopcinfo` — hand-crafted, covers `LabXEthernet` / ISP1xxx / LAN91C111

**Step 2 — golden diff tests (requires Phase 2 DTS generator)**

> **Decision (2026-06-08):** A true golden diff against Java tool output is not
> currently feasible for the following reasons:
>
> 1. The original GSRD `.sopcinfo` releases on rocketboards.org that the Java
>    tool was designed for are all 404 — those archives are gone.
> 2. Modern Platform Designer exports use an updated `.sopcinfo` schema that
>    references null fields (e.g. `nm`) the Java parser does not handle, causing
>    `NullPointerException` crashes before any DTS is generated.
> 3. Our synthetic test fixtures are minimal-XML stubs that also trigger those
>    null-field crashes in the Java tool.
>
> **Chosen approach:** manual Java source comparison.  Read `DTGenerator.java`,
> `DTSGenerator2.java`, and `BasicComponent.java` directly; verify that the
> Python output for synthetic fixtures matches the logic in those files.  Any
> deliberate deviations are recorded in the "Known Porting Deviations" section
> above.  When real `.sopcinfo` files from supported hardware become available,
> add them to `tests/fixtures/` and revisit.

- [ ] Java reference `.dts` files generated and committed to `tests/golden/`
- [ ] Python output matches Java output for CV SoC GHRD (whitespace-normalised)
- [ ] Python output matches Java output for A10 SoC GHRD
- [ ] Python output matches Java output for NEEK design

---

## Phase 2 — Generators

Goal: all output types from `-t` work and produce correct output.

> **Gate:** `dts.py` + `factory.py` must land before golden diff tests (Step 2
> above) can run. Port these first; the remaining generators can follow.

### Text generators (`sopc2dts_py/generators/`)
- [x] `DTSGenerator2.py` — port `DTSGenerator2` (primary output — **port first**)
- [x] `GeneratorFactory.py` — port `GeneratorFactory` (string type → generator instance — **port second**)
- [x] `KernelHeadersGenerator.py` — port `KernelHeadersGenerator`
- [x] `UBootHeaderGenerator.py` — port `UBootHeaderGenerator` (UBootComponentLib inlined)
- [x] `SopcCreateHeaderFilesImitator.py` — port `SopcCreateHeaderFilesImitator`
- [x] `GraphGenerator.py` — port `GraphGenerator` (Graphviz dot output)

### Binary generators
- [x] `DTBGenerator2.py` — shells out to `dtc -O dtb -I dts`, fallback to built-in `DTBlob`
- [x] `DTBHex8Generator.py` — port `DTBHex8Generator` (wraps DTBGenerator2 + bin2ihex I8Hex)
- [x] `DTBHex32Generator.py` — port `DTBHex32Generator` (wraps DTBGenerator2 + bin2ihex I32Hex LE)
- [x] `DTBCCharArray.py` — port `DTBCCharArray` (C unsigned char array, 12 entries/line)
- [x] `lib/bin2ihex.py` — port `Bin2IHex` (I8Hex / I32Hex / I64Hex with LE/BE byte ordering)

> **DTB generation decision (2026-06-08):** Rather than re-implementing the FDT binary
> serialisation from scratch, `DTBGenerator2` shells out to `dtc` (the standard Device Tree
> Compiler), which is universally available on Linux build hosts and validates the output.
> A built-in `DTBlob.get_bytes()` implementation is retained as a fallback for environments
> where `dtc` is not on `PATH`.

### Verification
- [ ] Round-trip test: `.sopcinfo` → DTB → decompile with `dtc` → compare to DTS output
- [x] `--mimic-sopc-create-header-files` (`-m`) auto-selects `sopc-header` output type

---

## Phase 3 — CLI Polish

Goal: drop-in replacement for the Java JAR on the command line.

- [x] All flags from `Sopc2DTS.java` implemented and tested
- [x] `--bridge-removal` strategies all work (all / balanced / none → `SICBridge`)
- [x] `--pov` / `--pov-type` selection
- [x] `--sort` (none / address / name / label)
- [x] `--bridge-ranges` (none / bridge / child) — wired to `BoardInfo.set_ranges_style()`
- [x] `--force-ALTR` / `--force-altr` compatible string normalisation
- [x] `--no-timestamp` flag
- [x] `--extra-component-libs` loading
- [x] `--mimic-sopc-create-header-files` (`-m`) auto-selects `sopc-header` output type
- [x] `--clocks` / `--conduits` / `--reset` / `--streaming` visibility flags
- [x] Version string from `importlib.metadata`
- [x] Exit codes match Java (0 = success, 1 = error)
- [x] Binary output to stdout warns when stdout is a terminal
- [x] Makefile replaced (Java `sopc2dts.jar` targets → `install` / `test` / `venv` / `clean`)
- [x] `sopc2dts.sh` wrapper added (auto-detects `.venv` or system Python 3.10+)

---

## Phase 4 — Web GUI

Goal: `sopc2dts --gui` opens a functional browser UI equivalent to the Swing GUI.

> **Implementation note:** single-file FastAPI + HTMX approach chosen over the
> original multi-template plan.  No frontend framework — dark-theme monospace UI,
> server-side rendering via HTMX partial swaps.

### Server (`sopc2dts_py/gui/`)
- [x] `app.py` — FastAPI app (routes, state singleton, log capture)
- [x] `launcher.py` — finds free port, starts uvicorn in main thread, opens browser in background thread
- [x] `__init__.py` — exposes `launch()`
- [x] `__main__.py` wires `--gui` flag to `launcher.launch()`

### Template (`sopc2dts_py/gui/templates/`)
- [x] `index.html` — single-page dark UI (HTMX 1.9, no framework)
  - Input section: sopcinfo path + board XML path, both with Load buttons
  - System section: component table (instance / class / group), HTMX-swapped on load
  - Generate section: output type, POV, sort, show-clocks, no-timestamp
  - Output section: textarea with Copy button + named download link
  - Log section: SSE stream, Clear button, auto-scroll toggle

### API routes
- [x] `GET /health` — launcher readiness poll
- [x] `POST /load` — parse sopcinfo/qsys, return system fragment
- [x] `POST /load-board` — parse boardinfo XML, return status + OOB POV field update
- [x] `POST /generate` — run generator, return output textarea or binary download link
- [x] `GET /download` — serve last output as named file attachment
- [x] `GET /log/stream` — SSE endpoint for live log (keepalive every 250 ms)

### Polish
- [x] Package version wired to generated DTS header (no more "version unknown")
- [x] Generated header updated: Walter's credit + Python port attribution + GitHub URL
- [x] Board file POV auto-fills generate form via HTMX OOB swap
- [x] Download filename uses system name (e.g. `neek.dts` not `output.dts`)
- [x] Known bug #1 logged: Ctrl+C unreliable on Windows/PowerShell (workaround: close browser tab)

### Verification
- [x] Manual smoke test: load `neek.sopcinfo` + `tests/fixtures/boardinfo_neek.xml`, generate DTS
- [x] Log panel streams messages in real time
- [x] Binary download works (DTB hex)
- [x] `tests/fixtures/boardinfo_neek.xml` added (original bundled file, `pov` corrected to `cpu_0`)

---

## Phase 5 — Agilex7 + Agilex5 Support

Goal: modernise component coverage for current Intel/Altera toolchain output.

### Phase 5A — Agilex7 (complete ✅)

Verified with a real Quartus 25.1 Agilex7 GHRD project (`a7-ghrd-project-orig`).

**Key findings:**

- `.sopcinfo` XML format is unchanged from Cyclone V / Arria 10 — no parser changes needed.
- New HPS class name: `intel_agilex_hps` (replaces `altera_arria10_hps`).
- Interface generator: `intel_agilex_interface_generator` (mirrors A10 pattern; moves EMAC interfaces to HPS EMAC sub-components).
- Agilex7 is **evolutionary** from Stratix 10/Arria 10: Cortex-A53 cluster, GIC-400, 32-bit SoC address space. Most DTS compatible strings carry over (`altr,socfpga-stmmac-a10-s10` for Ethernet, `intel,agilex-clkmgr` for clock manager).

**Changes made:**

- `sopc_components_altera.xml`: added `intel_agilex_hps`, `intel_agilex_interface_generator`, `altera_emif_cal`, `altera_emif_fm_hps`, `hps_response_timer`, `altera_s10_user_rst_clkgate`, `intel_cache_coherency_translator`, `intel_pcie_ptile_mcdma`, `arm_a9`, `hps_virt_clk`, `falconmesa_arm_gic`, `falconmesa_hps_bridge_avalon`.
- `sopc2dts_py/components/altera/AgilexInterfaceGenerator.py`: new handler for `intel_agilex_interface_generator`.
- `sopc2dts_py/model/component_lib.py`: dispatch case for `intel_agilex_interface_generator`.
- `tests/fixtures/a7_system.sopcinfo`: real Agilex7 GHRD sopcinfo from Quartus 25.1.
- `tests/integration/test_a7_integration.py`: 15 integration tests, all passing.

**A7 component coverage (new entries):**

| Component | Status | Notes |
|---|---|---|
| `intel_agilex_hps` | ignore ✓ | HPS toplevel; no direct DTS node. Connections from other ignored components suppressed at debug level. |
| `intel_agilex_interface_generator` | handler ✓ | Moves EMAC signal interfaces to HPS EMAC sub-components before generation (mirrors A10 pattern). |
| `altera_emif_cal` | ignore ✓ | EMIF calibration core; no DTS representation. |
| `altera_emif_fm_hps` | ignore ✓ | EMIF fabric-to-HPS bridge; no DTS representation. |
| `hps_response_timer` | ignore ✓ | HPS response timer; no DTS representation. |
| `altera_s10_user_rst_clkgate` | ignore ✓ | User reset/clock gate; no DTS representation. |
| `intel_cache_coherency_translator` | ignore ✓ | Cache coherency bridge; no DTS representation. |
| `intel_pcie_ptile_mcdma` | ignore ✓ | P-Tile PCIe + MCDMA. Fabric-only in A7 GHRD (no HPS Avalon-MM access); no HPS DTS node needed. |
| `altera_reset_bridge` | ignore ✓ | Reset domain crossing bridge; no DTS representation. |
| `arm_a9` | ignore ✓ | ARM placeholder sub-component; no DTS representation. |
| `hps_virt_clk` | ignore ✓ | Virtual clock placeholder; no DTS representation. |
| `falconmesa_arm_gic` | ignore ✓ | GIC-400 internal; real interrupt controller handled via `arm_gic,falconmesa_arm_gic` combined class name. |
| `falconmesa_hps_bridge_avalon` | ignore ✓ | Internal HPS bridge; no DTS representation. |

### Phase 5B — Agilex5 (pending)

Agilex5 is a **breaking** change relative to all prior families:

- **CPU**: Cortex-A55 + Cortex-A76 big.LITTLE cluster (not A53).
- **GIC**: GIC-v3 (`arm,gic-v3`) — different register layout from GIC-400.
- **Address space**: 64-bit — `#address-cells = <2>` in DTS.
- **Ethernet**: XGMAC (`snps,dwxgmac-2.10`) replaces TSE/STMMAC.
- **DMA**: AXI DMA (not PL330).
- **I3C** replaces I2C on some buses; different NAND controller.

64-bit address-cell support in the DTS generator is the main prerequisite.

- [ ] Obtain real Agilex5 `.sopcinfo` / `.qsys` fixture
- [ ] Add 64-bit `#address-cells` support to DTS generator
- [ ] Add `intel_agilex5_hps` and associated interface generator class names
- [ ] Add GIC-v3 handler (`arm,gic-v3` compatible)
- [ ] Add XGMAC Ethernet handler (`snps,dwxgmac-2.10`)
- [ ] Update `sopc_components_altera.xml` for Agilex5 IP blocks
- [ ] Integration tests against real Agilex5 project

