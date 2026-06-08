# sopc2dts — Makefile
#
# Default target builds / installs the Python port.
# Java targets are retained for golden-diff testing only.
#
# Python targets:
#   make / make install   install in editable mode (pip install -e .[dev])
#   make venv             create .venv and install dev deps
#   make test             run pytest
#   make lint             run ruff (if installed)
#   make clean            remove Python build / cache artefacts
#
# Java / golden-diff targets:
#   make jar              build sopc2dts.jar from the original Java sources
#   make golden           run both tools on GOLDEN_INPUT, diff the outputs
#   make clean-java       remove Java .class files and sopc2dts.jar
#   make clean-all        clean everything (Python + Java)
#
# Golden diff usage:
#   make golden GOLDEN_INPUT=tests/fixtures/neek.sopcinfo
#   make golden GOLDEN_INPUT=tests/fixtures/cv_soc_system.sopcinfo GOLDEN_ARGS="-b boardinfo_neek.xml"

PYTHON       ?= python3
PIP          ?= pip
VENV         := .venv
VENV_PIP     := $(VENV)/bin/pip

GOLDEN_INPUT ?= tests/fixtures/neek.sopcinfo
GOLDEN_ARGS  ?=
GOLDEN_DIR   := /tmp/sopc2dts_golden

# ---------------------------------------------------------------------------
# Default — Python
# ---------------------------------------------------------------------------

.PHONY: all install venv test lint clean

all: install

install:
	$(PIP) install -e ".[dev]" --quiet

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip --quiet
	$(VENV_PIP) install -e ".[dev]" --quiet
	@echo "Virtualenv ready.  Activate with:  source $(VENV)/bin/activate"

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check sopc2dts_py/ || true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc"     -delete 2>/dev/null || true
	rm -rf build dist *.egg-info sopc2dts.egg-info .pytest_cache

# ---------------------------------------------------------------------------
# Java build (reference tool — golden diff only)
# ---------------------------------------------------------------------------

SOURCES = Sopc2DTS.java \
	sopc2dts/LogListener.java sopc2dts/Logger.java \
	sopc2dts/generators/AbstractSopcGenerator.java \
	sopc2dts/generators/DTBGenerator2.java \
	sopc2dts/generators/DTBHex32Generator.java \
	sopc2dts/generators/DTBHex8Generator.java \
	sopc2dts/generators/DTGenerator.java \
	sopc2dts/generators/DTSGenerator2.java \
	sopc2dts/generators/GeneratorFactory.java \
	sopc2dts/generators/GraphGenerator.java \
	sopc2dts/generators/KernelHeadersGenerator.java \
	sopc2dts/generators/SopcCreateHeaderFilesImitator.java \
	sopc2dts/generators/UBootHeaderGenerator.java \
	sopc2dts/gui/BasicComponentComboBoxModel.java \
	sopc2dts/gui/BasicComponentRenderer.java \
	sopc2dts/gui/BasicComponentListItem.java \
	sopc2dts/gui/BoardInfoPanel.java \
	sopc2dts/gui/boardinfo/BISComponentGroup.java \
	sopc2dts/gui/boardinfo/BISEthernet.java \
	sopc2dts/gui/boardinfo/BISFlash.java \
	sopc2dts/gui/boardinfo/BISGeneral.java \
	sopc2dts/gui/boardinfo/BISI2C.java \
	sopc2dts/gui/boardinfo/BISSpi.java \
	sopc2dts/gui/boardinfo/BISSubComponentTable.java \
	sopc2dts/gui/boardinfo/BoardInfoSubPanel.java \
	sopc2dts/gui/InputPanel.java \
	sopc2dts/gui/OutputPanel.java \
	sopc2dts/gui/Sopc2DTSGui.java \
	sopc2dts/gui/ThreadedLoadPanel.java \
	sopc2dts/lib/Bin2IHex.java \
	sopc2dts/lib/BoardInfo.java \
	sopc2dts/lib/SopcComponentLib.java \
	sopc2dts/lib/AvalonSystem.java \
	sopc2dts/lib/BasicElement.java \
	sopc2dts/lib/Connection.java \
	sopc2dts/lib/Parameter.java \
	sopc2dts/lib/boardinfo/BICDTAppend.java \
	sopc2dts/lib/boardinfo/BICEthernet.java \
	sopc2dts/lib/boardinfo/BICI2C.java \
	sopc2dts/lib/boardinfo/BICSpi.java \
	sopc2dts/lib/boardinfo/BoardInfoComponent.java \
	sopc2dts/lib/boardinfo/I2CSlave.java \
	sopc2dts/lib/boardinfo/SpiSlave.java \
	sopc2dts/lib/boardinfo/SpiSlaveMMC.java \
	sopc2dts/lib/components/BasicComponent.java \
	sopc2dts/lib/components/InterruptReceiver.java \
	sopc2dts/lib/components/Interface.java \
	sopc2dts/lib/components/MemoryBlock.java \
	sopc2dts/lib/components/SopcComponentDescription.java \
	sopc2dts/lib/components/arm/CortexA9GIC.java \
	sopc2dts/lib/components/altera/GenericTristateController.java \
	sopc2dts/lib/components/altera/PCIeCompiler.java \
	sopc2dts/lib/components/altera/PCIeRootPort.java \
	sopc2dts/lib/components/altera/SICEpcs.java \
	sopc2dts/lib/components/altera/SICLan91c111.java \
	sopc2dts/lib/components/altera/SICSgdma.java \
	sopc2dts/lib/components/altera/SICTrippleSpeedEthernet.java \
	sopc2dts/lib/components/altera/TSEMonolithic.java \
	sopc2dts/lib/components/altera/InterfaceGenerator.java \
	sopc2dts/lib/components/altera/A10InterfaceGenerator.java \
	sopc2dts/lib/components/altera/InterruptBridge.java \
	sopc2dts/lib/components/altera/InterruptLatencyCounter.java \
	sopc2dts/lib/components/altera/hps/ClockManager.java \
	sopc2dts/lib/components/altera/hps/ClockManagerV.java \
	sopc2dts/lib/components/altera/hps/ClockManagerA10.java \
	sopc2dts/lib/components/altera/hps/SocFpgaGateClock.java \
	sopc2dts/lib/components/altera/hps/SocFpgaPeripClock.java \
	sopc2dts/lib/components/altera/hps/SocFpgaPllClock.java \
	sopc2dts/lib/components/altera/hps/VirtualClockElement.java \
	sopc2dts/lib/components/base/ClockSource.java \
	sopc2dts/lib/components/base/FlashPartition.java \
	sopc2dts/lib/components/base/GpioController.java \
	sopc2dts/lib/components/base/SCDSelfDescribing.java \
	sopc2dts/lib/components/base/SICBridge.java \
	sopc2dts/lib/components/base/SICFlash.java \
	sopc2dts/lib/components/base/SICI2CMaster.java \
	sopc2dts/lib/components/base/SICEthernet.java \
	sopc2dts/lib/components/base/SICSpiMaster.java \
	sopc2dts/lib/components/base/SICUnknown.java \
	sopc2dts/lib/components/nxp/USBHostControllerISP1xxx.java \
	sopc2dts/lib/components/snps/DwGpio.java \
	sopc2dts/lib/devicetree/DTBlob.java \
	sopc2dts/lib/devicetree/DTElement.java \
	sopc2dts/lib/devicetree/DTNode.java \
	sopc2dts/lib/devicetree/DTProperty.java \
	sopc2dts/lib/devicetree/DTPropByteVal.java \
	sopc2dts/lib/devicetree/DTPropHexNumVal.java \
	sopc2dts/lib/devicetree/DTPropNumVal.java \
	sopc2dts/lib/devicetree/DTPropPHandleVal.java \
	sopc2dts/lib/devicetree/DTPropStringVal.java \
	sopc2dts/lib/devicetree/DTPropVal.java \
	sopc2dts/lib/uboot/UBootComponentLib.java \
	sopc2dts/lib/uboot/UBootLibComponent.java \
	sopc2dts/parsers/BasicSystemLoader.java \
	sopc2dts/parsers/qsys/QSysSubSystem.java \
	sopc2dts/parsers/qsys/QSysSystemLoader.java \
	sopc2dts/parsers/sopcinfo/SopcInfoAssignment.java \
	sopc2dts/parsers/sopcinfo/SopcInfoComponent.java \
	sopc2dts/parsers/sopcinfo/SopcInfoConnection.java \
	sopc2dts/parsers/sopcinfo/SopcInfoElement.java \
	sopc2dts/parsers/sopcinfo/SopcInfoElementIgnoreAll.java \
	sopc2dts/parsers/sopcinfo/SopcInfoElementWithParams.java \
	sopc2dts/parsers/sopcinfo/SopcInfoInterface.java \
	sopc2dts/parsers/sopcinfo/SopcInfoParameter.java \
	sopc2dts/parsers/sopcinfo/SopcInfoSystemLoader.java

