"""共用工具函數."""

import os
import sys
import sysconfig
from functools import lru_cache


# Free-threaded build 偵測 (PEP 703, **Python 3.13t / 3.14t / ...** — 必須是含 't' 後綴的 build)。
# 條件:
#   1. Python >= 3.13 (PEP 703 最早的 free-threaded build)
#   2. sysconfig 報告 Py_GIL_DISABLED == 1 (這是 canonical 判斷,
#      只有 ./configure --disable-gil 編出來的 interpreter 會回 1)
# 注意: 一般 3.13/3.14/3.15 等非 't' 後綴的 build 仍有 GIL,此值為 False。
# True 時 ThreadPoolExecutor 為真並行 (CPU-bound 工作自動受益);
# False 時 ThreadPool 只對 I/O / subprocess 有用。
def _is_free_threaded_build() -> bool:
    """回傳目前 interpreter 是否為 free-threaded build."""
    return sys.version_info >= (3, 13) and str(sysconfig.get_config_var("Py_GIL_DISABLED")) == "1"


IS_FREE_THREADED: bool = _is_free_threaded_build()


def should_use_thread_pool(task_count: int, work_kind: str = "cpu") -> bool:
    """
    決定是否值得啟動 ThreadPool.

    Free-threaded build: 任何 task 數都用 ThreadPool (真並行).
    一般 build CPU-bound (ast.parse): 小 repo serial 比較快 (省 thread bootstrap).
    一般 build I/O-bound (subprocess): 仍用 ThreadPool 拿 I/O 重疊收益.

    Args:
        task_count: 任務數量
        work_kind: "cpu" 或 "io"

    Returns:
        True 表示啟動 ThreadPool
    """
    if IS_FREE_THREADED:
        return task_count >= 2
    if work_kind == "io":
        return task_count >= 4
    # GIL build + CPU-bound: ast.parse 每檔 ~0.2ms，thread bootstrap 數十 ms
    return task_count >= 200


def calculate_optimal_workers(task_count: int) -> int:
    """
    計算最佳的 worker 數量.

    Args:
        task_count: 任務數量

    Returns:
        最佳的 worker 數量
    """
    cpu_count = os.cpu_count() or 1
    # I/O 密集: CPU * 2,上限 32
    return max(1, min(cpu_count * 2, 32, task_count))


@lru_cache(maxsize=1)
def get_exclude_dirs_set() -> frozenset[str]:
    """取得預設排除目錄集合 (快取)."""
    return frozenset(
        {
            "__pycache__",
            ".git",
            "venv",
            "env",
            ".venv",
            "node_modules",
            "htmlcov",
            ".pytest_cache",
            "build",
            "dist",
            ".eggs",
            "*.egg-info",
        }
    )


def should_exclude_path(file_path: str, exclude_dirs: frozenset[str]) -> bool:
    """
    檢查路徑是否應被排除 (優化版本).

    Args:
        file_path: 檔案路徑
        exclude_dirs: 排除目錄集合

    Returns:
        是否應排除
    """
    # 使用 parts 進行集合交集,比字串 in 檢查快很多
    # 將路徑分割為各個部分
    path_parts = set(file_path.replace("\\", "/").split("/"))
    return bool(path_parts & exclude_dirs)


def walk_python_files(
    directory: str,
    exclude_dirs: frozenset[str],
    ignore_files: frozenset[str] = frozenset(),
) -> list[str]:
    """
    走訪目錄收集 .py 檔案，於 walk 過程 prune 排除目錄、跳過符號連結.

    一次 os.walk 解決三件事:
    1. exclude_dirs prune
    2. followlinks=False 自動跳過符號連結目錄 (不需事後 lstat)
    3. ignore_files 過濾

    比 glob.glob + 事後過濾快 (在中型 repo 上)，且 prune 在 walk 階段就避免 stat 大量檔案。

    Args:
        directory: 要搜尋的目錄
        exclude_dirs: 排除目錄集合 (basename match)
        ignore_files: 排除檔名集合 (basename match)

    Returns:
        排序後的 .py 檔案路徑列表
    """
    python_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        # In-place prune: 只排除明確列出的目錄，保留使用者可掃描其他 dot-dir 的能力。
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        python_files.extend(os.path.join(dirpath, f) for f in filenames if f.endswith(".py") and f not in ignore_files)

    python_files.sort()
    return python_files


def safe_relpath(path: str, start: str) -> str:
    """
    安全的相對路徑計算,處理跨磁碟機的情況.

    在 Windows 上,如果 path 和 start 在不同磁碟機上,
    os.path.relpath() 會拋出 ValueError。
    此函式在這種情況下返回絕對路徑。

    Args:
        path: 目標路徑
        start: 起始路徑

    Returns:
        相對路徑,如果無法計算則返回絕對路徑
    """
    try:
        return os.path.relpath(path, start)
    except ValueError:
        # 跨磁碟機時返回絕對路徑
        return os.path.abspath(path)
