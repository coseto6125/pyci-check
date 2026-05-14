"""測試：測試純潔度與隔離性 (Test Purity)."""

import pytest
from pathlib import Path
import argparse
from pyci_check.cli import check_side_effects


def test_purity_check_disabled_by_default(tmp_path: Path, capsys, monkeypatch):
    """預設不開啟純潔度檢查，測試檔案中使用 socket 應該沒事."""
    monkeypatch.chdir(tmp_path)

    test_file = tmp_path / "test_network.py"
    test_file.write_text(
        """
import socket
def test_socket():
    s = socket.socket()
    s.close()
""",
        encoding="utf-8",
    )

    args = argparse.Namespace(quiet=False)
    exit_code = check_side_effects(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "socket.socket" not in captured.out


def test_purity_check_enabled_warns_on_socket(tmp_path: Path, capsys, monkeypatch):
    """開啟純潔度檢查後，test_ 檔案使用 socket 會觸發警告."""
    monkeypatch.chdir(tmp_path)

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.pyci-check]
check-test-purity = true
""",
        encoding="utf-8",
    )

    test_file = tmp_path / "test_network.py"
    test_file.write_text(
        """
import socket
def test_func():
    s = socket.socket()
""",
        encoding="utf-8",
    )

    args = argparse.Namespace(quiet=False)
    exit_code = check_side_effects(args)

    # 預期回傳 0 (因為只是 warning)
    assert exit_code == 0

    captured = capsys.readouterr()
    # 但應該要在 stdout 中看到警告
    assert "socket.socket" in captured.out
    assert "Impure test" in captured.out


def test_purity_check_ignores_non_test_files(tmp_path: Path, capsys, monkeypatch):
    """開啟純潔度檢查，但非 test_ 檔案使用 socket 不會觸發純潔度警告."""
    monkeypatch.chdir(tmp_path)

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.pyci-check]
check-test-purity = true
""",
        encoding="utf-8",
    )

    # 注意這裡的檔名沒有 test_
    prod_file = tmp_path / "network_utils.py"
    prod_file.write_text(
        """
import socket
def connect():
    s = socket.socket()
    s.close()
""",
        encoding="utf-8",
    )

    args = argparse.Namespace(quiet=False)
    exit_code = check_side_effects(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "socket.socket" not in captured.out
