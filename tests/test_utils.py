"""測試工具函數."""

import os

import pytest

from pyci_check import utils
from pyci_check.imports import extract_from_all_files
from pyci_check.syntax import check_files_parallel
from pyci_check.utils import calculate_optimal_workers, get_exclude_dirs_set, should_exclude_path, walk_python_files


class TestUtils:
    """工具函數測試."""

    def test_calculate_optimal_workers_small(self):
        """測試小型檔案數的 worker 計算."""
        workers = calculate_optimal_workers(5)
        assert workers > 0
        assert workers <= 32

    def test_calculate_optimal_workers_large(self):
        """測試大型檔案數的 worker 計算."""
        workers = calculate_optimal_workers(100)
        assert workers > 0
        assert workers <= 32

    def test_calculate_optimal_workers_zero(self):
        """測試零檔案的 worker 計算."""
        workers = calculate_optimal_workers(0)
        assert workers > 0

    def test_get_exclude_dirs_set(self):
        """測試取得排除目錄集合."""
        exclude_set = get_exclude_dirs_set()

        assert isinstance(exclude_set, frozenset)
        assert ".venv" in exclude_set
        assert "venv" in exclude_set
        assert "__pycache__" in exclude_set
        assert ".git" in exclude_set

    def test_should_exclude_path_venv(self, temp_dir):
        """測試排除 .venv 路徑."""
        venv_path = temp_dir / ".venv" / "test.py"
        exclude_set = get_exclude_dirs_set()

        # should_exclude_path 需要字串而非 Path 物件
        assert should_exclude_path(str(venv_path), exclude_set) is True

    def test_should_exclude_path_normal(self, temp_dir):
        """測試不排除正常路徑."""
        normal_path = temp_dir / "src" / "test.py"
        exclude_set = get_exclude_dirs_set()

        # should_exclude_path 需要字串而非 Path 物件
        assert should_exclude_path(str(normal_path), exclude_set) is False

    def test_should_exclude_path_pycache(self, temp_dir):
        """測試排除 __pycache__ 路徑."""
        cache_path = temp_dir / "src" / "__pycache__" / "test.pyc"
        exclude_set = get_exclude_dirs_set()

        # should_exclude_path 需要字串而非 Path 物件
        assert should_exclude_path(str(cache_path), exclude_set) is True

    def test_walk_python_files_respects_exclude_ignore_and_symlinks(self, temp_dir):
        """walk_python_files 應排除指定目錄/檔案，且不追蹤目錄 symlink."""
        keep_dir = temp_dir / "keep"
        ignore_dir = temp_dir / "ignore_me"
        dot_dir = temp_dir / ".scripts"
        keep_dir.mkdir()
        ignore_dir.mkdir()
        dot_dir.mkdir()

        (keep_dir / "a.py").write_text("A = 1\n", encoding="utf-8")
        (keep_dir / "ignored.py").write_text("IGNORED = True\n", encoding="utf-8")
        (keep_dir / "b.txt").write_text("not python\n", encoding="utf-8")
        (ignore_dir / "c.py").write_text("C = 3\n", encoding="utf-8")
        (dot_dir / "task.py").write_text("TASK = 1\n", encoding="utf-8")

        symlink_dir = temp_dir / "via_symlink"
        try:
            os.symlink(keep_dir, symlink_dir, target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            pytest.skip("平台不支援建立目錄 symlink")

        found = walk_python_files(temp_dir, frozenset({ignore_dir.name}), frozenset({"ignored.py"}))

        found_rel = [os.path.relpath(path, temp_dir).replace("\\", "/") for path in found]
        assert found_rel == [".scripts/task.py", "keep/a.py"]

    def test_should_use_thread_pool_branches_for_cpu_and_io(self, monkeypatch):
        """覆蓋一般 GIL 與 free-threaded build 下的 thread pool 決策."""
        monkeypatch.setattr(utils, "IS_FREE_THREADED", False)

        assert utils.should_use_thread_pool(1, work_kind="cpu") is False
        assert utils.should_use_thread_pool(199, work_kind="cpu") is False
        assert utils.should_use_thread_pool(200, work_kind="cpu") is True
        assert utils.should_use_thread_pool(3, work_kind="io") is False
        assert utils.should_use_thread_pool(4, work_kind="io") is True

        monkeypatch.setattr(utils, "IS_FREE_THREADED", True)
        assert utils.should_use_thread_pool(1, work_kind="cpu") is False
        assert utils.should_use_thread_pool(2, work_kind="cpu") is True

    def test_is_free_threaded_build_accepts_string_config_var(self, monkeypatch):
        """Py_GIL_DISABLED 回傳字串 '1' 時也應判定為 free-threaded."""
        monkeypatch.setattr(utils.sys, "version_info", (3, 13, 0))
        monkeypatch.setattr(utils.sysconfig, "get_config_var", lambda _name: "1")

        assert utils._is_free_threaded_build() is True

    def test_check_files_parallel_small_and_large_sets(self, temp_dir):
        """小/大檔案集合都應回傳正確語法檢查結果."""
        small_file = temp_dir / "small.py"
        small_file.write_text("X = 1\n", encoding="utf-8")

        success_count, error_count, errors = check_files_parallel([str(small_file)])
        assert (success_count, error_count, errors) == (1, 0, [])

        large_files = []
        for index in range(200):
            file_path = temp_dir / f"large_{index}.py"
            file_path.write_text(f"VALUE = {index}\n", encoding="utf-8")
            large_files.append(str(file_path))

        success_count, error_count, errors = check_files_parallel(large_files)
        assert success_count == 200
        assert error_count == 0
        assert errors == []

    def test_extract_from_all_files_small_and_large_sets(self, temp_dir):
        """小/大檔案集合都應正確收集 import."""
        small_file = temp_dir / "small_import.py"
        small_file.write_text("import os\n", encoding="utf-8")

        imports, relative_imports = extract_from_all_files(str(temp_dir), target_files=[str(small_file)])
        assert {info["module"] for info in imports} == {"os"}
        assert relative_imports == []

        large_files = []
        for index in range(200):
            file_path = temp_dir / f"large_import_{index}.py"
            file_path.write_text("import sys\n", encoding="utf-8")
            large_files.append(str(file_path))

        imports, relative_imports = extract_from_all_files(str(temp_dir), target_files=large_files)
        assert len(imports) == 200
        assert {info["module"] for info in imports} == {"sys"}
        assert relative_imports == []
