"""測試：本地簽章驗證."""

import pytest
import os
import argparse
from pathlib import Path
from pyci_check.cli import check_signature
from pyci_check.signature import check_signatures, _get_module_name


def test_get_module_name():
    # 測試路徑轉換為模組名
    assert _get_module_name("/a/b/src/foo/bar.py", "/a/b", ["src"]) == "foo.bar"
    assert _get_module_name("/a/b/src/foo/__init__.py", "/a/b", ["src"]) == "foo"
    # 不在 src 裡
    assert _get_module_name("/a/b/scripts/deploy.py", "/a/b", ["src"]) == "scripts.deploy"


def test_signature_check(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # 定義檔案
    utils_py = src_dir / "utils.py"
    utils_py.write_text(
        """
def send_mail(to, subject, cc=None, *args, reply_to="no-reply", **kwargs):
    pass

class Mailer:
    def __init__(self, host, port=25):
        pass
""",
        encoding="utf-8",
    )

    # 呼叫檔案 (正確)
    main_py = src_dir / "main.py"
    main_py.write_text(
        """
from utils import send_mail, Mailer
import utils

send_mail("a@a.com", "Hello")
send_mail("a@a.com", "Hello", "cc", reply_to="admin")
send_mail("a@a.com", "Hello", extra="data") # allowed by **kwargs

Mailer("localhost")
Mailer("localhost", port=587)
""",
        encoding="utf-8",
    )

    # 呼叫檔案 (錯誤)
    bad_py = src_dir / "bad.py"
    bad_py.write_text(
        """
from utils import send_mail, Mailer

send_mail("a@a.com") # missing subject
send_mail("a@a.com", "b", "c", bad_kw="d") # if no **kwargs this would fail, but we have **kwargs, so this is valid. Wait, let's redefine a strict one.

def strict_func(a, b, *, c):
    pass

strict_func(1, 2) # missing c
strict_func(1, 2, c=3, d=4) # unexpected d
strict_func(1, 2, 3, c=4) # too many pos

Mailer() # missing host
""",
        encoding="utf-8",
    )

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.ruff]
src = ["src"]
""",
        encoding="utf-8",
    )

    # 執行檢查
    args = argparse.Namespace(quiet=False)
    exit_code = check_signature(args)

    assert exit_code == 1

    captured = capsys.readouterr()
    stdout = captured.out

    # bad.py 應該要有四個錯誤
    assert "Missing required positional arguments" in stdout  # send_mail missing subject
    assert "Missing required keyword-only arguments: c" in stdout  # strict_func missing c
    assert "Unexpected keyword arguments: d" in stdout  # strict_func unexpected d
    assert "Too many positional arguments" in stdout  # strict_func too many pos
    assert "Missing required positional arguments" in stdout  # Mailer missing host
