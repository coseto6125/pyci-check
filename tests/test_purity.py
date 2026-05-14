"""測試：測試純潔度與隔離性 (Test Purity)."""

import os
import subprocess
import sys
from pathlib import Path


def test_purity_check_disabled_by_default(tmp_path: Path):
    """預設不開啟純潔度檢查，測試檔案中使用 socket 應該沒事."""
    test_file = tmp_path / "test_network.py"
    test_file.write_text("""
import socket
def test_socket():
    s = socket.socket()
    s.close()
""", encoding="utf-8")

    # 執行 side-effects 檢查
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-m", "pyci_check.cli", "side-effects"],
        check=False, cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True
    )

    # 預期成功且沒有警告
    assert result.returncode == 0
    assert "socket.socket" not in result.stdout

def test_purity_check_enabled_warns_on_socket(tmp_path: Path):
    """開啟純潔度檢查後，test_ 檔案使用 socket 會觸發警告."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.pyci-check]
check-test-purity = true
""", encoding="utf-8")

    test_file = tmp_path / "test_network.py"
    test_file.write_text("""
import socket
def test_func():
    s = socket.socket()
""", encoding="utf-8")

    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-m", "pyci_check.cli", "side-effects"],
        check=False, cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True
    )

    # 預期回傳 0 (因為只是 warning)
    assert result.returncode == 0
    # 但應該要在 stdout 中看到警告
    assert "socket.socket" in result.stdout
    assert "Impure test" in result.stdout

def test_purity_check_ignores_non_test_files(tmp_path: Path):
    """開啟純潔度檢查，但非 test_ 檔案使用 socket 不會觸發純潔度警告."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.pyci-check]
check-test-purity = true
""", encoding="utf-8")

    # 注意這裡的檔名沒有 test_
    prod_file = tmp_path / "network_utils.py"
    prod_file.write_text("""
import socket
def connect():
    s = socket.socket()
    s.close()
""", encoding="utf-8")

    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-m", "pyci_check.cli", "side-effects"],
        check=False, cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True
    )

    # 預期成功且沒有警告
    assert result.returncode == 0
    assert "socket.socket" not in result.stdout
