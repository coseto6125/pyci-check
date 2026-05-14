"""整合測試：CLI 命令與輸出."""

import os
import subprocess
import sys
from pathlib import Path


def test_cli_dependency_command(tmp_path: Path):
    """測試 dependency 命令與輸出."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    (src_dir / "main.py").write_text("import requests\n", encoding="utf-8")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[project]
dependencies = ["httpx"]
[tool.ruff]
src = ["src"]
""", encoding="utf-8")

    # 執行 CLI 命令
    env = os.environ.copy()
    src_path = os.path.join(os.getcwd(), "src")
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{env['PYTHONPATH']}{os.pathsep}{src_path}"
    else:
        env["PYTHONPATH"] = src_path

    result = subprocess.run(
        [sys.executable, "-m", "pyci_check.cli", "dependency"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False
    )

    # 預期退出碼為 1 (發現問題)
    assert result.returncode == 1, f"Expected 1, got {result.returncode}. stderr: {result.stderr}"

    stdout = result.stdout or ""
    # 應該要報 requests 是幽靈依賴
    assert "requests" in stdout
    # 應該要報 httpx 是冗餘依賴
    assert "httpx" in stdout
def test_cli_cycles_command(tmp_path: Path):
    """測試 cycles 命令與輸出."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    (src_dir / "a.py").write_text("import b\n", encoding="utf-8")
    (src_dir / "b.py").write_text("import a\n", encoding="utf-8")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.ruff]
src = ["src"]
""", encoding="utf-8")

    env = os.environ.copy()
    src_path = os.path.join(os.getcwd(), "src")
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{env['PYTHONPATH']}{os.pathsep}{src_path}"
    else:
        env["PYTHONPATH"] = src_path

    result = subprocess.run(
        [sys.executable, "-m", "pyci_check.cli", "cycles"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False
    )

    assert result.returncode == 1, f"Expected 1, got {result.returncode}. stderr: {result.stderr}"
    stdout = result.stdout or ""

    assert "a.py -> src/b.py -> src/a.py" in stdout or "b.py -> src/a.py -> src/b.py" in stdout

