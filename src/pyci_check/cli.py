"""CLI 入口點."""

import argparse
import io
import os
import sys

# 確保 Windows 上的 stdout 使用 UTF-8 編碼
if sys.platform == "win32":
    if sys.stdout.encoding != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr.encoding != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pyci_check.cycles import find_import_cycles
from pyci_check.deadcode import scan_dead_code
from pyci_check.dependency import find_dependency_issues
from pyci_check.git_hook import install_hooks, uninstall_hooks
from pyci_check.i18n import t
from pyci_check.imports import (
    check_missing_modules,
    extract_from_all_files,
    get_ruff_config_from_pyproject,
    get_venv_from_pyproject,
)
from pyci_check.side_effects import detect_side_effects
from pyci_check.syntax import check_files_parallel, find_python_files
from pyci_check.utils import safe_relpath


def check_syntax(args: argparse.Namespace) -> int:
    """執行語法檢查."""
    paths = getattr(args, "paths", None) or ["."]

    python_files = []
    for path in paths:
        abs_path = os.path.abspath(path)

        if os.path.isfile(abs_path):
            if abs_path.endswith(".py"):
                python_files.append(abs_path)
        elif os.path.isdir(abs_path):
            python_files.extend(find_python_files(abs_path))
        else:
            print(f"⚠️  路徑不存在: {path}")
            return 1

    if not python_files:
        if not args.quiet:
            print(t("syntax.no_files"))
        return 0

    if not args.quiet:
        print(t("syntax.checking", len(python_files)))

    _success_count, _error_count, errors = check_files_parallel(python_files)

    if errors:
        for file_path, error_msg in errors:
            print(f"❌ {file_path}")
            print(f"   {error_msg}")
        return 1

    if not args.quiet:
        print(t("syntax.success"))
    return 0


def check_imports(args: argparse.Namespace) -> int:
    """執行 import 檢查."""
    paths = getattr(args, "paths", None) or ["."]
    project_path = os.getcwd()

    # 判斷使用靜態檢查還是真實執行
    use_static = not getattr(args, "i_understand_this_will_execute_code", False)

    ruff_config = get_ruff_config_from_pyproject(project_path)

    src_dirs = ruff_config["src"]
    ignore_dirs = set(ruff_config["exclude_dirs"])
    ignore_files = set(ruff_config["exclude_files"])

    # 取得 venv 路徑 (優先順序: CLI 參數 > pyproject.toml > 自動偵測 .venv)
    venv_path = getattr(args, "venv", None)

    if not venv_path:
        # 從 pyproject.toml 讀取
        venv_path = get_venv_from_pyproject(project_path)

    if not venv_path:
        # 自動偵測 .venv
        venv_dir = os.path.join(project_path, ".venv")
        if os.path.exists(venv_dir):
            venv_path = "."

    if not args.quiet:
        print(t("imports.checking"))
        if src_dirs:
            print(t("imports.pythonpath", ", ".join(src_dirs)))
        if venv_path:
            print(t("imports.venv", venv_path))
        if ignore_dirs:
            print(t("imports.exclude_dirs", ", ".join(sorted(ignore_dirs))))
        if ignore_files:
            print(t("imports.exclude_files", ", ".join(sorted(ignore_files))))

        # 顯示檢查模式
        if use_static:
            print(t("imports.mode_static"))
            print(t("imports.mode_static_hint"))
        else:
            print(t("imports.mode_execute"))
            print(t("imports.mode_execute_warning"))

    # 根據指定路徑收集檔案
    target_files = []
    for path in paths:
        abs_path = os.path.abspath(path)
        if os.path.isfile(abs_path):
            if abs_path.endswith(".py"):
                target_files.append(abs_path)
        elif os.path.isdir(abs_path):
            target_files.extend(find_python_files(abs_path, exclude_dirs=list(ignore_dirs)))

    all_imports, all_relative_imports = extract_from_all_files(
        project_path,
        ignore_dirs=ignore_dirs,
        ignore_files=ignore_files,
        target_files=target_files if target_files else None,
    )

    if args.check_relative and all_relative_imports:
        for rel_import in all_relative_imports:
            print(t("imports.relative_import_warning", rel_import["file"], rel_import["line"], rel_import["statement"]))
        return 1

    missing_modules = check_missing_modules(
        all_imports,
        project_dir=project_path,
        src_dirs=src_dirs,
        timeout=args.timeout,
        venv_path=venv_path,
        use_static=use_static,
    )

    if missing_modules:
        total_errors = 0
        for module, import_list in sorted(missing_modules.items()):
            for import_info in import_list:
                rel_path = safe_relpath(import_info["file"], project_path)
                error_msg = import_info.get("error", "Module not found")
                print(t("imports.module_failed", module))
                print(t("imports.file", rel_path, import_info["line"]))
                print(t("imports.statement", import_info["statement"]))
                print(t("imports.reason", error_msg))
                print()
                total_errors += 1

        # 顯示統計資訊
        if not args.quiet:
            print("=" * 60)
            print(t("imports.summary.failed_modules", len(missing_modules)))
            print(t("imports.summary.total_errors", total_errors))
            print("=" * 60)
        return 1

    if not args.quiet:
        print(t("imports.success"))
    return 0


