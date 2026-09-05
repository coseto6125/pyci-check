"""測試：本地簽章驗證."""

import argparse
from pathlib import Path

from pyci_check.cli import check_signature
from pyci_check.signature import _get_module_name


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


def test_fields_declared_on_an_annotated_base_are_constructor_arguments():
    """
    A class whose fields come from its base, not a decorator, still has them.

    msgspec.Struct, NamedTuple, TypedDict and pydantic.BaseModel all declare fields as
    class-level annotations and synthesise __init__ from them. Reading only the
    decorator list made every such class look like it took no arguments, so each
    Struct(field=...) became an unknown-keyword error: one real project reported 256,
    all from this, which buried the findings that were true.
    """
    import ast

    from pyci_check.signature import CallValidator, DefinitionCollector

    module = """
import msgspec

class Point(msgspec.Struct):
    x: int
    y: int
"""
    defs = DefinitionCollector("pkg.shapes")
    defs.visit(ast.parse(module))
    assert defs.signatures["Point"].pos_arg_names == {"x", "y"}

    signatures = {f"pkg.shapes.{name}": sig for name, sig in defs.signatures.items()}

    good = "from pkg.shapes import Point\ndef use():\n    return Point(x=1, y=2)\n"
    validator = CallValidator("use.py", "use", signatures)
    validator.visit(ast.parse(good))
    assert validator.errors == [], "a call naming the declared fields is valid"

    # And the check still bites: widening the constructor must not blind it.
    bad = "from pkg.shapes import Point\ndef use():\n    return Point(x=1, z=9)\n"
    validator = CallValidator("use.py", "use", signatures)
    validator.visit(ast.parse(bad))
    assert len(validator.errors) == 1
    assert "z" in validator.errors[0].message


def test_a_base_written_as_an_attribute_or_a_call_is_still_recognised():
    """`msgspec.Struct`, a bare `Struct`, and `Struct(frozen=True)` name the same base."""
    import ast

    from pyci_check.signature import DefinitionCollector

    for base in ("msgspec.Struct", "Struct", "Struct(frozen=True)", "NamedTuple", "TypedDict"):
        defs = DefinitionCollector("pkg.m")
        defs.visit(ast.parse(f"class C({base}):\n    a: int\n"))
        assert defs.signatures["C"].pos_arg_names == {"a"}, f"{base} was not read as a field base"
