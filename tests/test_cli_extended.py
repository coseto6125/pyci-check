"""整合測試：CLI 命令與輸出."""

import os
import argparse
from pathlib import Path
from pyci_check.cli import check_dependency, check_cycles


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
