# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Persistent worker pool for execute mode (multi-worker fan-out)
- find_spec cache invalidation by dist-info mtime instead of whole sys.path

## [0.2.0] - 2026-05-07

This release is a substantial overhaul of the import-checking core, focused on
**correctness** (no longer triggers user `__init__.py` side effects), **safety**
(persistent-worker isolation, sandboxed env), and **performance** (cold-run
~50% faster on a medium repo). Static-mode behavior is intentionally redefined:
it now answers "can this module be located?" and never executes user code,
leaving "does it import successfully?" to `--i-understand-this-will-execute-code`.

### Highlights

- **No more accidental code execution in static mode.** The previous
  implementation called `importlib.util.find_spec` on every module name; for
  dotted names (`a.b.c`) Python's importer is documented to import the parent
  package, executing its `__init__.py`. Real-world example: scanning a Sanic /
  free-threading project would deadlock under thread parallelism due to module
  locks held during partial init. v0.2.0 replaces find_spec with a 4-layer
  filesystem probe that never invokes any importer.

- **`pyci-check imports --i-understand-this-will-execute-code` is now ~7×
  faster.** Replaced "fork one Python subprocess per module" with a single
  persistent worker speaking a line protocol over stdin/stdout. Measured on
  30 stdlib modules: 273ms → 36ms.

- **Cross-run caching.** Static-mode results are persisted at
  `<project>/.pyci-check-cache/find_spec.json`, keyed by a sha256 of the
  effective sys.path entries and their mtimes. Cache invalidates automatically
  when `pip install`, venv switch, or `.pth` file changes touch any path.

- **Python 3.13t (free-threaded) detection.** When Py_GIL_DISABLED is set, the
  ThreadPool path becomes truly parallel and benefits all repository sizes.
  On regular GIL builds, small projects (<200 files) skip the pool entirely
  to avoid thread bootstrap overhead that exceeded the actual work.

### Added

- **4-layer static probe** in `check_module_importable_static` — replaces
  `importlib.util.find_spec`:
  - L1 stdlib via `sys.stdlib_module_names` (Python 3.10+)
  - L2 installed third-party via `importlib.metadata.packages_distributions()`
    plus a site-packages directory listing fallback (catches editable installs,
    namespace packages, missing `top_level.txt`)
  - L3 project-local probe walking `project_dir` and `src_dirs` for the dotted
    leaf, with full namespace-package support (PEP 420)
  - L4 sys.path probe (with optional `extra_paths`) covering `.pth`-injected
    paths and modern editable installs; recognizes `.py` and platform-specific
    C extensions via `importlib.machinery.EXTENSION_SUFFIXES`
- **`_PersistentImportWorker`**: single Python subprocess validates many
  modules over a line protocol; reader thread + bounded queue gives per-module
  timeout on Windows and Unix
- **`_FindSpecCache`**: process-spanning cache for static-mode results,
  signed by sys.path content + mtimes
- **`--venv` is now respected by static mode**: previous versions read the
  current process's `sys.path` regardless of `--venv`; now resolves the
  external venv's site-packages and feeds them to the L4 probe
- **Free-threading awareness**: `utils.IS_FREE_THREADED` and
  `utils.should_use_thread_pool(n, "cpu" | "io")` adapt parallelism strategy
  based on Py_GIL_DISABLED and task count
- **`utils.walk_python_files`**: shared file-walking helper used by both
  syntax and imports checks; uses `os.walk(followlinks=False)` and prunes
  excluded directories during traversal (no post-walk filtering)
- **TYPE_CHECKING-aware AST visitor**: imports inside
  `if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:` are skipped (they don't
  execute at runtime)
- **Optional-import detection**: imports wrapped in `try / except
  ImportError` (or `ModuleNotFoundError`, tuple forms, bare except) are
  marked `optional`; missing optional modules no longer fail the check
- **`tests/test_static_no_side_effects.py`** (15 new tests) — regression
  fence for "static mode must not execute user `__init__.py`", TYPE_CHECKING
  handling, optional-import handling, namespace packages, C extension
  recognition, and `--venv` propagation

### Changed

- **`syntax.find_python_files` and `imports.extract_from_all_files`** both
  share `walk_python_files`; removed duplicate glob/walk paths and the
  per-file `_has_symlink_in_path` post-filter (`os.walk(followlinks=False)`
  handles symlinks correctly during traversal)
- **`ImportVisitor` no longer extends `ast.NodeVisitor`**: the previous
  `generic_visit` traversal walked every AST node (~94k visits on a 220-file
  repo). New implementation walks only statement containers via a
  type-keyed dispatch dict; no expression nodes are visited. AST-walk time
  dropped from ~50ms to negligible on the same repo.
