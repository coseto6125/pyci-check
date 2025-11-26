"""測試語法檢查功能."""

import tempfile
from pathlib import Path

import pytest

from pyci_check.syntax import check_file_syntax, check_files_parallel, find_python_files


class TestSyntaxChecker:
    """語法檢查測試."""

    def test_check_valid_syntax(self):
        """測試有效的 Python 語法."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('hello world')\n")
            f.flush()
            temp_path = f.name

        is_valid, error = check_file_syntax(temp_path)
        Path(temp_path).unlink()

        assert is_valid is True
        assert error == ""

    def test_check_invalid_syntax(self):
        """測試無效的 Python 語法."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('unclosed string\n")
            f.flush()
            temp_path = f.name

        is_valid, error = check_file_syntax(temp_path)
        Path(temp_path).unlink()

        assert is_valid is False
        assert "SyntaxError" in error

    def test_find_python_files(self):
        """測試查找 Python 檔案."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 創建測試檔案
            (Path(tmpdir) / "test1.py").write_text("print('test1')", encoding="utf-8")
            (Path(tmpdir) / "test2.py").write_text("print('test2')", encoding="utf-8")
            (Path(tmpdir) / "test.txt").write_text("not python", encoding="utf-8")

            # 創建應排除的目錄
            venv_dir = Path(tmpdir) / ".venv"
            venv_dir.mkdir()
            (venv_dir / "test3.py").write_text("print('test3')", encoding="utf-8")

            files = find_python_files(tmpdir)

            # 應該只找到 test1.py 和 test2.py
            assert len(files) == 2
            assert all(f.endswith(".py") for f in files)
            assert not any(".venv" in f for f in files)

    def test_check_files_parallel(self):
        """測試並行檢查多個檔案."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 創建有效檔案
            valid_file = Path(tmpdir) / "valid.py"
            valid_file.write_text("print('hello')", encoding="utf-8")

            # 創建無效檔案
            invalid_file = Path(tmpdir) / "invalid.py"
            invalid_file.write_text("print('unclosed", encoding="utf-8")

            files = [str(valid_file), str(invalid_file)]
            success_count, error_count, errors = check_files_parallel(files)

            assert success_count == 1
            assert error_count == 1
            assert len(errors) == 1

    def test_check_empty_file_list(self):
        """測試空檔案列表."""
        success_count, error_count, errors = check_files_parallel([])

        assert success_count == 0
        assert error_count == 0
        assert errors == []
