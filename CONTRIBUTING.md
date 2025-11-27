# Contributing to pyci-check

> **Language**: [English](#english) | [繁體中文](docs/zh_TW/CONTRIBUTING.md) | [简体中文](docs/zh_CN/CONTRIBUTING.md)

---

Thank you for your interest in contributing to pyci-check! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version)
- Minimal code example if applicable

### Suggesting Enhancements

We welcome feature requests! Please create an issue with:
- Clear description of the proposed feature
- Use cases and benefits
- Potential implementation approach (optional)

### Pull Requests

1. **Fork the repository**
   ```bash
   gh repo fork coseto6125/pyci-check --clone
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Make your changes**
   - Write clear, readable code
   - Follow existing code style
   - Add tests for new features
   - Update documentation as needed

4. **Run tests**
   ```bash
   # Run all tests
   uv run pytest

   # Run specific test categories
   uv run pytest tests/test_syntax.py
   uv run pytest tests/test_imports.py

   # Run with coverage
   uv run pytest --cov=pyci_check
   ```

5. **Run code quality checks**
   ```bash
   # Syntax and import checks
   uv run pyci-check check

   # Linting
   uv run ruff check .

   # Formatting
   uv run ruff format .
   ```

6. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   # or
   git commit -m "fix: resolve issue with X"
   ```

   **Commit message format**:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `test:` - Test changes
   - `refactor:` - Code refactoring
   - `chore:` - Maintenance tasks

7. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   gh pr create --fill
   ```

## Development Setup

### Prerequisites

- Python 3.11, 3.12, or 3.13
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/coseto6125/pyci-check.git
   cd pyci-check
   ```

2. **Create virtual environment**
   ```bash
   # Using uv (recommended)
   uv venv
   source .venv/bin/activate  # Linux/macOS
   # or
   .venv\Scripts\activate  # Windows
   
   # Or using standard venv
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install in development mode**
   ```bash
   # Using uv (recommended - faster and more reliable)
   uv sync --extra dev

   # Or using pip
   pip install -e ".[dev]"
   ```

### Running Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/test_syntax.py

# With coverage report
uv run pytest --cov=pyci_check --cov-report=html
```

### Code Style

We use:
- **ruff** for linting and formatting
- **pyci-check** for syntax and import validation
- **pytest** for testing

Before submitting a PR, ensure:
```bash
uv run pyci-check check
uv run ruff check .
uv run ruff format .
uv run pytest
```

## Project Structure

```
pyci-check/
├── src/pyci_check/     # Main source code
│   ├── cli.py          # CLI interface
│   ├── syntax.py       # Syntax checking
│   ├── imports.py      # Import checking
│   ├── git_hook.py     # Git hooks functionality
│   ├── i18n.py         # Internationalization
│   └── locales/        # Language files
├── tests/              # Test suite
├── docs/               # Documentation
│   ├── en/            # English docs
│   ├── zh_TW/         # Traditional Chinese docs
│   └── zh_CN/         # Simplified Chinese docs
└── scripts/           # Utility scripts
```

## Documentation

When adding new features:
- Update relevant documentation in `docs/`
- Add docstrings to functions and classes
- Update `CHANGELOG.md`
- Consider adding examples to README

## Release Process

Releases are automated via GitHub Actions. Only maintainers can create releases:

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create and push tag: `git tag -a v0.x.0 -m "Release v0.x.0"`
4. Push tag: `git push origin v0.x.0`
5. GitHub Actions will automatically build and publish to PyPI

## Questions?

If you have questions, feel free to:
- Open an issue for discussion
- Check existing issues and PRs
- Read the documentation in `docs/`

Thank you for contributing! 🎉
