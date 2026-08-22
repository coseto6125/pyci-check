"""
全局依賴健康度檢查 (Dependency Health Check).

檢查專案中的：
1. 幽靈依賴 (Phantom Dependencies): 使用了但未在 pyproject.toml/requirements.txt 中宣告的依賴。
2. 冗餘依賴 (Orphan Dependencies): 宣告了但在專案中完全沒有使用的依賴。
"""

import os
import re

from pyci_check.config import load
from pyci_check.utils import stdlib_top_levels


def parse_requirements_txt(req_path: str) -> set[str]:
    """從 requirements.txt 提取依賴包名稱."""
    deps = set()
    if not os.path.exists(req_path):
        return deps

    try:
        with open(req_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(("#", "-r", "-c", "--")):
                    continue
                # 移除版本號、環境標記等 (例如 requests>=2.0.0; python_version < '3.7')
                # 簡單處理: 取第一個非字母數字底線橫線字元前的部分
                match = re.match(r"^([a-zA-Z0-9_\-]+)", line)
                if match:
                    deps.add(match.group(1))
    except OSError:
        pass
    return {d.lower().replace("_", "-") for d in deps}


def get_declared_dependencies(project_dir: str) -> set[str]:
    """
    獲取專案宣告的所有依賴 (包名).

    pyproject 與 requirements 變體都以同一個 config root 為基準:
    pyproject 的解析 (含往上層搜尋) 走 config.load 的快取結果.
    """
    cfg = load(project_dir)
    all_deps = set(cfg.declared_deps)

    # requirements.txt 及常見變體,與 pyproject 放在同一個 root
    root = os.path.dirname(cfg.pyproject_path) if cfg.pyproject_path else cfg.project_dir
    for req_file in ("requirements.txt", "requirements-dev.txt", "dev-requirements.txt"):
        path = os.path.join(root, req_file)
        if os.path.exists(path):
            all_deps.update(parse_requirements_txt(path))

    return all_deps


def find_dependency_issues(project_dir: str, imported_modules: set[str], local_modules: set[str]) -> dict[str, set[str]]:
    """
    分析依賴問題.

    Args:
        project_dir: 專案根目錄
        imported_modules: 程式碼中使用的所有頂層模組名
        local_modules: 專案自身的模組名 (應排除在第三方檢查外)

    Returns:
        {"phantom": set(), "orphan": set()}
    """
    declared_packages = get_declared_dependencies(project_dir)
    stdlib = stdlib_top_levels()

    # 獲取模組到包的映射 (需在當前環境執行)
    import importlib.metadata

    try:
        module_to_pkg = importlib.metadata.packages_distributions()
    except Exception:
        module_to_pkg = {}

    # 1. 幽靈依賴 (Phantom): 使用了，但沒宣告
    phantom = set()
    for mod in imported_modules:
        if mod in stdlib or mod in local_modules or mod == "setup":
            continue

        # 找出該模組屬於哪些包
        pkgs = module_to_pkg.get(mod, [mod])
        # 只要其中一個包有宣告，就算過關
        if not any(p.lower().replace("_", "-") in declared_packages for p in pkgs):
            phantom.add(mod)

    # 2. 冗餘依賴 (Orphan): 宣告了，但沒用到
    # 需要 反向映射: package -> modules
    pkg_to_modules = {}
    for mod, pkgs in module_to_pkg.items():
        for p in pkgs:
            p_norm = p.lower().replace("_", "-")
            if p_norm not in pkg_to_modules:
                pkg_to_modules[p_norm] = set()
            pkg_to_modules[p_norm].add(mod)

    orphan = set()
    for pkg in declared_packages:
        # 如果這個包對應的模組都沒有出現在 imported_modules 中
        mods = pkg_to_modules.get(pkg, {pkg.replace("-", "_")})
        if not any(m in imported_modules for m in mods):
            # 排除常見的工具類包 (未必會在代碼中 import)
            if pkg in {"pytest", "pytest-cov", "ruff", "black", "mypy", "tox", "flake8", "isort"}:
                continue
            orphan.add(pkg)

    return {"phantom": phantom, "orphan": orphan}
