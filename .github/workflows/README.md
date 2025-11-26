# GitHub Actions CI Workflow

This document describes the CI/CD pipeline for pyci-check.

## Workflow Overview

The CI pipeline is organized into the following categories:

### 1. Code Quality
- **Job**: `code-quality`
- **Platform**: Ubuntu Latest
- **Purpose**: Ensures code meets style and formatting standards
- **Checks**:
  - Ruff linting
  - Ruff formatting

### 2. Self Check
- **Job**: `self-check`
- **Platform**: Ubuntu Latest
- **Purpose**: Uses pyci-check to validate itself
- **Checks**:
  - Syntax check (AST parsing)
  - Import check (static analysis)
  - Import check (dynamic execution)
  - Full check (all checks combined)

### 3. Cross-Platform Tests
- **Job**: `test-cross-platform`
- **Platforms**: Ubuntu, macOS, Windows
- **Python Versions**: 3.11, 3.12, 3.13
- **Purpose**: Ensures compatibility across different OS and Python versions
- **Matrix**: 9 combinations (3 OS × 3 Python versions)
- **Coverage**: Uploads coverage report from Ubuntu + Python 3.13

### 4. Categorized Tests

Individual test suites run in parallel on Ubuntu:

#### 4.1 Syntax Checker Tests
- **Job**: `test-syntax`
- **Files**: `test_syntax.py`, `test_syntax_advanced.py`
- **Purpose**: Tests the AST-based syntax checker

#### 4.2 Import Checker Tests
- **Job**: `test-imports`
- **Files**: `test_imports.py`, `test_imports_advanced.py`
- **Purpose**: Tests both static and dynamic import checking

#### 4.3 Git Hooks Tests
- **Job**: `test-git-hooks`
- **Files**: `test_git_hooks.py`
- **Purpose**: Tests hook installation, update, and removal
- **Special**: Initializes a Git repository for testing

#### 4.4 CLI Interface Tests
- **Job**: `test-cli`
- **Files**: `test_cli.py`
- **Purpose**: Tests command-line interface and argument parsing

#### 4.5 I18n Tests
- **Job**: `test-i18n`
- **Files**: `test_i18n.py`
- **Purpose**: Tests internationalization (en, zh_CN, zh_TW)

#### 4.6 Utilities Tests
- **Job**: `test-utils`
- **Files**: `test_utils.py`
- **Purpose**: Tests utility functions

#### 4.7 Integration Tests
- **Job**: `test-integration`
- **Files**: `test_integration.py`
- **Purpose**: Tests end-to-end workflows

### 5. Type Checking
- **Job**: `type-check`
- **Platform**: Ubuntu Latest
- **Purpose**: Static type checking with mypy
- **Note**: Currently runs in permissive mode (does not fail CI)

### 6. Package Build
- **Job**: `build`
- **Platform**: Ubuntu Latest
- **Depends on**: `code-quality`, `self-check`, `test-cross-platform`
- **Purpose**: Builds the distribution package
- **Outputs**:
  - Wheel (.whl)
  - Source distribution (.tar.gz)
- **Validation**: Runs `twine check` on built packages
- **Artifacts**: Uploads to GitHub Actions artifacts

### 7. Package Installation Tests
- **Job**: `test-install`
- **Platforms**: Ubuntu, macOS, Windows
- **Depends on**: `build`
- **Purpose**: Verifies package can be installed on all platforms
- **Checks**:
  - Install from wheel
  - CLI availability (`pyci-check --help`)
  - Import verification

## Workflow Execution Flow

```
┌─────────────────┐
│  Code Quality   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│   Self Check    │     │  Type Checking   │
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Cross-Platform Tests (3×3 matrix)  │
│  Ubuntu / macOS / Windows            │
│  Python 3.11 / 3.12 / 3.13          │
└────────┬────────────────────────────┘
         │
         ├──► Categorized Tests (parallel)
         │    ├─ Syntax Checker
         │    ├─ Import Checker
         │    ├─ Git Hooks
         │    ├─ CLI Interface
         │    ├─ I18n
         │    ├─ Utilities
         │    └─ Integration
         │
         ▼
┌─────────────────┐
│  Package Build  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Package Installation Tests │
│  Ubuntu / macOS / Windows    │
└─────────────────────────────┘
```

## Test Triggers

The CI pipeline runs on:
- **Push** to `main` or `develop` branches
- **Pull requests** targeting `main` or `develop` branches

## Performance Optimizations

- **Parallel Execution**: Categorized tests run in parallel
- **Fail Fast**: Set to `false` for cross-platform tests to see all failures
- **Caching**: pip cache enabled for faster dependency installation
- **Matrix Strategy**: Cross-platform tests use matrix for efficiency

## Monitoring Test Results

### Success Criteria
All jobs must pass for the CI to be considered successful, except:
- `type-check`: Runs in permissive mode (does not block)

### Coverage Reports
Coverage is collected from:
- **Platform**: Ubuntu Latest
- **Python**: 3.13
- **Upload**: Codecov (if configured)

## Local Testing

To run tests locally that match CI:

```bash
# Code quality
ruff check .
ruff format --check .

# Self check
pyci-check syntax
pyci-check imports
pyci-check check .

# Run all tests
pytest tests/ -v --cov=src/pyci_check

# Run specific test category
pytest tests/test_syntax.py -v
pytest tests/test_imports.py -v
pytest tests/test_git_hooks.py -v
pytest tests/test_cli.py -v
pytest tests/test_i18n.py -v
pytest tests/test_utils.py -v
pytest tests/test_integration.py -v

# Type check
mypy src/pyci_check --ignore-missing-imports

# Build package
python -m build
twine check dist/*
```

## Adding New Tests

When adding new test files:

1. Create the test file in `tests/`
2. Add a new job in `.github/workflows/ci.yml` under "Categorized Tests"
3. Follow the naming convention: `test-<category>`
4. Update this README

Example:

```yaml
test-new-feature:
  name: Test New Feature
  runs-on: ubuntu-latest
  steps:
    - name: Checkout code
      uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.13"
        cache: 'pip'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest
        pip install -e .
    - name: Run new feature tests
      run: |
        pytest tests/test_new_feature.py -v
```
