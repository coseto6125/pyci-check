# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- English and Simplified Chinese translations for documentation
- Additional test coverage
- Performance benchmarks

## [0.1.0] - 2024-11-26

### Added
- Initial release
- **Syntax Checking**: AST-based Python syntax validation
- **Import Checking**: Two modes
  - Static analysis mode (safe, default)
  - Dynamic execution mode (detects runtime errors)
- **Path Support**: Check specific files or directories
- **Git Hooks**: Append-mode hook installation
  - Pre-commit hook support
  - Pre-push hook support
  - Preserves existing hooks
- **Multi-language Support**: English, Traditional Chinese, Simplified Chinese
- **Auto-integration**: Reads `ruff` configuration from `pyproject.toml`
- **Cross-platform**: Tested on Linux, macOS, Windows
- **Python Support**: Python 3.11, 3.12, 3.13
- **CLI Commands**:
  - `pyci-check check` - Run all checks
  - `pyci-check syntax` - Syntax checking only
  - `pyci-check imports` - Import checking only
  - `pyci-check install-hooks` - Install Git hooks
  - `pyci-check uninstall-hooks` - Remove Git hooks
- **Configuration**: Support for `pyproject.toml` configuration
- **Performance Optimizations**:
  - Parallel processing with ThreadPoolExecutor
  - Efficient file filtering
  - Smart caching

### Documentation
- Comprehensive README (English, Traditional Chinese, Simplified Chinese)
- Detailed usage guide (docs/*/USAGE.md)
- Validation documentation (docs/*/VALIDATION.md)
- CI/CD workflow documentation
- Release process documentation (docs/RELEASE.md)

### CI/CD
- GitHub Actions workflows:
  - Comprehensive CI testing (7 test categories)
  - Cross-platform testing (3 OS × 3 Python versions)
  - Automated release workflow
  - PyPI publishing support (Trusted Publisher)

[Unreleased]: https://github.com/coseto6125/pyci-check/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/coseto6125/pyci-check/releases/tag/v0.1.0