CLASSES = $(SOURCES:.java=.class)

ifeq ($(wildcard git-version),)
	SOPC2DTS_VERSION = $(shell git describe --tags --dirty 2>/dev/null || echo dev)
else
	SOPC2DTS_VERSION = $(shell cat git-version)
endif

.PHONY: jar clean-java clean-all golden

jar: sopc2dts.jar

sopc2dts.jar: $(CLASSES) sopc_components_*.xml
	echo "Implementation-Version: $(SOPC2DTS_VERSION)" > manifest
	jar -cmef manifest Sopc2DTS sopc2dts.jar *.java *.class sopc2dts sopc_components_*.xml
	rm -f manifest

%.class: %.java
	javac $<

clean-java:
	rm -f $(CLASSES) manifest sopc2dts.jar

clean-all: clean clean-java

# ---------------------------------------------------------------------------
# Golden diff
# ---------------------------------------------------------------------------
# Runs the Java reference tool and the Python port on the same input, then
# diffs the results (whitespace-normalised).  Exits 0 if identical.
#
# Usage:
#   make golden
#   make golden GOLDEN_INPUT=tests/fixtures/cv_soc_system.sopcinfo
#   make golden GOLDEN_INPUT=... GOLDEN_ARGS="-b boardinfo_neek.xml --no-timestamp"

golden: sopc2dts.jar
	@echo "=== Golden diff: $(GOLDEN_INPUT) ==="
	@mkdir -p $(GOLDEN_DIR)
	java -jar sopc2dts.jar \
		-i $(GOLDEN_INPUT) $(GOLDEN_ARGS) --no-timestamp \
		-o $(GOLDEN_DIR)/java.dts
	$(PYTHON) -m sopc2dts_py \
		-i $(GOLDEN_INPUT) $(GOLDEN_ARGS) --no-timestamp \
		-o $(GOLDEN_DIR)/python.dts
	@echo "--- diff (whitespace-normalised) ---"
	diff <(tr -s ' \t' ' ' < $(GOLDEN_DIR)/java.dts) \
	     <(tr -s ' \t' ' ' < $(GOLDEN_DIR)/python.dts) \
	&& echo "PASS: outputs are identical" \
	|| (echo "FAIL: outputs differ (see $(GOLDEN_DIR))" && exit 1)
