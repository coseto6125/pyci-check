"""測試工具函數."""

import pytest

from pyci_check.utils import calculate_optimal_workers, get_exclude_dirs_set, should_exclude_path


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
