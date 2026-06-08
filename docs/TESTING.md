# sopc2dts — Test Strategy

This document describes the test levels used in this project, what each covers,
and where the gaps are.

---

## Test levels

### Unit tests

**Location:** `tests/test_*.py`  
**Run with:** `pytest`  
**What they test:** Individual classes in isolation, with all dependencies
constructed inline. No file I/O, no real `.sopcinfo` input.

| File | Scope |
|------|-------|
| `test_model.py` | `BasicComponent`, `Interface`, `Connection`, `Parameter`, `AvalonSystem` |
| `test_devicetree.py` | `DTNode`, `DTProperty`, `DTPropVal` subtypes, `DTHelper`, `DTBlob` |
| `test_boardinfo.py` | `BoardInfo` model, boardinfo XML components (Ethernet, I2C, SPI, Flash) |
| `test_component_lib.py` | `SopcComponentLib` XML loading, SCD lookup, `final_check_on_component` |
| `test_component_handlers.py` | All component handler classes — dispatch, Phase 1 removal, constructors |
| `test_sopcinfo.py` | `SopcInfoSystemLoader` — XML parsing into `AvalonSystem` |
| `test_qsys.py` | `QSysSystemLoader` — Qsys XML parsing |
| `test_parser_wrappers.py` | `boardinfo_xml.py`, `component_xml.py` |

These tests verify correctness of individual units. They are fast (< 1s total)
and run on every commit.

---

### Component tests (integration)

**Location:** `tests/integration/`  
**Run with:** `pytest tests/integration/`  
**What they test:** A real `.sopcinfo` file parsed end-to-end through the full
pipeline — loader → model → `recheck_components()` — and the resulting
`AvalonSystem` inspected for correct component types, counts, and structure.
No generator is involved; this tests Phase 1 only.

This is called a *component test* because it exercises real component handlers
against real IP descriptions from actual Quartus designs, rather than synthetic
stubs.

#### Fixtures

Real `.sopcinfo` files are committed to `tests/fixtures/`. They are treated as
read-only golden inputs and **must not be modified**.

| Fixture | Design | Coverage |
|---------|--------|----------|
| `cv_soc_system.sopcinfo` | Cyclone V SoC GHRD (rocketboards.org, GSRD 14.x) | HPS clocks (`ClockManagerV`), HPS bridges (`MultiBridge`), HPS peripherals (EMAC, USB, SDMMC, UART, I2C, SPI, GPIO), FPGA fabric basics |
| `a10_soc_system.sopcinfo` | Arria 10 SoC GHRD (rocketboards.org) | HPS clocks (`ClockManagerA10`), `DwGpio`, A10 HPS peripherals, updated bridge topology |
| `neek.sopcinfo` | NEEK reference design (matches `boardinfo_neek.xml`) | Nios II CPU, `TSEMonolithic`, `SICSgdma`, `SICEpcs`, `SICBridge` variants, PIO, JTAG UART, timers |
| `synthetic_vip.sopcinfo` | Hand-crafted | `VIPFrameBuffer`, `VIPMixer` |
| `synthetic_pcie.sopcinfo` | Hand-crafted | `PCIeRootPort` |
| `synthetic_labx.sopcinfo` | Hand-crafted | `LabXEthernet`, `USBHostControllerISP1xxx`, `SICLan91c111` |

Hand-crafted fixtures are minimal valid `.sopcinfo` XML — just enough to
exercise the relevant component handlers, not a complete design.

#### What is verified

- Parser completes without exception
- `recheck_components()` completes without exception
- Expected component types are present (e.g. `ClockManagerV` for CV HPS)
- Bridge removal produces the expected reduced component set
- Known instance names appear in the system

---

### Golden diff tests (system)

**Location:** `tests/golden/`  
**Run with:** `pytest tests/golden/`  
**Requires:** DTS text generator (`generators/dts.py`) — Phase 2.
**What they test:** Full pipeline — parse → recheck → generate → compare DTS
output byte-for-byte against reference output from the original Java tool.

#### Pre-requisites

1. Java tool JAR available (original `sopc2dts` from `wgoossens/sopc2dts`)
2. DTS text generator ported (Phase 2 gate item)
3. Reference `.dts` files generated once from the Java tool and committed to
   `tests/golden/`

#### Process

```
# Generate reference output once (run on Java tool)
java -jar sopc2dts.jar -i tests/fixtures/cv_soc_system.sopcinfo \
     -b boardinfo_neek.xml -o tests/golden/cv_soc_system_ref.dts

# Golden test compares Python output to reference
pytest tests/golden/test_golden_cv.py
```

#### Tolerance

DTS output is compared after normalising whitespace and stripping the timestamp
comment (which differs between runs). All other content must match exactly.

---

## Coverage gaps

The following components have no real-design fixture available and are covered
only by unit tests and hand-crafted synthetic fixtures:

- `LabXEthernet` — LabX Ethernet MAC (niche third-party)
- `USBHostControllerISP1xxx` — ISP116x/ISP1362 (legacy USB host)
- `SICLan91c111` — SMSC LAN91C111 (legacy Ethernet)
- `VIPFrameBuffer`, `VIPMixer` — video pipeline IP
- `PCIeRootPort` — PCIe in FPGA fabric

---

## Running tests

```bash
# Unit tests only (fast, no fixtures needed)
pytest tests/ --ignore=tests/integration --ignore=tests/golden

# Unit + component tests (requires fixture files in tests/fixtures/)
pytest tests/ --ignore=tests/golden

# All tests including golden diff (requires Phase 2 generator)
pytest tests/
```

---

## Adding fixtures

Before committing a new `.sopcinfo` fixture:

1. Verify it parses cleanly with the Python tool (no exceptions)
2. Verify the Java tool produces valid DTS output from it
3. Commit the `.sopcinfo` to `tests/fixtures/`
4. If the generator is available, commit the Java reference `.dts` to
   `tests/golden/`
5. Add an integration test in `tests/integration/test_<name>.py`
