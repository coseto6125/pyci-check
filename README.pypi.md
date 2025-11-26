# pyci-check

Fast Python syntax and import checker designed for CI/CD and Git hooks.

## Features

- ⚡ **High-performance parallel processing** - Uses ThreadPoolExecutor
- 🔍 **Dual-layer checking** - Syntax (AST) + Import (static/dynamic)
- 🎯 **Flexible scope** - Check entire project, directories, or specific files
- 🔧 **Auto-integrates ruff config** - Reads from `pyproject.toml`
- 🪝 **Git hooks support** - Append mode, preserves existing hooks
- 📦 **Zero external dependencies** - Uses only Python standard library
- 🌐 **Multi-language** - English, Traditional Chinese, Simplified Chinese

## Installation

```bash
pip install pyci-check
```

Or with uv:

```bash
uv pip install pyci-check
```

## Quick Start

```bash
# Check entire project (syntax + import static analysis)
pyci-check check .

# Check syntax only
pyci-check syntax

# Check imports (static, safe)
pyci-check imports

# Install Git pre-commit hook
pyci-check install-hooks
```

## Main Commands

- `check [paths...]` - Run all checks (syntax + import)
- `syntax [paths...]` - Check Python syntax only
- `imports [paths...]` - Check import dependencies only
- `install-hooks` - Install Git hooks (append mode)
- `uninstall-hooks` - Remove pyci-check's Git hooks

## Common Options

- `--quiet` - Reduce output
- `--fail-fast` - Stop on first error
- `--venv PATH` - Specify virtual environment
- `--i-understand-this-will-execute-code` - Enable dynamic import checking

## Configuration

Configure in `pyproject.toml`:

```toml
[tool.pyci-check]
language = "en"  # or "zh_TW", "zh_CN"
import-timeout = 30

# Auto-reads ruff config
[tool.ruff]
src = ["src", "tests"]
exclude = [".venv", "build", "dist"]
```

## Documentation

Full documentation available on GitHub:

- **[Full README](https://github.com/coseto6125/pyci-check#readme)** - Complete guide with examples
- **[Usage Guide](https://github.com/coseto6125/pyci-check/blob/main/docs/en/USAGE.md)** - Detailed usage and configuration
- **[Validation Docs](https://github.com/coseto6125/pyci-check/blob/main/docs/en/VALIDATION.md)** - Check documentation with examples
- **[中文文档](https://github.com/coseto6125/pyci-check/blob/main/README.zh-TW.md)** - Traditional Chinese
- **[简体中文](https://github.com/coseto6125/pyci-check/blob/main/README.zh-CN.md)** - Simplified Chinese

## CI/CD Integration

### GitHub Actions

```yaml
- name: Check Python syntax and imports
  run: |
    pip install pyci-check
    pyci-check check .
```

### With ruff

```bash
pyci-check check .      # Syntax + import checking
ruff check --fix        # Lint + auto-fix
ruff format             # Format
```

## License

MIT License

## Links

- **Homepage**: https://github.com/coseto6125/pyci-check
- **Documentation**: https://github.com/coseto6125/pyci-check/blob/main/docs/en/USAGE.md
- **Bug Reports**: https://github.com/coseto6125/pyci-check/issues
- **Changelog**: https://github.com/coseto6125/pyci-check/releases