def check_dependency(args: argparse.Namespace) -> int:
    """執行依賴健康度檢查."""
    project_path = os.getcwd()
    ruff_config = get_ruff_config_from_pyproject(project_path)
    ignore_dirs = set(ruff_config["exclude_dirs"])
    ignore_files = set(ruff_config["exclude_files"])
    src_dirs = ruff_config["src"]

    if not args.quiet:
        print(t("dependency.checking"))

    all_imports, _ = extract_from_all_files(
        project_path,
        ignore_dirs=ignore_dirs,
        ignore_files=ignore_files,
    )

    imported_modules = {imp["module"].split(".")[0] for imp in all_imports}

    # 本地模組名
    local_modules = set()
    python_files = find_python_files(project_path, exclude_dirs=list(ignore_dirs))
    roots = [project_path] + [os.path.join(project_path, s) for s in src_dirs]
    for fp in python_files:
        for root in roots:
            if fp.startswith(os.path.abspath(root)):
                rel = os.path.relpath(fp, root)
                local_modules.add(rel.split(os.sep)[0].removesuffix(".py"))

    issues = find_dependency_issues(project_path, imported_modules, local_modules)

    has_issues = False
    if issues["phantom"]:
        has_issues = True
        print(t("dependency.phantom"))
        for p in sorted(issues["phantom"]):
            print(f"  - {p}")

    if issues["orphan"]:
        # Orphan 視為警告，不一定導致 exit 1，但這裡我們先統一報出來
        print(t("dependency.orphan"))
        for p in sorted(issues["orphan"]):
            print(f"  - {p}")

    if not has_issues:
        if not args.quiet:
            print(t("dependency.success"))
        return 0
    return 1


def check_cycles(args: argparse.Namespace) -> int:
    """執行循環引用檢查."""
    project_path = os.getcwd()
    ruff_config = get_ruff_config_from_pyproject(project_path)
    ignore_dirs = set(ruff_config["exclude_dirs"])
    ignore_files = set(ruff_config["exclude_files"])
    src_dirs = ruff_config["src"]

    if not args.quiet:
        print(t("cycles.checking"))

    all_imports, all_relative_imports = extract_from_all_files(
        project_path,
        ignore_dirs=ignore_dirs,
        ignore_files=ignore_files,
    )

    cycles = find_import_cycles(all_imports, all_relative_imports, project_path, src_dirs)

    if cycles:
        print(t("cycles.found", len(cycles)))
        for i, cycle in enumerate(cycles, 1):
            rel_cycle = [safe_relpath(fp, project_path) for fp in cycle]
            print(f"  {i}. {' -> '.join(rel_cycle)}")
        return 1

    if not args.quiet:
        print(t("cycles.success"))
    return 0


def check_side_effects(args: argparse.Namespace) -> int:
    """執行全局副作用檢查 (僅警告)."""
    project_path = os.getcwd()
    ruff_config = get_ruff_config_from_pyproject(project_path)
    ignore_dirs = set(ruff_config["exclude_dirs"])
    check_test_purity = ruff_config.get("check_test_purity", False)
    python_files = find_python_files(project_path, exclude_dirs=list(ignore_dirs))

    if not args.quiet:
        print(t("side_effects.checking"))

    warnings = detect_side_effects(python_files, check_test_purity)

    if warnings:
        print(t("side_effects.found", len(warnings)))
        for w in warnings:
            rel_file = safe_relpath(w["file"], project_path)
            print(f"  - {rel_file}:{w['line']} -> {w['call']} ({w['reason']})")
        # 僅警告，不回傳錯誤碼
        return 0

    if not args.quiet:
        print(t("side_effects.success"))
    return 0


def check_deadcode(args: argparse.Namespace) -> int:
    """執行死代碼掃描 (僅警告)."""
    project_path = os.getcwd()
    ruff_config = get_ruff_config_from_pyproject(project_path)
    ignore_dirs = set(ruff_config["exclude_dirs"])
    python_files = find_python_files(project_path, exclude_dirs=list(ignore_dirs))

    if not args.quiet:
        print(t("deadcode.checking"))

    warnings = scan_dead_code(python_files)

    if warnings:
        print(t("deadcode.found", len(warnings)))
        for w in warnings:
            rel_file = safe_relpath(w["file"], project_path)
            print(f"  - {w['name']} (in {rel_file}:{w['line']})")
        # 僅警告，不回傳錯誤碼
        return 0

    if not args.quiet:
        print(t("deadcode.success"))
    return 0


