# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Additional test coverage
- Performance benchmarks

## [0.1.5] - 2025-11-27

### Fixed
- **Critical Bug**: Fix exclude directories not being applied when checking imports
  - `find_python_files` was using default exclude set instead of ruff config
  - Now correctly passes `ignore_dirs` from ruff/pyci-check configuration
  - Resolves issue where excluded directories (e.g., experiments) were still being checked

## [0.1.4] - 2025-11-27

### Added
- **Statistics Display**: Show failed module count and total error count after import check
  - Added summary section showing `Failed modules: X` and `Total errors: Y`
  - Applied to both CLI mode and standalone mode
- **Exclude Configuration**: Display excluded directories and files in import check output
  - Show which directories and files are being excluded from checks
  - Helps users understand what is being skipped
- **pyci-check Configuration**: Support reading exclude settings from `[tool.pyci-check]`
  - Merges exclude settings from both `[tool.pyci-check]` and `[tool.ruff]`
  - Allows project-specific import check exclusions separate from linting

### Changed
- **i18n**: Added new translation keys for statistics and exclude display
  - `imports.exclude_dirs` and `imports.exclude_files`
  - `imports.summary.failed_modules` and `imports.summary.total_errors`
  - `imports.standalone.summary_total_errors`
  - Updated all locale files (en, zh_TW, zh_CN)

## [0.1.3] - 2025-11-27

### Changed
- **Documentation**: Update all examples to remove unnecessary `.` parameter
  - `pyci-check check` now the recommended way instead of `pyci-check check .`
  - Parameter `.` is still supported but not required (current directory is default)
  - Updated all README files, documentation, and CONTRIBUTING.md

## [0.1.2] - 2025-11-27

### Fixed
- **i18n**: Migrate all hardcoded error messages to use translation system
  - Import error messages now support multi-language (en/zh_TW/zh_CN)
  - Syntax error messages now support multi-language (en/zh_TW/zh_CN)
  - Removed misleading `--no-sandbox` hint from error messages
  - Updated test cases to use translation function for consistency

## [0.1.1] - 2024-11-27

### Added
- **LICENSE**: MIT License file
- **CONTRIBUTING.md**: Contribution guidelines with multi-language support (en/zh_TW/zh_CN)
- **Dev Dependencies**: Added `[project.optional-dependencies]` with pytest, pytest-cov, and ruff

### Changed
- **Installation Order**: Updated all README files to prioritize `uv add` over `uv pip install`
- **Documentation**: Improved pyproject.toml comments for exclude configuration
- **Documentation**: Completed English and Simplified Chinese translations

### Fixed
- **Ruff Configuration**: Added S603 exception for test files (subprocess usage)

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

[Unreleased]: https://github.com/coseto6125/pyci-check/compare/v0.1.5...HEAD
[0.1.5]: https://github.com/coseto6125/pyci-check/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/coseto6125/pyci-check/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/coseto6125/pyci-check/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/coseto6125/pyci-check/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/coseto6125/pyci-check/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/coseto6125/pyci-check/releases/tag/v0.1.0
