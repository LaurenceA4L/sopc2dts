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

`.sopcinfo` files are committed to `tests/fixtures/`. They are treated as
read-only golden inputs and **must not be modified**.

| Fixture | Design | Coverage |
|---------|--------|----------|
| `neek.sopcinfo` | **Synthetic** Nios II system (instance names match `boardinfo_neek.xml`) | `altera_nios2_qsys` CPU, `altera_avalon_cfi_flash`, `altera_avalon_new_sdram_controller`, `altera_avalon_onchip_memory2`, `opencores_i2c_master`, `altera_avalon_jtag_uart`, clock source, avalon/reset/interrupt connections |
| `cv_soc_ghrd.sopcinfo` | **Synthetic** Cyclone V SoC GHRD-style system | `altera_hps` (→ `BasicComponent`/group=ignore), `arm_gic` (→ `CortexA9GIC`), `lw_h2f_hps_bridge_avalon` (→ `MultiBridge` + `_f2h` split), dual `altera_avalon_pio`, `altera_avalon_sysid_qsys`, IRQ wiring, HPS LW master connections |

All current fixtures are hand-crafted synthetic files — valid `.sopcinfo` XML
authored for this project to exercise specific component handlers and connection
patterns, not exports from real Quartus builds. See
[Third-Party Acknowledgements](#third-party-acknowledgements) below.

Future fixtures to acquire (real Quartus outputs, not yet committed):

| Fixture | Design | Needed for |
|---------|--------|------------|
| `cv_soc_system.sopcinfo` | Cyclone V SoC GHRD (rocketboards.org, GSRD 14.x) | `ClockManagerV`, full HPS peripheral set |
| `a10_soc_system.sopcinfo` | Arria 10 SoC GHRD (rocketboards.org) | `ClockManagerA10`, `DwGpio`, A10 bridge topology |

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

The following components are covered only by unit tests (`test_component_handlers.py`).
No fixture (synthetic or real) has been written for them yet:

- `LabXEthernet` — LabX Ethernet MAC (niche third-party)
- `USBHostControllerISP1xxx` — ISP116x/ISP1362 (legacy USB host)
- `SICLan91c111` — SMSC LAN91C111 (legacy Ethernet)
- `VIPFrameBuffer`, `VIPMixer` — video pipeline IP
- `PCIeRootPort` — PCIe in FPGA fabric
- `ClockManagerV`, `ClockManagerA10` — require real HPS sopcinfo (SCD from Quartus IP, not bundled)

---

## Third-Party Acknowledgements

### Fixture files

All `.sopcinfo` fixture files in `tests/fixtures/` are **original works created
for this project**. No content was copied from any external repository.

The files are valid instances of Intel/Altera's `EnsembleReport` XML schema —
the format generated by Intel Quartus Prime's Qsys subsystem designer. Component
class names (e.g. `altera_nios2_qsys`, `altera_avalon_cfi_flash`, `arm_gic`)
are Intel/Altera IP identifiers. Their use in test fixtures to exercise a
format-compatible parser is considered fair use.

### Repositories consulted for format reference

The following public repositories were examined during development to understand
the `EnsembleReport` XML structure and real-world component/connection patterns.
**No content was copied from any of them.**

| Repository | Notes | License |
|-----------|-------|---------|
| [TJLW/DE0_NANO_SOC_GHRD](https://github.com/TJLW/DE0_NANO_SOC_GHRD) | DE0-Nano SoC GHRD export from Terasic system CF | No LICENSE file committed; content originates from Terasic's GHRD distribution |
| [ditek/soc_system_RT](https://github.com/ditek/soc_system_RT) | Cyclone V SoC real-time experiment | No LICENSE file committed |
| [Roboy/roboy_de10_nano_soc](https://github.com/Roboy/roboy_de10_nano_soc) | DE10-Nano SoC project | Consulted for connection topology patterns |
| [rsarwar87/altera-soc-rootfs](https://github.com/rsarwar87/altera-soc-rootfs) | Altera SoC rootfs build | Consulted for sopcinfo schema confirmation |

Because no content was extracted from these repositories, **no licence
obligations arise** from their consultation. If real `.sopcinfo` files from any
of these projects are added as fixtures in future, the applicable licence must be
reviewed at that point.

### Intel Quartus sopcinfo format

The `EnsembleReport` XML schema is documented in Intel's Embedded Design Suite
and GSRD (Golden System Reference Design) documentation. No Intel-owned artefacts
are included in this repository.

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
