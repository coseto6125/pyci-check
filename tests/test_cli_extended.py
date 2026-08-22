"""整合測試：CLI 命令與輸出."""

import argparse
from pathlib import Path

from pyci_check.cli import check_all, check_cycles, check_dependency


def test_cli_dependency_command(tmp_path: Path, capsys, monkeypatch):
    """測試 dependency 命令與輸出."""
    monkeypatch.chdir(tmp_path)

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    (src_dir / "main.py").write_text("import requests\n", encoding="utf-8")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx"]
[tool.ruff]
src = ["src"]
""",
        encoding="utf-8",
    )

    args = argparse.Namespace(quiet=False)
    exit_code = check_dependency(args)

    assert exit_code == 1

    captured = capsys.readouterr()
    stdout = captured.out

    assert "requests" in stdout
    assert "httpx" in stdout


def test_cli_cycles_command(tmp_path: Path, capsys, monkeypatch):
    """測試 cycles 命令與輸出."""
    monkeypatch.chdir(tmp_path)

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    (src_dir / "a.py").write_text("import b\n", encoding="utf-8")
    (src_dir / "b.py").write_text("import a\n", encoding="utf-8")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.ruff]
src = ["src"]
""",
        encoding="utf-8",
    )

    args = argparse.Namespace(quiet=False)
    exit_code = check_cycles(args)

    assert exit_code == 1

    captured = capsys.readouterr()
    stdout = captured.out.replace("\\", "/")

    assert "a.py -> src/b.py -> src/a.py" in stdout or "b.py -> src/a.py -> src/b.py" in stdout


def test_check_all_fail_fast_stops_at_cycles(tmp_path: Path, capsys, monkeypatch):
    """--fail-fast 應該在 cycles 階段失敗後停止,不再跑 signature 階段."""
    monkeypatch.chdir(tmp_path)

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # 階段 4 的違規: 循環引用
    (src_dir / "a.py").write_text("import b\n", encoding="utf-8")
    (src_dir / "b.py").write_text("import a\n", encoding="utf-8")

    # 階段 5 的違規: 簽章錯誤 (greet() 少了必填的 name)
    (src_dir / "defs.py").write_text("def greet(name):\n    pass\n", encoding="utf-8")
    (src_dir / "caller.py").write_text("from defs import greet\n\ngreet()\n", encoding="utf-8")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.ruff]
src = ["src"]
""",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        quiet=False,
        fail_fast=True,
        timeout=30,
        check_relative=False,
        venv=None,
        i_understand_this_will_execute_code=False,
    )
    exit_code = check_all(args)

    assert exit_code == 1

    stdout = capsys.readouterr().out
    assert "[4/7] Import cycle check" in stdout
    assert "[5/7] Local signature check" not in stdout
