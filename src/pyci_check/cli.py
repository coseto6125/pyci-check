"""CLI 入口點."""

import argparse
import os
import sys

from pyci_check.git_hook import install_hooks, uninstall_hooks
from pyci_check.i18n import t
from pyci_check.imports import (
    check_missing_modules,
    extract_from_all_files,
    get_ruff_config_from_pyproject,
    get_venv_from_pyproject,
)
from pyci_check.syntax import check_files_parallel, find_python_files


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
            target_files.extend(find_python_files(abs_path))

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
        for module, import_list in sorted(missing_modules.items()):
            for import_info in import_list:
                rel_path = os.path.relpath(import_info["file"], project_path)
                error_msg = import_info.get("error", "Module not found")
                print(t("imports.module_failed", module))
                print(t("imports.file", rel_path, import_info["line"]))
                print(t("imports.statement", import_info["statement"]))
                print(t("imports.reason", error_msg))
                print()
        return 1

    if not args.quiet:
        print(t("imports.success"))
    return 0


def check_all(args: argparse.Namespace) -> int:
    """執行所有檢查."""
    exit_code = 0

    if not args.quiet:
        print("=" * 60)
        print(t("check_all.start"))
        print("=" * 60)

    # 語法檢查
    if not args.quiet:
        print(f"\n{t('check_all.syntax_phase')}")
    syntax_result = check_syntax(args)
    if syntax_result != 0:
        exit_code = 1
        if args.fail_fast:
            return exit_code

    # Import 檢查
    if not args.quiet:
        print(f"\n{t('check_all.imports_phase')}")
    import_result = check_imports(args)
    if import_result != 0:
        exit_code = 1

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