def check_all(args: argparse.Namespace) -> int:
    """執行所有檢查."""
    exit_code = 0

    if not args.quiet:
        print("=" * 60)
        print(t("check_all.start"))
        print("=" * 60)

    # 1. 語法檢查
    if not args.quiet:
        print(f"\n{t('check_all.syntax_phase')}")
    if check_syntax(args) != 0:
        exit_code = 1
        if args.fail_fast:
            return exit_code

    # 2. Import 檢查
    if not args.quiet:
        print(f"\n{t('check_all.imports_phase')}")
    if check_imports(args) != 0:
        exit_code = 1
        if args.fail_fast:
            return exit_code

    # 3. 依賴健康度檢查
    if not args.quiet:
        print(f"\n{t('check_all.dependency_phase')}")
    if check_dependency(args) != 0:
        exit_code = 1
        if args.fail_fast:
            return exit_code

    # 4. 循環引用檢查
    if not args.quiet:
        print(f"\n{t('check_all.cycles_phase')}")
    if check_cycles(args) != 0:
        exit_code = 1

    # 5. 全局副作用檢查 (Warning only)
    if not args.quiet:
        print(f"\n{t('check_all.side_effects_phase')}")
    check_side_effects(args)

    # 6. 死代碼掃描 (Warning only)
    if not args.quiet:
        print(f"\n{t('check_all.deadcode_phase')}")
    check_deadcode(args)

    if not args.quiet:
        print("\n" + "=" * 60)
        if exit_code == 0:
            print(t("check_all.success"))
        else:
            print(t("check_all.errors"))
        print("=" * 60)

    return exit_code


def main() -> None:
    """CLI 主程式."""
    parser = argparse.ArgumentParser(
        prog="pyci-check",
        description=t("cli.description"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("cli.examples"),
    )

    subparsers = parser.add_subparsers(dest="command", help=t("cli.help.subcommand"))

    # 為每個子指令建立 parser,並加入共用參數
    def add_common_args(subparser: argparse.ArgumentParser, add_paths: bool = True) -> None:
        """新增共用參數."""
        if add_paths:
            subparser.add_argument("paths", nargs="*", default=None, help="要檢查的檔案或目錄路徑 (預設: 當前目錄)")
        subparser.add_argument("--quiet", "-q", action="store_true", help=t("cli.help.quiet"))
        subparser.add_argument("--fail-fast", action="store_true", help=t("cli.help.fail_fast"))
        subparser.add_argument("--timeout", type=int, default=30, help=t("cli.help.timeout"))
        subparser.add_argument("--check-relative", action="store_true", help=t("cli.help.check_relative"))
        subparser.add_argument("--venv", type=str, help=t("cli.help.venv"))
        subparser.add_argument("--i-understand-this-will-execute-code", action="store_true", help=t("cli.help.i_understand"))

    # check 子指令 (執行所有檢查)
    check_parser = subparsers.add_parser("check", help="執行所有檢查 (語法 + import)")
    add_common_args(check_parser)

    # syntax 子指令
    syntax_parser = subparsers.add_parser("syntax", help=t("cli.help.syntax"))
    add_common_args(syntax_parser)

    # imports 子指令
    imports_parser = subparsers.add_parser("imports", help=t("cli.help.imports"))
    add_common_args(imports_parser)

    # dependency 子指令
    dependency_parser = subparsers.add_parser("dependency", help=t("cli.help.dependency"))
    add_common_args(dependency_parser)

    # cycles 子指令
    cycles_parser = subparsers.add_parser("cycles", help=t("cli.help.cycles"))
    add_common_args(cycles_parser)

    # side-effects 子指令
    side_effects_parser = subparsers.add_parser("side-effects", help="檢查全局副作用 (警告層級)")
    add_common_args(side_effects_parser)

    # deadcode 子指令
    deadcode_parser = subparsers.add_parser("deadcode", help="掃描死代碼 (警告層級)")
    add_common_args(deadcode_parser)

    # install-hooks 子指令
    install_parser = subparsers.add_parser("install-hooks", help=t("cli.help.install_hooks"))
    install_parser.add_argument("--type", choices=["pre-commit", "pre-push", "both"], default="pre-commit", help=t("cli.help.hook_type"))

    # uninstall-hooks 子指令
    subparsers.add_parser("uninstall-hooks", help=t("cli.help.uninstall_hooks"))

    args = parser.parse_args()

    # 執行對應指令
    if args.command == "check":
        exit_code = check_all(args)
    elif args.command == "syntax":
        exit_code = check_syntax(args)
    elif args.command == "imports":
        exit_code = check_imports(args)
    elif args.command == "dependency":
        exit_code = check_dependency(args)
    elif args.command == "cycles":
        exit_code = check_cycles(args)
    elif args.command == "side-effects":
        exit_code = check_side_effects(args)
    elif args.command == "deadcode":
        exit_code = check_deadcode(args)
    elif args.command == "install-hooks":
        exit_code = install_hooks(args.type)
    elif args.command == "uninstall-hooks":
        exit_code = uninstall_hooks()
    else:
        # 沒有指定子指令時,顯示幫助訊息
        parser.print_help()
        exit_code = 0

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
