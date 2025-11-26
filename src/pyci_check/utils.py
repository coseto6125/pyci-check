"""共用工具函數."""

import os
from functools import lru_cache


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
    return frozenset({
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
    })


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
