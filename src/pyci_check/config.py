"""
專案設定載入：pyproject.toml 的單一窗口.

所有 pyproject 設定的讀取集中在這個 module:
- 往上層搜尋 pyproject.toml (唯一一份搜尋邏輯)
- 合併 [tool.pyci-check] 與 [tool.ruff] 的 exclude / extend-exclude / src
- 解析 venv、language、check-test-purity

快取屬於 implementation 細節,caller 不需知道;測試需要隔離時呼叫 clear_cache().
"""

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """單一專案目錄解析後的全部設定."""

    project_dir: str
    pyproject_path: str | None
    src_dirs: tuple[str, ...]
    exclude_dirs: frozenset[str]
    exclude_files: frozenset[str]
    check_test_purity: bool
    venv_setting: str | None
    language: str


def find_pyproject(project_dir: str) -> str | None:
    """從 project_dir 往上層搜尋 pyproject.toml,包含 project_dir 本身."""
    current = os.path.abspath(project_dir)
    while True:
        candidate = os.path.join(current, "pyproject.toml")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:  # 已到根目錄
            return None
        current = parent


def _as_str_list(value: object) -> list[str]:
    """TOML 設定值正規化為字串清單 (允許單一字串)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _split_exclude(items: set[str]) -> tuple[frozenset[str], frozenset[str]]:
    """依「basename 有副檔名視為檔案」把排除項分成目錄與檔案兩組."""
    dirs: set[str] = set()
    files: set[str] = set()
    for item in items:
        stripped = item.rstrip("/")
        basename = os.path.basename(stripped)
        if "." in basename and not stripped.startswith("."):
            files.add(stripped)
        else:
            dirs.add(stripped)
    return frozenset(dirs), frozenset(files)


@lru_cache(maxsize=128)
def load(project_dir: str = ".") -> ProjectConfig:
    """載入專案設定 (結果依 project_dir 快取)."""
    pyproject_path = find_pyproject(project_dir)

    data: dict = {}
    if pyproject_path is not None:
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            data = {}

    ruff = data.get("tool", {}).get("ruff", {})
    pyci_check = data.get("tool", {}).get("pyci-check", {})

    exclude_items: set[str] = set()
    exclude_items.update(_as_str_list(pyci_check.get("exclude")))
    exclude_items.update(_as_str_list(pyci_check.get("extend-exclude")))
    exclude_items.update(_as_str_list(ruff.get("exclude")))
    exclude_items.update(_as_str_list(ruff.get("extend-exclude")))
    exclude_dirs, exclude_files = _split_exclude(exclude_items)

    venv_setting = pyci_check.get("venv")
    language = pyci_check.get("language")

    return ProjectConfig(
        project_dir=os.path.abspath(project_dir),
        pyproject_path=pyproject_path,
        src_dirs=tuple(_as_str_list(ruff.get("src"))),
        exclude_dirs=exclude_dirs,
        exclude_files=exclude_files,
        check_test_purity=bool(pyci_check.get("check-test-purity", False)),
        venv_setting=venv_setting if isinstance(venv_setting, str) and venv_setting else None,
        language=language if isinstance(language, str) and language.strip() else "en",
    )


def resolve_venv(explicit: str | None, config: ProjectConfig) -> str | None:
    """
    解析 venv 路徑.

    優先順序: CLI 參數 > pyproject.toml [tool.pyci-check].venv > 自動偵測 .venv.
    """
    if explicit:
        return explicit
    if config.venv_setting:
        return config.venv_setting
    if os.path.exists(os.path.join(config.project_dir, ".venv")):
        return "."
    return None


def clear_cache() -> None:
    """清空設定快取 (測試隔離用)."""
    load.cache_clear()
