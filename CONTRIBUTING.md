# Contributing to sopc2dts

## Development Setup

```bash
# Clone the repo
git clone https://github.com/LaurenceA4L/sopc2dts.git
cd sopc2dts

# Create and activate a virtual environment
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Install in editable mode (core only)
pip install -e .

# Install with GUI dependencies
pip install -e ".[gui]"

# Install with dev/test dependencies
pip install -e ".[dev]"

# Verify
sopc2dts --version
sopc2dts --help
```

## Running Tests

```bash
pytest tests/
```

## Project Structure

```
sopc2dts_py/        Python package (the port — this is where new work goes)
sopc2dts/           Original Java source (reference only, do not modify)
docs/PORTING.md     Phase-by-phase porting tracker
tests/              Pytest tests
tests/fixtures/     Sample .sopcinfo / .qsys files for testing
```

## Workflow

Work happens on feature branches, not directly on `main`.

```bash
git checkout -b feature/my-thing
# ... make changes ...
git push origin feature/my-thing
# open a pull request on GitHub
```

`main` is protected — all changes go through a PR.

## Code Style

- Python 3.10+
- Type hints on all public functions
- Each ported file carries both the original Walter Goossens copyright and the port copyright (see existing files for the header template)

## Before Submitting a PR

- [ ] `pytest tests/` passes
- [ ] New code has the standard file header (copyright + license)
- [ ] PORTING.md checkboxes updated if applicable
