# pyci-check

> **Language**: [English](#english) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

---

Fast Python syntax and import checker designed for CI/CD and Git hooks.

## Features

- ⚡ **High-performance parallel processing** - Uses ThreadPoolExecutor for concurrent checking
- 🔍 **Dual-layer checking**:
  - **Syntax checking** - AST static analysis, fast and completely safe
  - **Import checking** - Static analysis or dynamic execution to detect runtime errors
- 🎯 **Flexible scope** - Check entire project, specific directories, or specific files
- 🔧 **Auto-integrates ruff config** - Reads exclude and src settings from `pyproject.toml`
- 🪝 **Git hooks support** - Append mode, won't overwrite existing hooks
- 📦 **Zero external dependencies** - Uses only Python standard library
- ⚠️ **Explicit consent** - Dynamic import checking requires explicit flag
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
# Check entire project (syntax + static import analysis)
pyci-check check

# Check syntax only
pyci-check syntax

# Check imports (static, safe)
pyci-check imports

# Check imports (dynamic, executes code)
pyci-check imports --i-understand-this-will-execute-code
```

### Check Specific Files or Directories

```bash
# Check specific files
pyci-check check src/main.py tests/test_main.py

# Check specific directories
pyci-check check src/ tests/

# Mix files and directories
pyci-check check src/ scripts/deploy.py
```

### Git Hooks Integration

```bash
# Install pre-commit hook (default)
pyci-check install-hooks

# Install pre-push hook
pyci-check install-hooks --type pre-push

# Remove pyci-check hooks (preserves other hooks)
pyci-check uninstall-hooks
```

**Note**: `install-hooks` uses append mode and won't overwrite your existing hooks (like black, mypy, etc.).

## Main Commands

- `check [paths...]` - Execute all checks (syntax + import static analysis)
- `syntax [paths...]` - Check Python syntax only
- `imports [paths...]` - Check import dependencies only
- `install-hooks` - Install Git hooks (append mode)
- `uninstall-hooks` - Remove pyci-check's Git hooks

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
