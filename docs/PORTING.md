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
- [ ] `tests/fixtures/` populated with real `.sopcinfo` files (see below)
- [ ] `sopc_components_*.xml` files all load without errors
- [x] CV SoC GHRD parses cleanly; expected HPS component types present
- [ ] A10 SoC GHRD parses cleanly; `ClockManagerA10` / `DwGpio` present
- [x] NEEK design parses cleanly; Nios II + TSE + SGDMA present

**Fixtures to acquire and commit to `tests/fixtures/`:**
- [ ] `cv_soc_system.sopcinfo` — Cyclone V SoC GHRD (rocketboards.org, GSRD 14.x)
- [ ] `a10_soc_system.sopcinfo` — Arria 10 SoC GHRD (rocketboards.org)
- [ ] `neek.sopcinfo` — NEEK reference design (pairs with `boardinfo_neek.xml`)
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

### Server (`sopc2dts/gui/`)
- [ ] `app.py` — FastAPI app with uvicorn launcher
- [ ] `launcher.py` — finds free port, starts server, calls `webbrowser.open(url)`
- [ ] `__main__.py` wires `--gui` flag to `launcher.py`

### Templates (`sopc2dts/gui/templates/`)
- [ ] `base.html` — layout, nav tabs, HTMX + minimal CSS (no framework)
- [ ] `input.html` — file picker for `.sopcinfo` / `.qsys`, component list (HTMX swap)
- [ ] `boardinfo.html` — port of `BoardInfoPanel` tabs (General, Ethernet, I2C, SPI, Flash)
- [ ] `output.html` — output type selector, POV picker, generate button, preview pane
- [ ] `log.html` — streaming log via SSE (`/log/stream` endpoint)

### API routes
- [ ] `POST /system/load` — parse input file, return component list fragment
- [ ] `POST /boardinfo/load` — parse boardinfo XML, return populated form
- [ ] `POST /generate` — run generator, return text/binary result
- [ ] `GET /generate/download` — serve binary output as file download
- [ ] `GET /log/stream` — SSE endpoint for live log output

### Verification
- [ ] Manual smoke test: load `boardinfo_neek.xml`, generate DTS, verify output matches CLI
- [ ] Log panel streams messages in real time
- [ ] Binary download works (DTB)

---

## Phase 5 — Agilex7 + Agilex5 Support

Goal: modernise component coverage for current Intel/Altera toolchain output.

> Note: Quartus Pro `.qsys` format for Agilex differs from legacy Cyclone V / Arria 10.  
> Confirm exact differences from Intel docs before starting this phase.

- [ ] Audit `.qsys` format differences for Agilex7 vs Arria 10
- [ ] Update `parsers/qsys.py` for any schema changes
- [ ] Add Agilex7 HPS component handlers (new IP blocks, updated compatibles)
- [ ] Add Agilex5 HPS component handlers
- [ ] Update DTS `compatible` strings for Agilex SoC family
- [ ] Test against real Agilex7 `.sopcinfo` / `.qsys` files
- [ ] Test against real Agilex5 `.sopcinfo` / `.qsys` files

---

## Phase 6 — cheby Integration (future)

Goal: GUI becomes a unified front-end for sopc2dts + cheby register tooling.

> Deferred until Phases 1–4 are complete and stable.

- [ ] Design shared data model between sopc2dts component map and cheby register map
- [ ] Add cheby input panel to web GUI
- [ ] Cross-link: sopc2dts component address → cheby register block
- [ ] Unified DTS + register header generation workflow
- [ ] Export: combined `.dts` + `.yaml` / `.h` output

---

## Reference Files

| File | Purpose |
|------|---------|
| `Sopc2DTS.java` | CLI entry point, option parsing |
| `sopc2dts/parsers/sopcinfo/SopcInfoSystemLoader.java` | Main input parser |
| `sopc2dts/parsers/qsys/QSysSystemLoader.java` | Qsys input parser |
| `sopc2dts/lib/AvalonSystem.java` | Core system model |
| `sopc2dts/lib/BoardInfo.java` | Board overlay model |
| `sopc2dts/lib/devicetree/*.java` | DT data model |
| `sopc2dts/generators/DTSGenerator2.java` | Primary DTS text output |
| `sopc2dts/generators/DTBGenerator2.java` | DTB binary output |
| `sopc2dts/gui/Sopc2DTSGui.java` | Swing GUI shell |
| `sopc_components_*.xml` | Component library definitions |
| `boardinfo_neek.xml` | Example boardinfo file (test fixture) |
