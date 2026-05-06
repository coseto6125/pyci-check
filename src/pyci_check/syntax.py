"""檢查專案中所有 Python 檔案的語法是否正確."""

import ast
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from pyci_check.i18n import t
from pyci_check.utils import calculate_optimal_workers, get_exclude_dirs_set, safe_relpath, should_use_thread_pool, walk_python_files


def find_python_files(directory: str, exclude_dirs: list[str] | None = None) -> list[str]:
    """
    找出指定目錄下所有的 Python 檔案.

    用 os.walk(followlinks=False) 在 walk 過程 prune 排除目錄、跳過符號連結；
    比 glob.glob + 事後過濾快約 3-5x。

    Args:
        directory: 要搜尋的目錄
        exclude_dirs: 要排除的目錄列表

    Returns:
        Python 檔案路徑列表
    """
    exclude_set = get_exclude_dirs_set() if exclude_dirs is None else frozenset(exclude_dirs)
    ignore_files = frozenset({"starlette_app.py", "sanic_app.py"})
    return walk_python_files(directory, exclude_set, ignore_files)


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
        return False, t("syntax.error.syntax_error", e)
    except UnicodeDecodeError as e:
        return False, t("syntax.error.encoding_error", e)
    except OSError as e:
        return False, t("syntax.error.file_error", e)
    except Exception as e:
        # 預期外的錯誤,但仍需報告
        return False, t("syntax.error.unexpected_error", e)


def check_files_parallel(python_files: list[str]) -> tuple[int, int, list]:
    """
    檢查多個檔案的語法 (自適應並行).

    GIL build 對 CPU-bound 的 ast.parse 並行收益有限,小 repo (<200) serial 反而快;
    free-threaded (3.13t) 上 ThreadPool 為真並行,所有規模都受益。

    Args:
        python_files: Python 檔案列表

    Returns:
        (成功數量, 錯誤數量, 錯誤列表)
    """
    if not python_files:
        return 0, 0, []

    current_dir = os.getcwd()
    errors: list[tuple[str, str]] = []
    success_count = 0

    if should_use_thread_pool(len(python_files), work_kind="cpu"):
        max_workers = calculate_optimal_workers(len(python_files))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(check_file_syntax, fp): fp for fp in python_files}
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    is_valid, error_msg = future.result()
                    if is_valid:
                        success_count += 1
                    else:
                        errors.append((safe_relpath(file_path, current_dir), error_msg))
                except Exception as exc:
                    errors.append((safe_relpath(file_path, current_dir), t("syntax.error.exception", exc)))
    else:
        # 小 repo serial: 省 thread bootstrap 開銷
        for fp in python_files:
            try:
                is_valid, error_msg = check_file_syntax(fp)
                if is_valid:
                    success_count += 1
                else:
                    errors.append((safe_relpath(fp, current_dir), error_msg))
            except Exception as exc:
                errors.append((safe_relpath(fp, current_dir), t("syntax.error.exception", exc)))

    return success_count, len(errors), errors


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
