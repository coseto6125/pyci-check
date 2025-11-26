"""檢查專案中所有 Python 檔案的語法是否正確."""

import ast
import glob
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pyci_check.utils import calculate_optimal_workers, get_exclude_dirs_set, safe_relpath, should_exclude_path


def _has_symlink_in_path(file_path: str, base_dir: str) -> bool:
    """
    檢查檔案路徑中是否包含符號連結 (使用 pathlib).

    Args:
        file_path: 完整檔案路徑
        base_dir: 基準目錄

    Returns:
        True 如果路徑中包含符號連結
    """
    try:
        file_p = Path(file_path)
        base_p = Path(base_dir).resolve()

        # 逐層檢查每個父目錄（不使用 resolve 以保留符號連結）
        current = file_p
        while True:
            if current.resolve() == base_p:
                break
            if current.is_symlink():
                return True
            parent = current.parent
            if parent == current:  # 到達根目錄
                break
            current = parent

        return False
    except (OSError, ValueError):
        # 路徑無效或無法解析
        return False


def find_python_files(directory: str, exclude_dirs: list[str] | None = None) -> list[str]:
    """
    找出指定目錄下所有的 Python 檔案 (優化版本).

    Args:
        directory: 要搜尋的目錄
        exclude_dirs: 要排除的目錄列表

    Returns:
        Python 檔案路徑列表
    """
    exclude_set = get_exclude_dirs_set() if exclude_dirs is None else frozenset(exclude_dirs)

    ignore_files = frozenset({"starlette_app.py", "sanic_app.py"})

    # 使用 glob 遞迴搜尋 (比 pathlib.rglob 快)
    pattern = os.path.join(directory, "**", "*.py")
    python_files = [
        file_path
        for file_path in glob.glob(pattern, recursive=True)
        if (
            os.path.basename(file_path) not in ignore_files
            and not should_exclude_path(file_path, exclude_set)
            and not _has_symlink_in_path(file_path, directory)  # 排除路徑中包含符號連結的檔案
        )
    ]

    return sorted(python_files)


def check_file_syntax(file_path: str) -> tuple[bool, str]:
    """
    檢查單一檔案的語法 (優化版本 - 僅讀取一次).

    Args:
        file_path: 檔案路徑

    Returns:
        (是否正確, 錯誤訊息)
    """
    try:
        # 使用 utf-8-sig 自動處理 BOM
        with open(file_path, encoding="utf-8-sig") as f:
            source = f.read()
        ast.parse(source, filename=file_path)
        return True, ""

    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    except UnicodeDecodeError as e:
        return False, f"Encoding Error: {e}"
    except OSError as e:
        return False, f"File Error: {e}"
    except Exception as e:
        # 預期外的錯誤,但仍需報告
        return False, f"Unexpected Error: {e}"


def check_files_parallel(python_files: list[str]) -> tuple[int, int, list]:
    """
    並行檢查多個檔案的語法 (優化版本).

    Args:
        python_files: Python 檔案列表

    Returns:
        (成功數量, 錯誤數量, 錯誤列表)
    """
    if not python_files:
        return 0, 0, []

    max_workers = calculate_optimal_workers(len(python_files))
    current_dir = os.getcwd()

    errors = []
    success_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(check_file_syntax, fp): fp for fp in python_files}

        for future in as_completed(future_to_file):
            file_path = future_to_file[future]

            try:
                is_valid, error_msg = future.result()

                if is_valid:
                    success_count += 1
                else:
                    relative_path = safe_relpath(file_path, current_dir)
                    errors.append((relative_path, error_msg))

            except Exception as exc:
                relative_path = safe_relpath(file_path, current_dir)
                errors.append((relative_path, f"Exception: {exc}"))

    error_count = len(errors)
    return success_count, error_count, errors


def main() -> None:
    """主程式."""
    current_dir = os.getcwd()
    python_files = find_python_files(current_dir)

    if not python_files:
        sys.exit(0)

    _success_count, _error_count, errors = check_files_parallel(python_files)

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
