"""測試 CLI 功能."""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class TestCLI:
    """CLI 測試."""

    def test_cli_help(self):
        """測試 --help 選項."""
        result = subprocess.run(
            [sys.executable, "-m", "pyci_check.cli", "--help"],
            capture_output=True,
            text=True,
            check=False,
            env={"PYTHONPATH": "src"},
        )

        assert result.returncode == 0
        assert "pyci-check" in result.stdout
        assert "syntax" in result.stdout
        assert "imports" in result.stdout

    def test_cli_syntax_command(self):
        """測試 syntax 子命令."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 創建有效的 Python 檔案
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')\n")

            import os

            pythonpath = os.path.join(os.getcwd(), "src")
            env = os.environ.copy()
            env["PYTHONPATH"] = pythonpath

            result = subprocess.run(
                [sys.executable, "-m", "pyci_check.cli", "syntax"],
                capture_output=True,
                text=True,
                check=False,
                cwd=tmpdir,
                env=env,
            )

            assert result.returncode == 0

    def test_cli_syntax_with_error(self, pythonpath_env):
        """測試檢測語法錯誤."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 創建語法錯誤的檔案
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('unclosed\n")

            result = subprocess.run(
                [sys.executable, "-m", "pyci_check.cli", "syntax"],
                capture_output=True,
                text=True,
                check=False,
                cwd=tmpdir,
                env=pythonpath_env,
            )

            assert result.returncode == 1
            assert "SyntaxError" in result.stdout or "SyntaxError" in result.stderr

    def test_cli_quiet_mode(self, pythonpath_env):
        """測試安靜模式."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 創建有效的 Python 檔案
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')\n")

            result = subprocess.run(
                [sys.executable, "-m", "pyci_check.cli", "syntax", "--quiet"],
                capture_output=True,
                text=True,
                check=False,
                cwd=tmpdir,
                env=pythonpath_env,
            )

            assert result.returncode == 0
            # 安靜模式不應該有輸出（成功時）
            assert len(result.stdout) == 0 or "Checking" not in result.stdout
