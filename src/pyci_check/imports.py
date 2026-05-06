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
import contextlib
import hashlib
import json
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
from pyci_check.utils import calculate_optimal_workers, get_exclude_dirs_set, safe_relpath, should_use_thread_pool, walk_python_files

# 效能優化: 預先定義常數避免重複創建
SENSITIVE_ENV_PREFIXES = frozenset({"AWS", "SECRET", "TOKEN", "KEY", "PASSWORD"})

# 預先編譯正則表達式 (避免每次呼叫時重新編譯)
# 模組名稱驗證: 符合 Python 識別字規則 (字母、數字、底線、點號)
MODULE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$")

# 一次性 subprocess import 檢查腳本; sys.exit(0) 在 try 外面避免被 BaseException 捕到
IMPORT_CHECK_SCRIPT = """
import sys
sys.dont_write_bytecode = True
try:
    __import__('{module}')
except BaseException as e:
    # 含 SystemExit/KeyboardInterrupt: 模組 top-level 觸發 sys.exit 視為失敗
    print(str(e) or type(e).__name__, file=sys.stderr)
    sys.exit(1)
sys.exit(0)
"""

class _FindSpecCache:
    """
    find_spec 結果按 sys.path 內容 + mtime 做快取.

    Cache key: sys.path 字串 + 各路徑 mtime 的 sha256 (取前 16 字)
    pip install / venv 變更 → 簽名改變 → cache 自動失效
    """

    FILENAME = "find_spec.json"
    VERSION = 2

    def __init__(self, project_dir: str | None, sys_path: list[str]) -> None:
        self.disabled = project_dir is None
        if self.disabled:
            self.signature = ""
            self.cache_file = ""
        else:
            self.cache_dir = os.path.join(project_dir, ".pyci-check-cache")
            self.cache_file = os.path.join(self.cache_dir, self.FILENAME)
            self.signature = self._compute_signature(sys_path)
        self._data: dict[str, bool | str] = {}  # module -> True (found) / error_msg (missing)
        self._dirty = False
        if not self.disabled:
            self._load()

    @staticmethod
    def _compute_signature(sys_path: list[str]) -> str:
        parts = ["|".join(sys_path)]
        for p in sys_path:
            try:
                parts.append(f"{p}={os.path.getmtime(p)}")
            except OSError:
                # 路徑不存在: 簽名仍應穩定
                parts.append(f"{p}=missing")
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]

    def _load(self) -> None:
        try:
            with open(self.cache_file, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        if data.get("version") == self.VERSION and data.get("signature") == self.signature:
            self._data = data.get("results", {})

    def get(self, module: str) -> tuple[bool, str | None] | None:
        """None = miss, (True, None) = 已找到, (False, msg) = 找不到."""
        v = self._data.get(module)
        if v is None:
            return None
        if v is True:
            return (True, None)
        return (False, str(v))

    def set(self, module: str, error: str | None) -> None:
        self._data[module] = True if error is None else error
        self._dirty = True

    def flush(self) -> None:
        if self.disabled or not self._dirty:
            return
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump({"version": self.VERSION, "signature": self.signature, "results": self._data}, f)
        except OSError:
            # 寫入失敗不影響檢查結果
            pass


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

    合併 [tool.pyci-check] 和 [tool.ruff] 的 exclude 和 extend-exclude 設定.

    合併順序:
    - [tool.pyci-check].exclude
    - [tool.pyci-check].extend-exclude
    - [tool.ruff].exclude
    - [tool.ruff].extend-exclude

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

    # 讀取 pyci-check 的 exclude + extend-exclude
    pyci_exclude = pyci_check.get("exclude", [])
    if isinstance(pyci_exclude, str):
        pyci_exclude = [pyci_exclude]

    pyci_extend_exclude = pyci_check.get("extend-exclude", [])
    if isinstance(pyci_extend_exclude, str):
        pyci_extend_exclude = [pyci_extend_exclude]

    # 讀取 ruff 的 exclude + extend-exclude
    exclude = ruff.get("exclude", [])
    if isinstance(exclude, str):
        exclude = [exclude]

    extend_exclude = ruff.get("extend-exclude", [])
    if isinstance(extend_exclude, str):
        extend_exclude = [extend_exclude]

    # 合併去重: pyci-check 的 exclude + extend-exclude + ruff 的 exclude + extend-exclude
    all_exclude = set(pyci_exclude + pyci_extend_exclude + exclude + extend_exclude)

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


_OPTIONAL_IMPORT_EXC_NAMES = frozenset({"ImportError", "ModuleNotFoundError", "Exception", "BaseException"})


def _is_type_checking_guard(test: ast.expr) -> bool:
    """判斷 if test 是否為 TYPE_CHECKING 守護 (typing.TYPE_CHECKING / TYPE_CHECKING)."""
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return bool(isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    """Except 子句是否會抓到 ImportError (含 bare except / Exception / 元組)."""
    exc_type = handler.type
    if exc_type is None:
        return True  # bare except: 抓 everything 含 ImportError
    if isinstance(exc_type, ast.Name):
        return exc_type.id in _OPTIONAL_IMPORT_EXC_NAMES
    if isinstance(exc_type, ast.Attribute):
        return exc_type.attr in _OPTIONAL_IMPORT_EXC_NAMES
    if isinstance(exc_type, ast.Tuple):
        for elt in exc_type.elts:
            if isinstance(elt, ast.Name) and elt.id in _OPTIONAL_IMPORT_EXC_NAMES:
                return True
            if isinstance(elt, ast.Attribute) and elt.attr in _OPTIONAL_IMPORT_EXC_NAMES:
                return True
    return False


def _handle_import(visitor: "ImportVisitor", stmt: ast.Import) -> None:
    for alias in stmt.names:
        visitor.imports.append(visitor._create_import_info(alias.name, stmt.lineno, f"import {alias.name}", "absolute"))


def _handle_import_from(visitor: "ImportVisitor", stmt: ast.ImportFrom) -> None:
    names_part = ", ".join(alias.name for alias in stmt.names)
    if stmt.level > 0:  # 相對導入
        statement = f"from {'.' * stmt.level}{stmt.module or ''} import {names_part}"
        visitor.relative_imports.append(
            {**visitor._create_import_info(stmt.module or ".", stmt.lineno, statement, "relative"), "level": stmt.level},
        )
    elif stmt.module:  # 絕對導入
        statement = f"from {stmt.module} import {names_part}"
        visitor.imports.append(visitor._create_import_info(stmt.module, stmt.lineno, statement, "absolute"))


def _handle_if(visitor: "ImportVisitor", stmt: ast.If) -> None:
    """If 特別處理: TYPE_CHECKING 守護下 body runtime 不執行，只走 orelse."""
    if _is_type_checking_guard(stmt.test):
        visitor._walk(stmt.orelse)
    else:
        visitor._walk(stmt.body)
        visitor._walk(stmt.orelse)


def _handle_body_orelse(visitor: "ImportVisitor", stmt: ast.While | ast.For | ast.AsyncFor) -> None:
    visitor._walk(stmt.body)
    visitor._walk(stmt.orelse)


def _handle_body_only(visitor: "ImportVisitor", stmt: ast.With | ast.AsyncWith | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
    visitor._walk(stmt.body)


def _handle_try(visitor: "ImportVisitor", stmt: ast.Try | ast.TryStar) -> None:
    """Try 特別處理: 若任一 handler 抓 ImportError，try.body 內的 import 標 optional."""
    catches_import = any(_handler_catches_import_error(h) for h in stmt.handlers)
    if catches_import:
        visitor._optional_depth += 1
        try:
            visitor._walk(stmt.body)
        finally:
            visitor._optional_depth -= 1
    else:
        visitor._walk(stmt.body)
    for handler in stmt.handlers:
        visitor._walk(handler.body)
    visitor._walk(stmt.orelse)
    visitor._walk(stmt.finalbody)


def _handle_match(visitor: "ImportVisitor", stmt: ast.Match) -> None:
    for case in stmt.cases:
        visitor._walk(case.body)


# Dispatch by exact type — AST stmt 都是 concrete leaf class，無需 isinstance 多型；
# 大宗 stmt (Expr/Assign/Return/...) 一次 dict.get miss 即跳過，免走 isinstance 鏈
_DISPATCH: dict[type, "callable"] = {
    ast.Import: _handle_import,
    ast.ImportFrom: _handle_import_from,
    ast.If: _handle_if,
    ast.While: _handle_body_orelse,
    ast.For: _handle_body_orelse,
    ast.AsyncFor: _handle_body_orelse,
    ast.With: _handle_body_only,
    ast.AsyncWith: _handle_body_only,
    ast.FunctionDef: _handle_body_only,
    ast.AsyncFunctionDef: _handle_body_only,
    ast.ClassDef: _handle_body_only,
    ast.Try: _handle_try,
    ast.TryStar: _handle_try,
    ast.Match: _handle_match,
}


class ImportVisitor:
    """提取 import 語句，只下鑽 statement 容器，不訪問 expression."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.imports: list[dict] = []
        self.relative_imports: list[dict] = []
        # try/except ImportError 嵌套深度: > 0 表示當前 import 是 optional dep
        self._optional_depth = 0

    def _create_import_info(self, module: str, line: int, statement: str, import_type: str) -> dict:
        return {
            "module": module,
            "line": line,
            "statement": statement,
            "file": self.filepath,
            "type": import_type,
            "optional": self._optional_depth > 0,
        }

    def visit(self, tree: ast.Module) -> None:
        self._walk(tree.body)

    def _walk(self, stmts: list[ast.stmt]) -> None:
        # 區域變數 hoist: 避免每次迭代查 global
        dispatch_get = _DISPATCH.get
        for stmt in stmts:
            handler = dispatch_get(type(stmt))
            if handler is not None:
                handler(self, stmt)


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
        ignore_dirs = set(get_exclude_dirs_set())
    if ignore_files is None:
        ignore_files = set()

    # target_files 優先；否則用 walk_python_files (os.walk(followlinks=False) + prune 排除目錄)
    python_files = target_files or walk_python_files(project_dir, frozenset(ignore_dirs), frozenset(ignore_files))

    if not python_files:
        return [], []

    max_workers = max_workers or calculate_optimal_workers(len(python_files))

    all_imports: list[dict] = []
    all_relative_imports: list[dict] = []

    if should_use_thread_pool(len(python_files), work_kind="cpu"):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_file, fp): fp for fp in python_files}
            for future in as_completed(futures):
                imports, relative_imports = future.result()
                all_imports.extend(imports)
                all_relative_imports.extend(relative_imports)
    else:
        for file_path in python_files:
            imports, relative_imports = process_single_file(file_path)
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


def _build_sandbox_env(project_dir: str | None, src_dirs: list[str] | None, venv_path: str | None) -> tuple[dict[str, str], str]:
    """
    組 sandbox 用的 env dict 與 Python 執行檔路徑.

    用於 subprocess import 檢查 (一次性 check_module_importable 與常駐 worker 共用).
    步驟: PYTHONPATH 注入專案路徑 → 過濾 SENSITIVE_ENV_PREFIXES → 設安全變數。

    Returns:
        (sandbox_env, python_exec)
    """
    env = os.environ.copy()

    paths: list[str] = []
    if project_dir:
        paths.append(project_dir)
        if src_dirs:
            for src in src_dirs:
                full_path = os.path.join(project_dir, src)
                if os.path.isdir(full_path):
                    paths.append(full_path)
    if paths:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(paths + ([existing] if existing else []))

    sandbox_env = {k: v for k, v in env.items() if not any(k.startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES)}
    sandbox_env["PYTHONDONTWRITEBYTECODE"] = "1"
    # PYTHONINSPECT: 3.14+ 任何非空字串都 enable; 必須 pop 而非設 "0"
    sandbox_env.pop("PYTHONINSPECT", None)
    sandbox_env["PYTHONUNBUFFERED"] = "1"

    return sandbox_env, find_python_executable(venv_path)


@lru_cache(maxsize=1)
def _stdlib_top_levels() -> frozenset[str]:
    """Stdlib 全部模組名 (3.10+)，比 sys.builtin_module_names 完整 (含純 Python stdlib)."""
    return frozenset(sys.stdlib_module_names) | frozenset({"__main__", "__future__", "__builtins__"})


@lru_cache(maxsize=1)
def _installed_top_levels() -> frozenset[str]:
    """
    已安裝第三方 top-level 模組名集合.

    雙保險:
    1. importlib.metadata.packages_distributions() — 讀 dist-info top_level.txt / RECORD
    2. site-packages 直接 ls — 補強 editable install / 老式 setuptools / namespace package
    """
    import site
    from importlib.metadata import PackageNotFoundError, packages_distributions

    # metadata 損壞或缺檔: suppress 後退到下面的 site-packages ls fallback
    names: set[str] = set()
    with contextlib.suppress(PackageNotFoundError, OSError, ValueError):
        names.update(packages_distributions().keys())

    # site-packages ls fallback (補 editable install / namespace package / metadata 漏網)
    candidates: list[str] = []
    with contextlib.suppress(AttributeError, OSError):
        candidates.extend(site.getsitepackages())
    try:
        user_site = site.getusersitepackages()
        if user_site:
            candidates.append(user_site)
    except OSError:
        pass

    for site_dir in candidates:
        try:
            for entry in os.listdir(site_dir):
                # 排除 dist-info / egg-info / pyc 等
                if entry.endswith((".dist-info", ".egg-info", ".pyc", ".pth", ".txt")):
                    continue
                if entry.startswith(("__pycache__", "_distutils_hack")):
                    continue
                if entry.endswith(".py"):
                    stem = entry[:-3]
                    if stem.isidentifier():
                        names.add(stem)
                # 目錄: regular package or namespace package
                elif entry.isidentifier():
                    names.add(entry)
        except OSError:
            continue

    return frozenset(names)


def _probe_module_roots(module: str, roots: list[str]) -> bool:
    """檢查 roots 內是否存在 dotted module (檔案系統純 probe)."""
    parts = module.split(".")
    suffixes = _module_file_suffixes()

    for root in roots:
        if not os.path.isdir(root):
            continue
        # 沿 dotted 一路走下去，途中允許 namespace package (沒 __init__.py 也行)
        cur = root
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            dir_path = os.path.join(cur, part)
            if is_last:
                # 葉子: 接受 .py / C extension / 套件目錄 / namespace package 目錄
                for suffix in suffixes:
                    if os.path.isfile(os.path.join(cur, part + suffix)):
                        return True
                if os.path.isdir(dir_path):
                    return True
                break
            # 中間段: 一定要是目錄 (regular 或 namespace package 都可)
            if os.path.isdir(dir_path):
                cur = dir_path
                continue
            break
    return False


def _probe_local(module: str, project_dir: str, src_dirs: list[str] | None) -> bool:
    """檢查 project_dir + src_dirs 內是否存在該模組 (檔案系統純 probe)."""
    roots = [project_dir]
    if src_dirs:
        roots.extend(os.path.join(project_dir, s) for s in src_dirs)
    return _probe_module_roots(module, roots)


# .py + 當前 Python 的 C extension 後綴 (含 ABI tag / platform tag)
@lru_cache(maxsize=1)
def _module_file_suffixes() -> tuple[str, ...]:
    import importlib.machinery as _im
    return (".py", *_im.EXTENSION_SUFFIXES)


def _venv_site_packages(venv_path: str) -> list[str]:
    """從 --venv 參數推算 site-packages 路徑 (跨平台)."""
    import glob

    candidates: list[str] = []
    # 兩種佈局: <venv>/.venv/lib/... (uv 慣例) 與 <venv>/lib/... (標準 venv)
    for base in (os.path.join(venv_path, ".venv"), venv_path):
        # Unix: lib/python3.X/site-packages
        candidates.extend(glob.glob(os.path.join(base, "lib", "python*", "site-packages")))
        # Windows: Lib/site-packages
        win_path = os.path.join(base, "Lib", "site-packages")
        if os.path.isdir(win_path):
            candidates.append(win_path)
    return candidates


# 大量 dotted import 共享同一路徑查找 → 掃描結果可重用
@lru_cache(maxsize=512)
def _probe_sys_path_cached(module: str, paths_tuple: tuple[str, ...]) -> bool:
    roots = [entry or os.getcwd() for entry in paths_tuple]
    return _probe_module_roots(module, roots)


def _probe_sys_path(module: str, extra_paths: list[str] | None = None) -> bool:
    """
    掃 sys.path (+ extra_paths) 各 entry 純檔案系統檢查; 不觸發任何 finder 或 __init__.py.

    補 metadata + site-packages ls 的漏網 case:
    - .pth 注入的非標準路徑
    - 條件式 sys.path.insert 加進來的目錄
    - PEP 660 editable install 把源碼路徑 inject 到 sys.path
    - C extension (.so / .pyd / .abi3.so) 子模組
    - 透過 --venv 指定的外部虛擬環境 site-packages

    Args:
        module: 模組名稱
        extra_paths: 額外掃描路徑 (例如 --venv 指定的 site-packages)
    """
    # tuple 化 paths 才能進 lru_cache
    paths_tuple = (*extra_paths, *sys.path) if extra_paths else tuple(sys.path)
    return _probe_sys_path_cached(module, paths_tuple)


def check_module_importable_static(
    module: str,
    project_dir: str | None = None,
    src_dirs: list[str] | None = None,
    extra_paths: list[str] | None = None,
) -> tuple[str, str | None]:
    """
    純靜態檢查模組是否能被找到 (完全不執行任何使用者程式碼).

    四層 probe (從最快到最慢):
    L1. stdlib (sys.stdlib_module_names) — frozenset O(1)
    L2. 已安裝第三方 (importlib.metadata + site-packages ls)
    L3. 專案 local (project_dir + src_dirs 檔案系統)
    L4. sys.path + extra_paths probe (補 .pth / editable install / --venv 指定的 site-packages)

    僅檢查「模組是否能被找到」,不檢查「import 時是否會出錯」(後者需 --execute 模式)。
    完全不呼叫 importlib.util.find_spec — 後者對 dotted name 會 import parent package
    觸發 __init__.py 副作用 (與並行檢查衝突可能 deadlock)。

    Args:
        module: 模組名稱
        project_dir: 專案根目錄
        src_dirs: 額外的 source 目錄
        extra_paths: 外部虛擬環境 site-packages 路徑 (來自 --venv 參數)

    Returns:
        (模組名稱, 錯誤訊息 or None)
    """
    top = module.split(".", 1)[0]

    # L1: stdlib
    if top in _stdlib_top_levels():
        return module, None

    # L2: 已安裝第三方 top-level (dotted submodule 需走後續檔案系統深度 probe)
    if "." not in module and not extra_paths and top in _installed_top_levels():
        return module, None

    # L3: 專案 local (能定位到 dotted 葉子節點)
    if project_dir and _probe_local(module, project_dir, src_dirs):
        return module, None

    # L4: sys.path + extra_paths 檔案系統 fallback
    if _probe_sys_path(module, extra_paths):
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

    sandbox_env, python_exec = _build_sandbox_env(project_dir, src_dirs, venv_path)
    import_script = IMPORT_CHECK_SCRIPT.format(module=module)

    try:
        # S603: module name 已通過 MODULE_NAME_PATTERN regex 驗證
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

    # try/except ImportError 包住的模組 (全部使用點都 optional) → 跳過驗證
    # 這是 Python 表達 optional dep 的標準寫法；missing 不算錯
    all_optional_modules: set[str] = {
        mod for mod, infos in modules_by_name.items() if all(info.get("optional", False) for info in infos)
    }
    for mod in all_optional_modules:
        del modules_by_name[mod]

    unique_modules = list(modules_by_name.keys())
    if not unique_modules:
        return {}

    missing_modules: dict[str, list[dict]] = {}

    def _record_error(mod: str, err: str) -> None:
        # 同模組混合 optional/required 使用: 只報 required 那些 (avoid 雜訊)
        # 全 optional 已被 all_optional_modules 在前面過濾掉，此處 required_infos 必非空
        required_infos = [info for info in modules_by_name[mod] if not info.get("optional", False)]
        for info in required_infos:
            info["error"] = err
        missing_modules[mod] = required_infos

    if use_static:
        # 靜態模式: 4 層 probe + mtime cache
        # 計算 effective_sys_path = project src + venv site-packages + 當前 sys.path
        # 這個 list 同時用於 cache 簽名與 probe extra_paths
        effective_sys_path: list[str] = []
        if project_dir and src_dirs:
            for src in src_dirs:
                p = os.path.join(project_dir, src)
                if os.path.exists(p):
                    effective_sys_path.append(p)
            effective_sys_path.append(project_dir)
        # --venv 指定的外部虛擬環境 site-packages
        venv_extra: list[str] = _venv_site_packages(venv_path) if venv_path else []
        effective_sys_path.extend(venv_extra)
        # 簽名也納入當前 sys.path 確保 venv 切換能 invalidate
        cache_signature_paths = list(effective_sys_path) + list(sys.path)
        cache = _FindSpecCache(project_dir, cache_signature_paths)

        # extra_paths 同時用於 probe (尊重 --venv)
        probe_extra = venv_extra or None

        # 先掃 cache 命中,沒命中的才丟並行
        to_check: list[str] = []
        for m in unique_modules:
            cached = cache.get(m)
            if cached is None:
                to_check.append(m)
            elif not cached[0]:
                _record_error(m, cached[1] or "Module not found")

        if to_check:
            workers = max_workers or calculate_optimal_workers(len(to_check))
            if should_use_thread_pool(len(to_check), work_kind="cpu"):
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {executor.submit(check_module_importable_static, m, project_dir, src_dirs, probe_extra): m for m in to_check}
                    for future in as_completed(futures):
                        module, error = future.result()
                        cache.set(module, error)
                        if error:
                            _record_error(module, error)
            else:
                for m in to_check:
                    module, error = check_module_importable_static(m, project_dir, src_dirs, probe_extra)
                    cache.set(module, error)
                    if error:
                        _record_error(module, error)
        cache.flush()
        return missing_modules

    # 執行模式必須維持每個模組獨立 subprocess，避免前一個 import 污染後續結果。
    workers = max_workers or calculate_optimal_workers(len(unique_modules))
    if should_use_thread_pool(len(unique_modules), work_kind="io"):
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(check_module_importable, m, project_dir, src_dirs, timeout, venv_path): m
                for m in unique_modules
            }
            for future in as_completed(futures):
                module, error = future.result()
                if error:
                    _record_error(module, error)
    else:
        for m in unique_modules:
            module, error = check_module_importable(m, project_dir, src_dirs, timeout, venv_path)
            if error:
                _record_error(module, error)

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
    total_errors = 0

    if args.check_relative and all_relative_imports:
        has_issues = True
        for rel_import in all_relative_imports:
            # 錯誤訊息不受 --quiet 影響,總是顯示
            print(t("imports.standalone.relative_warning", rel_import["file"], rel_import["line"], rel_import["statement"]))

    if missing_modules:
        has_issues = True
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
