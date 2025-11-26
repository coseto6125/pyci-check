# pyci-check Validation Documentation

This document details what pyci-check validates and provides examples of various error types.

## Table of Contents

- [Syntax Checking](#syntax-checking)
- [Import Checking](#import-checking)
- [Relative Import Checking](#relative-import-checking)
- [Error Message Format](#error-message-format)

## Syntax Checking

Syntax checking uses Python's built-in AST (Abstract Syntax Tree) parser to detect all Python syntax errors.

### How It Works

```python
import ast

with open(file_path, encoding="utf-8") as f:
    source = f.read()
    ast.parse(source, filename=file_path)
```

### Common Syntax Errors

#### 1. Indentation Error

```python
# ❌ Error: Inconsistent indentation
def hello():
    print("Hello")
      print("World")  # Too much indentation
```

**Error Message**:
```
src/example.py: unexpected indent (example.py, line 3)
```

#### 2. Unclosed Parenthesis

```python
# ❌ Error: Missing closing parenthesis
result = calculate(
    a, b, c
# Missing )
```

**Error Message**:
```
src/example.py: '(' was never closed (example.py, line 2)
```

#### 3. Invalid Syntax

```python
# ❌ Error: print statement (Python 2 syntax)
print "Hello"

# ❌ Error: Missing colon
def hello()
    pass

# ❌ Error: Invalid variable name
1st_variable = 10
```

**Error Messages**:
```
src/example.py: Missing parentheses in call to 'print'
src/example.py: invalid syntax
src/example.py: invalid decimal literal
```

#### 4. Unterminated String

```python
# ❌ Error: Missing closing quote
message = "Hello World
print(message)
```

**Error Message**:
```
src/example.py: unterminated string literal
```

### Syntax Checking Features

- ✅ **Fast**: Uses AST parsing, much faster than actual execution
- ✅ **Safe**: Does not execute code, no side effects
- ✅ **Complete**: Catches all syntax errors
- ✅ **Parallel**: Uses ThreadPoolExecutor to check all files in parallel
- ✅ **Accurate**: Shows exact file path, line number, and error message

### What Is NOT Checked

Syntax checking does **NOT** check:
- ❌ Logic errors (like infinite loops)
- ❌ Type errors (use mypy)
- ❌ Style issues (use ruff)
- ❌ Unused variables (use ruff)
- ❌ Import errors (use `pyci-check imports`)

## Import Checking

Import checking validates that all import statements are correct and modules exist and can be loaded.

### Checking Methods

pyci-check provides two checking modes:

#### 1. Static Analysis Mode (Default)

Uses `importlib.util.find_spec()` to check if modules exist without executing code.

```bash
pyci-check imports
```

**Features**:
- ✅ Completely safe (does not execute code)
- ✅ Fast
- ⚠️ May not detect runtime errors

**Logic**:
1. Use `find_spec()` to check if module exists
2. If not found, try filesystem lookup (relative imports)
3. Report error if both fail

#### 2. Dynamic Execution Mode

Actually loads and executes modules to detect runtime errors.

```bash
pyci-check imports --i-understand-this-will-execute-code
```

**Features**:
- ✅ Detects runtime errors (missing env vars, circular imports, etc.)
- ⚠️ Executes code (may have side effects)
- ⚠️ Slower

### Common Import Errors

#### 1. Module Does Not Exist

```python
# ❌ Error: Module does not exist
import nonexistent_module
from fake_package import something
```

**Error Message (Static)**:
```
src/example.py:1: import nonexistent_module
  Module 'nonexistent_module' cannot be imported: No module named 'nonexistent_module'
```

#### 2. Circular Import (Only detected in dynamic mode)

**module_a.py**:
```python
from module_b import b_function

def a_function():
    return b_function()
```

**module_b.py**:
```python
from module_a import a_function

def b_function():
    return a_function()
```

**Error Message (Dynamic)**:
```
src/module_a.py:1: from module_b import b_function
  Import failed: cannot import name 'b_function' from partially initialized module 'module_b'
```

**Note**: Static analysis mode may not detect this error.

#### 3. Package Not Installed

```python
# ❌ Error: Package not installed in current environment
import numpy
import pandas
```

**Error Message**:
```
src/example.py:1: import numpy
  Module 'numpy' cannot be imported: No module named 'numpy'
```

**Solutions**:
- Install missing package: `pip install numpy`
- Use correct virtual environment: `pyci-check imports --venv .`

### Import Checking Features

#### Static Analysis Mode

- ✅ **Safe**: Does not execute code
- ✅ **Fast**: Only uses `find_spec()`
- ✅ **Suitable for**: Daily development, pre-commit hooks
- ⚠️ **Limitation**: Cannot detect runtime errors

#### Dynamic Execution Mode

- ✅ **Complete**: Detects all import errors (including runtime)
- ✅ **Accurate**: Actually loads modules
- ✅ **Suitable for**: CI/CD, pre-release checks
- ⚠️ **Side effects**: Executes module-level code
- ⚠️ **Slower**: Needs to actually load all modules

## Relative Import Checking

When using the `--check-relative` option, pyci-check will forbid relative imports.

### How to Enable

```bash
pyci-check check . --check-relative
```

Or configure in `pyproject.toml`:

```toml
[tool.pyci-check]
allow-relative-imports = false
```

### Relative Import Examples

#### ❌ Forbidden Relative Imports

```python
# Import from current package
from . import module
from .module import function
from . import *

# Import from parent package
from .. import parent_module
from ..parent import function
```

**Error Message**:
```
src/package/module.py:1: from . import module
  Relative import detected (relative imports are forbidden)
```

#### ✅ Allowed Absolute Imports

```python
# Use absolute imports
from package import module
from package.module import function
from package.subpackage import something
```

### Why Forbid Relative Imports?

**Advantages**:
- ✅ Clear, explicit paths
- ✅ Easier refactoring
- ✅ Avoids confusion
- ✅ Suitable for large projects

**Disadvantages**:
- ❌ Longer paths
- ❌ Requires `PYTHONPATH` or `src` directory setup

**Recommendations**:
- Small projects: Relative imports are OK
- Large projects: Recommend absolute imports
- Libraries: Recommend absolute imports

## Error Message Format

### Syntax Errors

```
<relative_path>: <error_message>
```

**Example**:
```
src/example.py: invalid syntax (example.py, line 10)
```

**Information Included**:
- File relative path
- Detailed error message
- Original filename
- Line number

### Import Errors

```
<relative_path>:<line_number>: <import_statement>
  <error_reason>
```

**Example (Static)**:
```
src/main.py:5: import nonexistent_module
  Module 'nonexistent_module' cannot be imported: No module named 'nonexistent_module'
```

**Example (Dynamic)**:
```
src/main.py:5: import broken_module
  Import failed: division by zero
```

**Information Included**:
- File relative path
- Line number
- Complete import statement
- Detailed error reason

## Check Summary Table

| Check Type | Command | Executes Code | Speed | Use Cases |
|------------|---------|---------------|-------|-----------|
| Syntax Check | `pyci-check syntax` | ❌ No | ⚡ Fast | pre-commit, CI/CD |
| Import Static | `pyci-check imports` | ❌ No | ⚡ Fast | Daily dev, pre-commit |
| Import Dynamic | `pyci-check imports --i-understand-this-will-execute-code` | ✅ Yes | 🐢 Slow | CI/CD, pre-release |
| Full Check (Static) | `pyci-check check .` | ❌ No | ⚡ Fast | Daily development |
| Full Check (Dynamic) | `pyci-check check . --i-understand-this-will-execute-code` | ✅ Yes | 🐢 Slow | CI/CD |

## Best Practices

### Development Phase

```bash
# Quick check (syntax + import static)
pyci-check check .
```

### Git Hooks

```bash
# pre-commit: Only syntax (fastest)
pyci-check syntax

# pre-push: Can add import static
pyci-check check .
```

### CI/CD

```bash
# Full check (including dynamic import)
pyci-check check . --i-understand-this-will-execute-code
```

### Before Release

```bash
# Full check + other tools
pyci-check check . --i-understand-this-will-execute-code
mypy .
ruff check .
pytest
```

## See Also

- [README.md](../../README.md) - Project overview and quick start
- [USAGE.md](USAGE.md) - Detailed usage and configuration
