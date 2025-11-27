# pyci-check Usage Guide

This document provides detailed usage instructions, advanced options, and configuration for pyci-check.

## Table of Contents

- [Command Reference](#command-reference)
- [CLI Options](#cli-options)
- [Configuration File](#configuration-file)
- [Virtual Environment Handling](#virtual-environment-handling)
- [Git Hooks](#git-hooks)
- [Advanced Usage](#advanced-usage)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)

## Command Reference

### `check [paths...]`

Execute all checks (syntax + import static analysis).

```bash
# Check entire project
pyci-check check

# Check specific directories
pyci-check check src/ tests/

# Check specific files
pyci-check check src/main.py

# Mix files and directories
pyci-check check src/ scripts/deploy.py tests/test_main.py
```

**Behavior**:
- Defaults to current directory (`.`) if no paths specified
- Supports multiple path arguments
- Paths can be files or directories
- Automatically recurses through directories for `.py` files
- Auto-excludes `.venv`, `__pycache__`, etc. (based on ruff config)

### `syntax [paths...]`

Check Python syntax only, using AST static analysis.

```bash
# Check syntax
pyci-check syntax

# Check syntax in specific directory
pyci-check syntax src/
```

**Features**:
- Fast and completely safe (does not execute code)
- Uses Python's built-in `ast.parse()`
- Parallel processing of all files
- Suitable for pre-commit hooks

### `imports [paths...]`

Check import dependencies only.

```bash
# Static analysis (default, does not execute code)
pyci-check imports

# Dynamic execution (actually loads modules)
pyci-check imports --i-understand-this-will-execute-code

# Check imports in specific directory
pyci-check imports src/
```

**Two Modes**:

1. **Static Analysis Mode** (default):
   - Uses `importlib.util.find_spec()` to check module existence
   - Does not execute code, completely safe
   - May not detect runtime errors (like missing env vars)

2. **Dynamic Execution Mode** (requires `--i-understand-this-will-execute-code`):
   - Actually loads and executes all modules
   - Detects runtime errors
   - ⚠️ Triggers side effects (file writes, network requests, etc.)

### `install-hooks`

Install Git hooks (uses append mode, won't overwrite existing hooks).

```bash
# Install pre-commit hook (default)
pyci-check install-hooks

# Install pre-push hook
pyci-check install-hooks --type pre-push
```

**Append Mode Explanation**:
- Uses markers `# >>> pyci-check start >>>` and `# <<< pyci-check end <<<`
- If hook file exists, appends pyci-check's block
- Preserves all other content (like black, mypy, ruff, etc.)
- If pyci-check block already exists, updates it (doesn't duplicate)

### `uninstall-hooks`

Remove pyci-check's Git hooks (preserves other hooks).

```bash
# Remove all pyci-check hooks
pyci-check uninstall-hooks
```

**Behavior**:
- Only removes content between `# >>> pyci-check start >>>` and `# <<< pyci-check end <<<`
- Preserves all other hooks (black, mypy, etc.)
- If only shebang and `set -e` remain after removal, deletes the hook file
- Warns if hook was not created by pyci-check

## CLI Options

### Global Options

These options work with all commands:

#### `--quiet`

Reduce output, only show errors.

```bash
pyci-check check --quiet
```

#### `--fail-fast`

Stop checking immediately on first error.

```bash
pyci-check check --fail-fast
```

**Use Cases**:
- Quick error discovery
- Save time in CI/CD
- Fast failure in Git hooks

#### `--timeout SECONDS`

Set timeout in seconds for import checking (default: 30).

```bash
pyci-check imports --timeout 60
```

**Note**:
- Only applies to dynamic import checking
- Timeout is treated as check failure

#### `--check-relative`

Forbid relative imports, treat them as errors.

```bash
pyci-check check --check-relative
```

**Example Errors**:
```python
# Will be flagged as errors
from . import module
from .. import parent_module
from .submodule import function
```

#### `--venv PATH`

Specify virtual environment path.

```bash
# Use .venv in current directory
pyci-check imports --venv .

# Use .venv in specified project
pyci-check imports --venv /path/to/project

# Use venv/ directory
pyci-check imports --venv venv
```

**Behavior**:
- `.` - Uses current directory's `.venv/`
- `/path/to/project` - Uses specified project's `.venv/`
- `venv` - Uses `venv/` directory

#### `--i-understand-this-will-execute-code`

Execute dynamic import checking (actually loads modules).

```bash
pyci-check imports --i-understand-this-will-execute-code
pyci-check check --i-understand-this-will-execute-code
```

**Safety Warning**:
- ⚠️ Loads and executes all module-level code
- ⚠️ May trigger side effects (file writes, network requests, system changes, etc.)
- ⚠️ Consumes system resources
- ✅ Only use in trusted projects

## Configuration File

pyci-check reads configuration from `pyproject.toml`.

### Basic Configuration

```toml
[tool.pyci-check]
# Language setting (default: en)
# Supported: "en" (English) | "zh_CN" (Simplified Chinese) | "zh_TW" (Traditional Chinese)
language = "en"

# Import check timeout in seconds (default: 30)
import-timeout = 30
```

### Virtual Environment Configuration

```toml
[tool.pyci-check]
# Virtual environment path (optional)
venv = "."  # Use .venv in current directory (recommended, suitable for uv)
```

**Priority** (highest to lowest):
1. CLI parameter `--venv`
2. `venv` in `pyproject.toml`
3. Auto-detect: Use `.venv/` in project root if it exists
4. Current Python environment (`sys.executable`)

### Auto-Integration with ruff Config

pyci-check automatically reads `[tool.ruff]` configuration:

```toml
[tool.ruff]
# src directories automatically added to PYTHONPATH
src = ["src", "tests"]

# Exclude directories and files (pyci-check auto-reads)
exclude = [".venv", "build", "dist"]
extend-exclude = ["experiments/", "*.egg-info"]
```

**Reading Behavior**:
- `exclude` and `extend-exclude` are automatically merged
- Supports directories (like `.venv`) and file patterns (like `*.egg-info`)
- `src` directories are automatically added to `PYTHONPATH`

## Virtual Environment Handling

### Auto-Detection

pyci-check detects virtual environments in the following priority order:

1. **CLI Parameter**: `--venv .`
2. **Config File**: `[tool.pyci-check] venv = "."`
3. **Auto-Detect**: `.venv/` in project root
4. **Current Environment**: `sys.executable`

### Using uv Virtual Environment

```bash
# Recommended: configure in pyproject.toml
[tool.pyci-check]
venv = "."
```

Or use CLI parameter:

```bash
pyci-check imports --venv .
```

## Git Hooks

### Pre-commit Hook

**Behavior**:
- Only checks **staged** `.py` files
- Executes syntax checking (fast and safe)
- Blocks commit on errors
- Fast failure (fail-fast)

**Installation**:
```bash
pyci-check install-hooks
```

### Coexisting with Other Hooks

pyci-check uses append mode and can coexist with other tools' hooks:

**Example**: Using black, mypy, and pyci-check together

```bash
#!/usr/bin/env bash
set -e

# black's hook
black --check .

# mypy's hook
mypy .

# >>> pyci-check start >>>
# pyci-check's hook
PY_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
if [ -n "$PY_FILES" ]; then
    pyci-check syntax $PY_FILES
fi
# <<< pyci-check end <<<
```

**Update/Remove**:
- Update: Running `install-hooks` again updates pyci-check block
- Remove: `uninstall-hooks` only removes pyci-check block, preserves other content

## Advanced Usage

### CI/CD Integration

#### GitHub Actions

```yaml
name: Python Checks

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install pyci-check
        run: pip install pyci-check

      - name: Check syntax
        run: pyci-check syntax

      - name: Check imports
        run: pyci-check imports --i-understand-this-will-execute-code
```

### Integration with Other Tools

#### With ruff

```bash
# Recommended check order
pyci-check check      # Syntax + import checking
ruff check --fix        # Lint + auto-fix
ruff format             # Format
```

## Performance Optimization

### Core Optimizations

pyci-check uses multiple optimization techniques for best performance:

1. **Read file only once**: Uses `ast.parse()` instead of `py_compile.compile()` (2x improvement)
2. **Set lookup**: Uses `frozenset` for O(1) lookup instead of O(n×m) string comparison (10-20x improvement)
3. **Config caching**: Uses `@lru_cache` to avoid repeated reads of `pyproject.toml`
4. **Parallel processing**: Uses `ThreadPoolExecutor`, auto-calculates optimal worker count (CPU cores × 2, max 32)
5. **Git hook mode**: Only checks staged/changed files

## Troubleshooting

### Common Issues

#### 1. Import Check Fails But Module Exists

**Cause**: Incorrect virtual environment path

**Solution**:
```bash
# Specify correct virtual environment
pyci-check imports --venv .

# Or configure in pyproject.toml
[tool.pyci-check]
venv = "."
```

#### 2. Hook Not Working After Installation

**Cause**: Hook file doesn't have execute permission

**Solution**:
```bash
# pyci-check auto-sets execute permission, but if not:
chmod +x .git/hooks/pre-commit
```

## Exit Codes

- `0`: All checks passed
- `1`: Errors found (blocks commit/push)

## See Also

- [README.md](../../README.md) - Project overview and quick start
- [VALIDATION.md](VALIDATION.md) - Detailed check documentation with examples