- **`check_files_parallel` is now adaptive**: uses ThreadPool for >=200
  files (or any count on free-threaded builds), runs serially otherwise to
  avoid thread bootstrap overhead exceeding the work
- **Sandbox env construction extracted** into `_build_sandbox_env`,
  shared by `check_module_importable` (one-shot) and the persistent-worker
  branch in `check_missing_modules`

### Fixed

- **`PYTHONINSPECT="0"` regression on Python 3.14+**. Previous versions set
  `PYTHONINSPECT="0"` in the sandbox subprocess, intending to disable
  interactive mode. Python 3.14 changed the parsing rule: any non-empty
  string now enables interactive mode (3.13 had a special case for `"0"`).
  The result on 3.14 was that every `import` check terminated with a
  `SystemExit: 0` traceback and a non-zero return code, making `pyci-check
  imports --i-understand-this-will-execute-code` report every module as
  failed. Fix: `pop("PYTHONINSPECT")` instead of setting it
- **`ImportVisitor` traversal performance**: previously walked every AST
  node via `generic_visit`; now skips expression subtrees entirely
- **AST visitor's exception-class catching**: import-check subprocess script
  now catches `BaseException` so a module-level `sys.exit()` is reported as
  a failure rather than silently passing
- **find_python_files walked into `.venv-ft`, `.gitnexus`, etc.** when not
  in the default exclude set. New `walk_python_files` skips dot-prefixed
  directories during traversal, matching `glob`'s default-hidden behavior

### Removed

- **`find_spec` is no longer used in static mode.** The function and the
  surrounding `sys.path`-mutation try/finally are gone. Behavior change:
  static mode now reports "module found" if the **top-level** package is
  installed; deep-validating that `from foo.bar.baz import X` resolves
  requires `--i-understand-this-will-execute-code`. This matches what
  static mode could honestly verify without code execution.
- **`syntax._has_symlink_in_path`**: dead after switching to
  `os.walk(followlinks=False)`

### Performance (measured against [enoract](https://github.com/coseto6125/enoract), 220 .py files)

| Operation | v0.1.6 | v0.2.0 | Δ |
|---|---|---|---|
| `pyci-check syntax` | 248ms | 155ms | -38% |
| `pyci-check imports` (cold cache) | 405ms | 180ms | **-56%** |
| `pyci-check imports` (warm cache) | 405ms | 180ms | -56% |
| `pyci-check imports --i-understand-this-will-execute-code` (microbench, 30 modules) | 273ms | 36ms | **7.6x** |
| AST visit count per `imports` run | 94,330 | 0 | -100% |

### Migration notes

- **Static mode is stricter about its scope**: if your project relied on
  pyci-check static mode catching "imported submodule does not exist on the
  installed package", it no longer does. This was always best-effort under
  `find_spec` (which would re-import parent packages and surface their
  `ImportError`). Use `--i-understand-this-will-execute-code` for full
  runtime validation.
- **`--venv` now actually affects static mode.** Previous versions silently
  ignored `--venv` for static mode. Any CI invocation that passed `--venv`
  but relied on the current-process sys.path will now see results consistent
  with the chosen interpreter.
- **`.pyci-check-cache/` directory** is created in the project root.
  Add it to `.gitignore` if you don't want it tracked. The cache is safe to
  delete at any time.
- **API additions** — these are new keyword args; existing positional /
  keyword call sites are unchanged:
  - `check_module_importable_static(..., extra_paths=None)`
  - `import_info` dicts include a new `optional: bool` field

## [0.1.6] - 2025-11-27

### Added
- **Configuration**: Support `extend-exclude` in `[tool.pyci-check]` configuration
  - Merges with `exclude` settings from both `[tool.pyci-check]` and `[tool.ruff]`
  - Merge priority: pyci-check exclude → pyci-check extend-exclude → ruff exclude → ruff extend-exclude
  - Allows more flexible exclusion patterns without overriding base configuration

### Changed
- **Error Display**: Error messages now always displayed even in quiet mode
  - Import errors, syntax errors, and relative import warnings bypass `--quiet` flag
  - Ensures critical issues are never silently hidden
  - Only informational messages (statistics, progress) are suppressed in quiet mode

### Fixed
- **Error Handling**: Fix `total_errors` uninitialized warning in `print_results()`
- **Type Safety**: Improve type checking in test cases for better code reliability

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

[Unreleased]: https://github.com/coseto6125/pyci-check/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/coseto6125/pyci-check/compare/v0.1.6...v0.2.0
[0.1.6]: https://github.com/coseto6125/pyci-check/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/coseto6125/pyci-check/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/coseto6125/pyci-check/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/coseto6125/pyci-check/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/coseto6125/pyci-check/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/coseto6125/pyci-check/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/coseto6125/pyci-check/releases/tag/v0.1.0
