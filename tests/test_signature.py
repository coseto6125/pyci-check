"""測試：本地簽章驗證."""

import argparse
from pathlib import Path

from pyci_check.cli import check_signature
from pyci_check.signature import _get_module_name, check_signatures


def _check_source(tmp_path: Path, source: str) -> list[dict]:
    module = tmp_path / "case.py"
    module.write_text(source, encoding="utf-8")
    return check_signatures([str(module)], str(tmp_path), [])


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


def test_check_signatures_msgspec_struct_accepts_fields_and_rejects_unknown_kwarg(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
import msgspec

class Outcome(msgspec.Struct, frozen=True, kw_only=True):
    status: str
    error: str | None = None

Outcome(status="ok")
Outcome(status="ok", bogus=True)
""",
    )

    assert len(errors) == 1
    assert errors[0]["line"] == 9
    assert "Unexpected keyword arguments: bogus" in errors[0]["reason"]


def test_check_signatures_msgspec_subclass_merges_inherited_and_own_fields(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
import msgspec

class Base(msgspec.Struct, kw_only=True):
    a: str

class Child(Base):
    b: str

Child(a="a", b="b")
Child(a="a", b="b", bogus=True)
""",
    )

    assert len(errors) == 1
    assert "Unexpected keyword arguments: bogus" in errors[0]["reason"]


def test_check_signatures_msgspec_kwonly_subclass_default_overrides_required_field(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
import msgspec

class Base(msgspec.Struct, kw_only=True):
    value: str

class Child(Base):
    value: str = "default"

Child()
Child(bogus=True)
""",
    )

    assert len(errors) == 1
    assert "Unexpected keyword arguments: bogus" in errors[0]["reason"]


def test_check_signatures_msgspec_positional_subclass_default_overrides_required_field(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
import msgspec

class Base(msgspec.Struct):
    value: str

class Child(Base):
    value: str = "default"

Child()
Child("first", "second")
""",
    )

    assert len(errors) == 1
    assert "Too many positional arguments: expected at most 1, got 2" in errors[0]["reason"]


def test_check_signatures_msgspec_classvar_is_not_a_constructor_field(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
from typing import ClassVar

import msgspec

class Model(msgspec.Struct, kw_only=True):
    kind: ClassVar[str]

Model()
Model(kind="override")
""",
    )

    assert len(errors) == 1
    assert "Unexpected keyword arguments: kind" in errors[0]["reason"]


def test_check_signatures_exception_subclass_inherits_constructor(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        '''
class QuotaViolationError(ValueError):
    """Raised when a quota is exceeded."""

QuotaViolationError("quota exceeded")
''',
    )

    assert errors == []


def test_check_signatures_plain_subclass_inherits_local_constructor(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
class Base:
    def __init__(self, first, second):
        self.values = (first, second)

class Child(Base):
    pass

Child(1, 2)
Child(1, wrong=2)
""",
    )

    assert len(errors) == 1
    assert "Unexpected keyword arguments: wrong" in errors[0]["reason"]


def test_check_signatures_cross_file_import_matches_project_relative_alias(tmp_path: Path):
    package = tmp_path / "enoract" / "chat" / "retrieval"
    package.mkdir(parents=True)
    manager = package / "manager.py"
    manager.write_text(
        """
import msgspec

class ReplicaOutcome(msgspec.Struct, kw_only=True):
    status: str
""",
        encoding="utf-8",
    )
    consumer = tmp_path / "consumer.py"
    consumer.write_text(
        """
from enoract.chat.retrieval.manager import ReplicaOutcome

ReplicaOutcome(status="ok")
ReplicaOutcome(bogus=1)
""",
        encoding="utf-8",
    )

    errors = check_signatures([str(manager), str(consumer)], str(tmp_path), ["enoract"])

    assert len(errors) == 1
    assert "Unexpected keyword arguments: bogus" in errors[0]["reason"]


def test_check_signatures_qualified_dataclass_decorator(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
import dataclasses

@dataclasses.dataclass
class Record:
    value: str

Record(value="ok")
Record(wrong="bad")
""",
    )

    assert len(errors) == 1
    assert "Unexpected keyword arguments: wrong" in errors[0]["reason"]


def test_check_signatures_named_tuple_uses_annotated_fields(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
from typing import NamedTuple

class Pair(NamedTuple):
    left: str
    right: str

Pair("a", "b")
Pair(left="a", wrong="b")
""",
    )

    assert len(errors) == 1
    assert "Unexpected keyword arguments: wrong" in errors[0]["reason"]


def test_check_signatures_staticmethod_keeps_first_parameter(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
class Parser:
    @staticmethod
    def parse(value: str) -> str:
        return value

Parser.parse("value")
""",
    )

    assert errors == []


def test_check_signatures_skips_decorator_modified_callable(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
def inject(func):
    def wrapper():
        return func("injected")
    return wrapper

@inject
def task(dependency):
    return dependency

task()
""",
    )

    assert errors == []


def test_check_signatures_cached_function_preserves_signature(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
import functools

@functools.cache
def combine(left, right):
    return left + right

combine(1, 2, 3, 4)
""",
    )

    assert len(errors) == 1
    assert "Too many positional arguments: expected at most 2, got 4" in errors[0]["reason"]


def test_check_signatures_skips_decorator_modified_class(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
def with_constructor(cls):
    return lambda value: (cls, value)

@with_constructor
class Generated:
    pass

Generated("value")
""",
    )

    assert errors == []


def test_check_signatures_keeps_local_class_scopes_separate(tmp_path: Path):
    errors = _check_source(
        tmp_path,
        """
def with_payload():
    class Response:
        def __init__(self, payload):
            self.payload = payload
    return Response("ok")

def without_payload():
    class Response:
        pass
    return Response()
""",
    )

    assert errors == []
