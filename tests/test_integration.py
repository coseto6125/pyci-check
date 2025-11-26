"""整合測試."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class TestIntegration:
    """整合測試."""

    def test_full_workflow_syntax_check(self, project_root, temp_project):
        """測試完整的語法檢查流程."""
        # 設定環境
        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        # 執行 syntax 檢查
        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "syntax"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_project),
            env=env,
        )

        assert result.returncode == 0

    def test_full_workflow_with_syntax_error(self, project_root, temp_dir):
        """測試檢測語法錯誤的完整流程."""
        # 創建語法錯誤的檔案
        (temp_dir / "error.py").write_text("def incomplete(")

        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "syntax"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_dir),
            env=env,
        )

        assert result.returncode == 1
        assert "SyntaxError" in result.stdout or "SyntaxError" in result.stderr

    def test_quiet_mode_no_output(self, project_root, temp_project):
        """測試安靜模式沒有輸出."""
        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "syntax", "--quiet"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_project),
            env=env,
        )

        assert result.returncode == 0
        # 安靜模式成功時應該沒有輸出
        assert len(result.stdout) == 0 or "Checking" not in result.stdout

    def test_help_command(self, project_root):
        """測試 --help 命令."""
        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "--help"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        assert result.returncode == 0
        assert "pyci-check" in result.stdout
        assert "syntax" in result.stdout

    def test_parallel_file_checking(self, project_root, temp_dir):
        """測試並行檢查多個檔案."""
        # 創建多個檔案
        for i in range(20):
            (temp_dir / f"file{i}.py").write_text(f"print('file {i}')")

        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "syntax"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_dir),
            env=env,
        )

        assert result.returncode == 0

    def test_mixed_valid_and_invalid_files(self, project_root, temp_dir):
        """測試混合有效和無效的檔案."""
        # 創建有效檔案
        (temp_dir / "valid.py").write_text("import os\nprint('ok')")

        # 創建無效檔案
        (temp_dir / "invalid.py").write_text("print('unclosed")

        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "syntax"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_dir),
            env=env,
        )

        assert result.returncode == 1

    def test_exclude_directories(self, project_root, temp_dir):
        """測試排除目錄功能."""
        # 創建目錄結構
        (temp_dir / "src").mkdir()
        (temp_dir / ".venv").mkdir()
        (temp_dir / "src" / "main.py").write_text("import os")
        (temp_dir / ".venv" / "bad.py").write_text("print('unclosed")

        # 創建 pyproject.toml 排除 .venv
        (temp_dir / "pyproject.toml").write_text("""
[tool.ruff]
src = ["src"]
exclude = [".venv"]
""")

        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "syntax"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_dir),
            env=env,
        )

        # 應該成功，因為 .venv 被排除了
        assert result.returncode == 0

    def test_large_project_performance(self, project_root, temp_dir):
        """測試大型專案的效能."""
        # 創建 100 個檔案
        for i in range(100):
            (temp_dir / f"file{i}.py").write_text(
                f"import os\nimport sys\nprint('file {i}')\n",
            )

        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        import time

        start = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "syntax", "--quiet"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_dir),
            env=env,
        )
        elapsed = time.time() - start

        assert result.returncode == 0
        # 100 個檔案應該在合理時間內完成（10 秒）
        assert elapsed < 10.0

    def test_unicode_in_files(self, project_root, temp_dir):
        """測試包含 Unicode 字元的檔案."""
        (temp_dir / "unicode.py").write_text(
            "# -*- coding: utf-8 -*-\nprint('你好世界 🌍')\n",
            encoding="utf-8",
        )

        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "syntax"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_dir),
            env=env,
        )

        assert result.returncode == 0

    def test_error_reporting_format(self, project_root, temp_dir):
        """測試錯誤報告格式."""
        (temp_dir / "error.py").write_text("def test(\npass")

        pythonpath = str(project_root / "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "syntax"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_dir),
            env=env,
        )

        assert result.returncode == 1
        # 錯誤報告應包含檔案名稱
        assert "error.py" in result.stdout or "error.py" in result.stderr
