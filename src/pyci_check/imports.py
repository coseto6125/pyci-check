"""
Import 依賴檢查模組.

特點：
- 使用 subprocess 真正執行 import,能檢測到運行時錯誤
- 自動讀取 pyproject.toml 的 [tool.ruff] 設定
- 並行處理,速度快
- 每個模組完全隔離,一個失敗不影響其他檢查
"""

import argparse
import ast
import glob
import os
import re
import runpy
import subprocess
import sys
import time
import tomllib
from argparse import Namespace
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

from pyci_check.i18n import t
from pyci_check.utils import calculate_optimal_workers, safe_relpath

# 效能優化: 預先定義常數避免重複創建
SENSITIVE_ENV_PREFIXES = frozenset({"AWS", "SECRET", "TOKEN", "KEY", "PASSWORD"})

# 預先編譯正則表達式 (避免每次呼叫時重新編譯)
# 模組名稱驗證: 符合 Python 識別字規則 (字母、數字、底線、點號)
MODULE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$")

# Import 檢查腳本模板 (避免每次重新建立字串)
IMPORT_CHECK_SCRIPT = """
import sys
import os

# 禁止寫入操作
sys.dont_write_bytecode = True

try:
    __import__('{module}')
    sys.exit(0)
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
"""


@lru_cache(maxsize=1)
def find_pyproject_toml(project_dir: str) -> str | None:
    """尋找 pyproject.toml (快取結果)."""
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if os.path.exists(pyproject_path):
        return pyproject_path

    # 往上層尋找
    current = os.path.abspath(project_dir)
    while True:
        parent = os.path.dirname(current)
        if parent == current:  # 已到根目錄
            break
        candidate = os.path.join(parent, "pyproject.toml")
        if os.path.exists(candidate):
            return candidate
        current = parent

    return None


@lru_cache(maxsize=1)
def get_ruff_config_from_pyproject(project_dir: str) -> dict:
    """
    從 pyproject.toml 讀取 ruff 設定.

    優先讀取 [tool.pyci-check] 的 exclude,如果為空則讀取 [tool.ruff] 的 exclude.

    Returns:
        dict with keys: src, exclude_dirs, exclude_files
    """
    pyproject_path = find_pyproject_toml(project_dir)
    if not pyproject_path:
        return {"src": [], "exclude_dirs": [], "exclude_files": []}

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        # 檔案讀取失敗或 TOML 格式錯誤,使用預設設定
        return {"src": [], "exclude_dirs": [], "exclude_files": []}

    ruff = data.get("tool", {}).get("ruff", {})
    pyci_check = data.get("tool", {}).get("pyci-check", {})

    # 讀取 src
    src = ruff.get("src", [])
    if isinstance(src, str):
        src = [src]

    # 讀取 pyci-check 的 exclude
    pyci_exclude = pyci_check.get("exclude", [])
    if isinstance(pyci_exclude, str):
        pyci_exclude = [pyci_exclude]

    # 讀取 ruff 的 exclude + extend-exclude
    exclude = ruff.get("exclude", [])
    if isinstance(exclude, str):
        exclude = [exclude]

    extend_exclude = ruff.get("extend-exclude", [])
    if isinstance(extend_exclude, str):
        extend_exclude = [extend_exclude]

    # 合併去重: pyci-check 的 exclude + ruff 的 exclude + extend-exclude
    all_exclude = set(pyci_exclude + exclude + extend_exclude)

    # 合併並分類
    exclude_dirs = []
    exclude_files = []

    for item in all_exclude:
        # 移除尾部斜線
        item = item.rstrip("/")
        # 判斷是否為檔案（有副檔名）
        basename = os.path.basename(item)
        if "." in basename and not item.startswith("."):
            exclude_files.append(item)
        else:
            exclude_dirs.append(item)

    return {"src": src, "exclude_dirs": exclude_dirs, "exclude_files": exclude_files}


@lru_cache(maxsize=1)
def get_venv_from_pyproject(project_dir: str) -> str | None:
    """
    從 pyproject.toml 讀取虛擬環境設定.

    Returns:
        虛擬環境路徑或 None
    """
    pyproject_path = find_pyproject_toml(project_dir)
    if not pyproject_path:
        return None

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        # 檔案讀取失敗或 TOML 格式錯誤
        return None

    # 讀取 [tool.pyci-check] 中的 venv 設定
    pyci_check = data.get("tool", {}).get("pyci-check", {})
    venv = pyci_check.get("venv")

    if venv and isinstance(venv, str):
        return venv

    return None


