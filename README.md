# pyci-check

> **Language**: [English](#english) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

---

Fast Python syntax, import, and architecture checker designed for CI/CD and Git hooks.

## Features

- ⚡ **High-performance parallel processing** - Uses ThreadPoolExecutor for concurrent checking
- 🛡️ **Architecture Defender**:
  - **Dependency Health** - Detects phantom (used but undeclared) and orphan (declared but unused) dependencies
  - **Import Cycles** - Graph-based detection of absolute and relative import cycles
  - **Side-Effects Scan** - Warns on dangerous top-level threading/network IO
  - **Deep Dead Code** - Project-wide scan for unused functions and classes
  - **Test Purity** (Opt-in) - Blocks network requests in unit tests to prevent flaky tests
- 🔍 **Dual-layer Import checking**:
  - **Static analysis** - Fast and completely safe
  - **Dynamic execution** - Detects runtime errors (requires explicit flag)
- 🔧 **Auto-integrates ruff config** - Reads exclude and src settings from `pyproject.toml`
- 🪝 **Strict Pre-commit Hook** - Runs local CI (ruff format -> ruff check -> pyci-check) before committing
- 🌐 **Multi-language** - Supports English, Traditional Chinese, Simplified Chinese

## Installation

```bash
pip install pyci-check
```

Or with uv (recommended):

```bash
# Preferred (adds to pyproject.toml)
uv add pyci-check

# Or direct install
uv pip install pyci-check
```

## Quick Start

### Basic Usage

```bash
# Execute full CI pipeline (Syntax -> Imports -> Dependency Health -> Cycles -> Side-effects -> Deadcode)
pyci-check check

# Check syntax only
pyci-check syntax

# Check import cycles
pyci-check cycles

# Check dependency health (Phantom & Orphan)
pyci-check dependency

# Check imports (static, safe)
pyci-check imports
```

### Git Hooks Integration

```bash
# Install strict pre-commit hook (runs ruff + pyci-check locally)
pyci-check install-hooks
```

## Main Commands

- `check [paths...]` - Execute all 6 validation phases
- `syntax [paths...]` - Check Python syntax
- `imports [paths...]` - Check import resolvability
- `dependency` - Check for phantom and orphan dependencies
- `cycles` - Detect import cycles
- `side-effects` - Warn on dangerous top-level operations
- `deadcode` - Warn on unused functions/classes
- `install-hooks` - Install local CI Git hooks

## Common Options

- `--quiet` - Reduce output messages
- `--fail-fast` - Stop immediately on first error
- `--timeout SECONDS` - Import check timeout in seconds (default: 30)
- `--check-relative` - Forbid relative imports (treat as errors)
- `--venv PATH` - Specify virtual environment path
- `--i-understand-this-will-execute-code` - Execute dynamic import checking (loads modules)

### Advanced Examples

```bash
# Check for relative imports
pyci-check check --check-relative

# Stop immediately on error
pyci-check check --fail-fast

# Set import timeout (seconds)
pyci-check imports --timeout 60

# Use specified virtual environment (supports uv .venv)
pyci-check imports --venv .
pyci-check imports --venv /path/to/project

# Quiet mode with full check
pyci-check check --quiet --i-understand-this-will-execute-code
```

## Important Safety Notes

**Dynamic import checking executes code**:
- ⚠️ Loads and executes all module-level code
- ⚠️ May trigger side effects (file writes, network requests, etc.)
- ⚠️ Consumes system resources
- ✅ Accurately detects runtime errors (missing env vars, dependency issues, etc.)

**Default is static analysis**:
- `pyci-check imports` - Uses static analysis, doesn't execute code (safe)
- `pyci-check imports --i-understand-this-will-execute-code` - Dynamic execution (requires explicit consent)

**Git hooks behavior**:
- pre-commit: Only checks syntax (fast and safe)
- pre-push: Optional dynamic import checking

## Configuration

Configure in `pyproject.toml`:

```toml
[tool.pyci-check]
# Language setting (default: en)
language = "en"  # or "zh_TW", "zh_CN"

# Enable strict test purity check (Blocks network/threading in tests)
check-test-purity = true

# Virtual environment path (optional)
# venv = "."  # Use .venv in current directory (recommended for uv)

# Import check timeout in seconds (default: 30)
import-timeout = 30
```

**Auto-integration with ruff config**:

pyci-check automatically reads `[tool.ruff]` settings for `exclude`, `extend-exclude`, and `src`. It's recommended to manage exclusion rules in ruff:

```toml
[tool.ruff]
# src directories automatically added to PYTHONPATH
src = ["src", "tests"]

# Exclude directories and files (pyci-check auto-reads)
exclude = [".venv", "build", "dist"]
extend-exclude = ["experiments/", "*.egg-info"]
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Check Python syntax and imports
  run: |
    pip install pyci-check
    pyci-check check  # Syntax + import static analysis
```

### Using with ruff

```bash
# Recommended check order
pyci-check check      # Syntax + import checking
ruff check --fix        # Lint + auto-fix
ruff format             # Format
```

## Documentation

- **[USAGE.md](docs/en/USAGE.md)** - Detailed usage guide, advanced options, and configuration
- **[VALIDATION.md](docs/en/VALIDATION.md)** - Validation checks documentation with examples

## License

MIT License