class ImportVisitor(ast.NodeVisitor):
    """AST 訪問器，用於提取 import 語句."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.imports: list[dict] = []
        self.relative_imports: list[dict] = []

    def _create_import_info(self, module: str, line: int, statement: str, import_type: str) -> dict:
        return {"module": module, "line": line, "statement": statement, "file": self.filepath, "type": import_type}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module_name = alias.name
            self.imports.append(self._create_import_info(module_name, node.lineno, f"import {alias.name}", "absolute"))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level > 0:  # 相對導入
            # Python 3.11 兼容: 避免 f-string 中的引號巢狀
            dots = "." * node.level
            module_part = node.module or ""
            names_part = ", ".join(alias.name for alias in node.names)
            statement = f"from {dots}{module_part} import {names_part}"
            self.relative_imports.append(
                {**self._create_import_info(node.module or ".", node.lineno, statement, "relative"), "level": node.level},
            )
        elif node.module:  # 絕對導入
            module_name = node.module
            names_part = ", ".join(alias.name for alias in node.names)
            statement = f"from {node.module} import {names_part}"
            self.imports.append(self._create_import_info(module_name, node.lineno, statement, "absolute"))


def extract_imports_from_code(code: str, filepath: str) -> tuple[list[dict], list[dict]]:
    """提取程式碼中的 import 語句，並記錄位置資訊."""
    try:
        tree = ast.parse(code)
        visitor = ImportVisitor(filepath)
        visitor.visit(tree)
        return visitor.imports, visitor.relative_imports
    except SyntaxError:
        return [], []


def read_file_with_encoding(filepath: str) -> str | None:
    """
    讀取檔案，嘗試常見編碼.

    優化: 99% 的 Python 檔案都是 UTF-8，優先嘗試避免 exception 開銷

    Returns:
        檔案內容,如果讀取失敗則回傳 None
    """
    try:
        # 快速路徑: 直接讀取 UTF-8 (最常見)
        with open(filepath, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # 降級: 嘗試其他編碼
        for encoding in ["utf-8-sig", "latin-1"]:
            try:
                with open(filepath, encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError):
                continue
        # 所有編碼都失敗
        return None
    except OSError:
        # 檔案不存在、權限問題等
        return None


def process_single_file(filepath: str) -> tuple[list[dict], list[dict]]:
    """
    處理單一檔案的 import.

    Returns:
        (imports列表, relative_imports列表)
        如果檔案讀取失敗或無法解析,回傳空列表
    """
    code = read_file_with_encoding(filepath)
    if code is None:
        # 檔案讀取失敗 (編碼錯誤、權限問題等)
        # 靜默跳過,不中斷整體檢查
        return [], []

    return extract_imports_from_code(code, filepath)


def extract_from_all_files(
    project_dir: str,
    ignore_dirs: set[str] | None = None,
    ignore_files: set[str] | None = None,
    max_workers: int | None = None,
    target_files: list[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """使用多執行緒處理檔案 (優化版本)."""
    if ignore_dirs is None:
        ignore_dirs = {"venv", "env", ".venv", "node_modules", "__pycache__", ".git", "build", "dist", "experiments", ".layer_build"}
    if ignore_files is None:
        ignore_files = set()

    # 如果指定了 target_files,則使用指定的檔案列表
    if target_files:
        python_files = target_files
    else:
        # 使用 glob 遞迴搜尋 (比 pathlib.rglob 快)
        # 優化: 避免在迴圈中重複創建 set (從 O(n×m) 降到 O(n))
        pattern = os.path.join(project_dir, "**", "*.py")
        python_files = []
        for py_file in glob.glob(pattern, recursive=True):
            # 檢查檔案名 (O(1) set lookup)
            if os.path.basename(py_file) in ignore_files:
                continue
            # 檢查路徑中是否包含要忽略的目錄 (使用 any() 短路求值)
            path_parts = py_file.replace("\\", "/").split("/")
            if any(part in ignore_dirs for part in path_parts):
                continue
            python_files.append(py_file)

    if not python_files:
        return [], []

    max_workers = max_workers or calculate_optimal_workers(len(python_files))

    all_imports: list[dict] = []
    all_relative_imports: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_file, fp): fp for fp in python_files}
        for future in as_completed(futures):
            imports, relative_imports = future.result()
            all_imports.extend(imports)
            all_relative_imports.extend(relative_imports)

    return all_imports, all_relative_imports


def get_dynamic_imports(entry_path: str) -> set[str]:
    """
    取得動態載入的模組.

    透過執行入口檔案來收集動態 import 的模組.
    注意: 這會實際執行程式碼,可能有副作用.

    Args:
        entry_path: 入口檔案路徑

    Returns:
        動態載入的模組集合 (只包含頂層模組名稱)

    Raises:
        執行過程中的任何異常都會直接拋出
    """
    before = set(sys.modules.keys())
    runpy.run_path(entry_path, run_name="__main__")
    after = set(sys.modules.keys())
    dynamic = after - before
    return {name.split(".")[0] for name in dynamic}


def find_python_executable(venv_path: str | None = None) -> str:
    """
    尋找 Python 執行檔.

    邏輯:
    - 如果指定虛擬環境: 使用虛擬環境的 Python
    - 沒有指定: 使用當前執行的 Python (sys.executable)

    Args:
        venv_path: 虛擬環境路徑 (可選)

    Returns:
        Python 執行檔路徑
    """
    # 如果指定了虛擬環境,嘗試找虛擬環境的 Python
    if venv_path:
        # 檢查 uv 虛擬環境 (.venv/)
        uv_python = os.path.join(venv_path, ".venv", "bin", "python")
        if os.path.exists(uv_python):
            return uv_python

        # 檢查標準虛擬環境 (bin/)
        std_python = os.path.join(venv_path, "bin", "python")
        if os.path.exists(std_python):
            return std_python

        # 檢查 Windows (Scripts/)
        win_python = os.path.join(venv_path, "Scripts", "python.exe")
        if os.path.exists(win_python):
            return win_python

    # 沒有指定虛擬環境,或找不到虛擬環境: 使用當前 Python
    return sys.executable


def check_module_importable_static(module: str, project_dir: str | None = None, src_dirs: list[str] | None = None) -> tuple[str, str | None]:
    """
    最高限度靜態檢查模組是否存在 (完全不執行程式碼).

    檢查策略:
    1. 使用 importlib.util.find_spec 檢查標準庫和已安裝套件
    2. 檢查專案目錄中的模組檔案
    3. 支援套件和單檔案模組
    4. 支援命名空間套件

    Args:
        module: 模組名稱
        project_dir: 專案根目錄
        src_dirs: 額外的 source 目錄

    Returns:
        (模組名稱, 錯誤訊息 or None)
    """
    import importlib.util
    import sys

    # 策略 1: 檢查標準庫和已安裝套件
    # 暫存原始 sys.path
    original_path = sys.path.copy()

    try:
        # 加入專案路徑到 sys.path (不執行程式碼)
        if project_dir and src_dirs:
            for src in src_dirs:
                src_path = os.path.join(project_dir, src)
                if os.path.exists(src_path):
                    sys.path.insert(0, src_path)

            # 也加入專案根目錄
            sys.path.insert(0, project_dir)

        # 使用 find_spec 靜態查找
        # 注意: find_spec 的行為
        # - 找到模組: 回傳 ModuleSpec 物件
        # - 找不到: 回傳 None
        # - 錯誤 (循環導入、損壞的模組等): 拋出異常 → 應該報錯
        try:
            spec = importlib.util.find_spec(module)
        except Exception as e:
            # find_spec 檢查過程出錯,回傳錯誤訊息
            return module, t("imports.error.find_spec_failed", e)

    finally:
        # 確保 sys.path 總是被還原
        sys.path = original_path

    # 策略 1 成功找到模組
    if spec is not None:
        return module, None

    # 策略 2: 手動檢查專案目錄中的檔案
    if project_dir:
        # 處理模組名稱 (支援 a.b.c 形式)
        module_parts = module.split(".")
        base_module = module_parts[0]

        # 檢查根目錄
        root_module_py = os.path.join(project_dir, f"{base_module}.py")
        root_module_init = os.path.join(project_dir, base_module, "__init__.py")
        if os.path.exists(root_module_py):
            return module, None
        if os.path.exists(root_module_init):
            return module, None

        # 檢查 src_dirs
        if src_dirs:
            for src in src_dirs:
                src_path = os.path.join(project_dir, src)
                if not os.path.exists(src_path):
                    continue

                # 單檔案模組
                module_file = os.path.join(src_path, f"{base_module}.py")
                if os.path.exists(module_file):
                    return module, None

                # 套件目錄
                module_dir = os.path.join(src_path, base_module, "__init__.py")
                if os.path.exists(module_dir):
                    return module, None

                # 檢查子模組 (如 a.b.c)
                if len(module_parts) > 1:
                    submodule_path = os.path.join(src_path, base_module)
                    for part in module_parts[1:]:
                        submodule_path = os.path.join(submodule_path, part)

                    submodule_py = os.path.join(os.path.dirname(submodule_path), f"{part}.py")
                    submodule_init = os.path.join(submodule_path, "__init__.py")
                    if os.path.exists(submodule_py):
                        return module, None
                    if os.path.exists(submodule_init):
                        return module, None

    return module, t("imports.error.module_not_found", module)


def check_module_importable(
    module: str,
    project_dir: str | None = None,
    src_dirs: list[str] | None = None,
    timeout: int = 30,
    venv_path: str | None = None,
) -> tuple[str, str | None]:
    """
    檢查模組是否能載入 (會真實執行 import 載入所有程式碼).

    警告: 此函數會實際執行模組的程式碼!

    Args:
        module: 模組名稱
        project_dir: 專案根目錄
        src_dirs: 額外的 source 目錄 (如 src, tests)
        timeout: 超時秒數
        venv_path: 虛擬環境路徑 (可選)

    Returns:
        (模組名稱, 錯誤訊息 or None)
    """
    # S603: 安全檢查 - 驗證模組名稱僅包含合法字元
    if not MODULE_NAME_PATTERN.match(module):
        return module, t("imports.error.invalid_module_name", module)

    # 真實執行 import (subprocess 隔離)
    env = os.environ.copy()

    # 組合所有路徑
    paths: list[str] = []
    if project_dir:
        paths.append(project_dir)
        # 加入 src_dirs
        if src_dirs:
            for src in src_dirs:
                full_path = os.path.join(project_dir, src)
                if os.path.isdir(full_path):
                    paths.append(full_path)

    if paths:
        current = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(paths + ([current] if current else []))

    # 取得 Python 執行檔
    python_exec = find_python_executable(venv_path)

    try:
        # 使用 subprocess 隔離執行
        # Sandbox 安全措施:
        # 1. 移除敏感環境變數 (優化: 使用預定義的 frozenset)
        sandbox_env = {k: v for k, v in env.items() if not any(k.startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES)}

        # 2. 設定安全的環境變數
        sandbox_env["PYTHONDONTWRITEBYTECODE"] = "1"  # 不寫入 .pyc
        sandbox_env["PYTHONINSPECT"] = "0"  # 不進入交互模式
        sandbox_env["PYTHONUNBUFFERED"] = "1"  # 不緩衝輸出

        # 3. 使用受限的 import 檢查腳本 (優化: 使用預定義模板)
        import_script = IMPORT_CHECK_SCRIPT.format(module=module)

        # S603: subprocess call is safe - module name validated by regex at line 441
        result = subprocess.run(  # noqa: S603
            [python_exec, "-c", import_script],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=sandbox_env,
            cwd=project_dir,
        )
        if result.returncode != 0:
            # 取最後幾行錯誤訊息
            stderr_lines = result.stderr.strip().split("\n") if result.stderr else []
            error = stderr_lines[-1] if stderr_lines else "Unknown error"
            return module, error
        return module, None
    except subprocess.TimeoutExpired:
        return module, t("imports.error.import_timeout", timeout)
    except OSError as e:
        # 執行 Python 失敗 (檔案不存在、權限問題等)
        return module, t("imports.error.failed_to_execute", e)
    except Exception as e:
        # 其他預期外的錯誤
        return module, t("imports.error.unexpected_error", e)


def check_missing_modules(
    all_imports: list[dict],
    project_dir: str | None = None,
    src_dirs: list[str] | None = None,
    max_workers: int | None = None,
    timeout: int = 30,
    venv_path: str | None = None,
    use_static: bool = True,
) -> dict[str, list[dict]]:
    """
    檢查缺少的模組.

    Args:
        all_imports: 所有 import 資訊
        project_dir: 專案根目錄
        src_dirs: 額外的 source 目錄
        max_workers: 最大並行數
        timeout: 每個模組的超時秒數
        venv_path: 虛擬環境路徑 (可選)
        use_static: True=靜態檢查(不執行), False=真實執行(可檢測運行時錯誤)

    Returns:
        缺少/載入失敗的模組字典
    """
    # 優化: 使用 frozenset 比 set 快 (不可變,hash code 可快取)
    builtin_modules = frozenset(sys.builtin_module_names) | frozenset({"__main__", "__future__", "__builtins__"})

    # 收集需要檢查的模組
    modules_by_name: dict[str, list[dict]] = defaultdict(list)
    for import_info in all_imports:
        module = import_info["module"]
        if module not in builtin_modules:
            modules_by_name[module].append(import_info)

    unique_modules = list(modules_by_name.keys())
    if not unique_modules:
        return {}

    max_workers = max_workers or calculate_optimal_workers(len(unique_modules))

    # 並行檢查
    missing_modules: dict[str, list[dict]] = {}

    # 選擇檢查方式
    check_func = check_module_importable_static if use_static else check_module_importable

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        if use_static:
            # 靜態檢查不需要 timeout 和 venv_path
            futures = {executor.submit(check_func, m, project_dir, src_dirs): m for m in unique_modules}
        else:
            # 真實執行需要 timeout 和 venv_path
            futures = {executor.submit(check_func, m, project_dir, src_dirs, timeout, venv_path): m for m in unique_modules}  # type: ignore[call-arg]

        for future in as_completed(futures):
            module, error = future.result()
            if error:
                # 加入錯誤訊息到每個 import_info
                for info in modules_by_name[module]:
                    info["error"] = error
                missing_modules[module] = modules_by_name[module]

    return missing_modules


def print_results(
    missing_modules: dict[str, list[dict]],
    all_relative_imports: list[dict],
    args: Namespace,
    total_time: float,
    unique_modules: set[str],
) -> bool:
    """輸出結果."""
    has_issues = False

    if args.check_relative and all_relative_imports:
        has_issues = True
        for rel_import in all_relative_imports:
            # 錯誤訊息不受 --quiet 影響,總是顯示
            print(t("imports.standalone.relative_warning", rel_import["file"], rel_import["line"], rel_import["statement"]))

    if missing_modules:
        has_issues = True
        total_errors = 0
        for module, import_list in sorted(missing_modules.items()):
            for import_info in import_list:
                file_path = import_info["file"]
                error_msg = import_info.get("error", "Module not found")
                # 錯誤訊息不受 --quiet 影響,總是顯示
                rel_path = safe_relpath(file_path, args.project_path)
                print(t("imports.standalone.load_failed", module))
                print(t("imports.standalone.file_line", rel_path, import_info["line"]))
                print(t("imports.standalone.statement", import_info["statement"]))
                print(t("imports.standalone.reason", error_msg))
                print()
                total_errors += 1

    if not args.quiet:
        print(t("imports.standalone.summary_line"))
        print(t("imports.standalone.summary_time", total_time))
        print(t("imports.standalone.summary_modules", len(unique_modules)))
        if missing_modules:
            print(t("imports.standalone.summary_failed", len(missing_modules)))
            print(t("imports.standalone.summary_total_errors", total_errors))
        else:
            print(t("imports.standalone.summary_success"))

    return has_issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Python 模組依賴檢查工具（支援運行時錯誤檢測）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  %(prog)s .                          # 檢查當前目錄
  %(prog)s ./project --timeout 60     # 檢查指定目錄，超時 60 秒
  %(prog)s . --check-relative         # 同時檢查相對導入
  %(prog)s . --src-dirs src tests     # 手動指定 source 目錄

設定檔 (自動讀取 pyproject.toml):
  [tool.ruff]
  src = ["src", "tests"]              # 作為 PYTHONPATH
  exclude = [".venv", "build"]        # 忽略的目錄
  extend-exclude = ["starlette_app.py"] # 也支援忽略特定檔案
        """,
    )
    parser.add_argument("project_path", nargs="?", default=".", help="專案根目錄（預設：當前目錄）")
    parser.add_argument("--entry", help="指定主程式入口（觸發動態 import）")
    parser.add_argument("--workers", type=int, help="多執行緒工作者數量（不指定則自動計算）")
    parser.add_argument("--timeout", type=int, default=30, help="每個模組載入的超時秒數（預設：30）")
    parser.add_argument("--quiet", "-q", action="store_true", help="減少輸出訊息")
    parser.add_argument("--check-relative", action="store_true", help="檢查相對導入（預設：不檢查）")
    parser.add_argument(
        "--ignore-dirs",
        nargs="*",
        default=[],
        help="額外要忽略的目錄（會與 ruff exclude 合併）",
    )
    parser.add_argument("--ignore-files", nargs="*", default=[], help="要忽略的檔案")
    parser.add_argument(
        "--src-dirs",
        nargs="*",
        default=None,
        help="額外的 source 目錄（不指定則從 pyproject.toml [tool.ruff] src 讀取）",
    )
    args = parser.parse_args()

    start_time = time.time()

    # 取得絕對路徑
    project_path = os.path.abspath(args.project_path)

    # 讀取 ruff 設定
    ruff_config = get_ruff_config_from_pyproject(project_path)

    # src_dirs：優先使用命令列參數，否則從 pyproject.toml 讀取
    src_dirs = args.src_dirs if args.src_dirs is not None else ruff_config["src"]

    # ignore_dirs：合併預設值 + 命令列參數 + ruff exclude_dirs
    default_ignore_dirs = {"venv", "env", ".venv", "node_modules", "__pycache__", ".git", "build", "dist", ".layer_build"}
    ignore_dirs = default_ignore_dirs | set(args.ignore_dirs or []) | set(ruff_config["exclude_dirs"])

    # ignore_files：合併命令列參數 + ruff exclude_files
    ignore_files = set(args.ignore_files or []) | set(ruff_config["exclude_files"])

    if not args.quiet:
        print(t("imports.standalone.start_check", project_path))
        if src_dirs:
            print(t("imports.standalone.pythonpath", ", ".join(src_dirs)))
        if ruff_config["exclude_dirs"]:
            print(t("imports.standalone.exclude_dirs", ", ".join(ruff_config["exclude_dirs"])))
        if ruff_config["exclude_files"]:
            print(t("imports.standalone.exclude_files", ", ".join(ruff_config["exclude_files"])))
        print(t("imports.standalone.mode"))
        print(t("imports.standalone.summary_line"))

    # 分析 import
    all_imports, all_relative_imports = extract_from_all_files(
        project_path,
        ignore_dirs=ignore_dirs,
        ignore_files=ignore_files,
        max_workers=args.workers,
    )

    # 動態 import
    has_dynamic_error = False
    if args.entry:
        if not args.quiet:
            print(t("imports.standalone.run_dynamic", args.entry))
        try:
            dynamic_imports = get_dynamic_imports(args.entry)
            for module in dynamic_imports:
                all_imports.append({"module": module, "line": 0, "statement": f"Dynamic load: {module}", "file": args.entry, "type": "dynamic"})
        except Exception as e:
            has_dynamic_error = True
            # 錯誤訊息不受 --quiet 影響,總是顯示
            print(t("imports.standalone.dynamic_error", args.entry))
            print(t("imports.standalone.reason", str(e)))
            print()

    unique_modules = {imp["module"] for imp in all_imports}

    if not args.quiet:
        print(t("imports.standalone.found_modules", len(unique_modules)))
        print()

    # 檢查模組
    missing_modules = check_missing_modules(
        all_imports,
        project_dir=project_path,
        src_dirs=src_dirs,
        max_workers=args.workers,
        timeout=args.timeout,
    )

    total_time = time.time() - start_time

    has_issues = print_results(missing_modules, all_relative_imports, args, total_time, unique_modules)
    sys.exit(1 if (has_issues or has_dynamic_error) else 0)


if __name__ == "__main__":
    main()
