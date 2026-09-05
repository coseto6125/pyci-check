"""測試死代碼掃描與副作用偵測."""

from pyci_check.deadcode import scan_dead_code
from pyci_check.findings import Finding
from pyci_check.side_effects import detect_side_effects


def test_side_effects(tmp_path):
    safe_file = tmp_path / "safe.py"
    safe_file.write_text(
        """
import requests
def fetch():
    requests.get('http://example.com')
""",
        encoding="utf-8",
    )

    danger_file = tmp_path / "danger.py"
    danger_file.write_text(
        """
import requests
# 頂層副作用
response = requests.get('http://example.com')
""",
        encoding="utf-8",
    )

    warnings = detect_side_effects([str(safe_file), str(danger_file)])

    assert len(warnings) == 1
    assert isinstance(warnings[0], Finding)
    assert "danger.py" in warnings[0].file
    assert "requests.get" in warnings[0].message


def test_deadcode_scan(tmp_path):
    a_py = tmp_path / "a.py"
    a_py.write_text(
        """
def used_func():
    pass

def unused_func():
    pass
""",
        encoding="utf-8",
    )

    b_py = tmp_path / "b.py"
    b_py.write_text(
        """
from a import used_func

def main():
    used_func()
""",
        encoding="utf-8",
    )

    # 執行死代碼掃描
    warnings = scan_dead_code([str(a_py), str(b_py)])

    # 預期 main 會在 whitelist 中被忽略
    # used_func 被使用了
    # 只有 unused_func 應該被報告
    dead_msgs = [f.message for f in warnings]
    assert len(dead_msgs) == 1
    assert "'unused_func'" in dead_msgs[0]


def test_scan_dead_code_without_corpus_streams(monkeypatch, tmp_path):
    """Standalone 呼叫不得整批建 Corpus (記憶體退步防護網):fallback 必須逐檔串流."""
    from pyci_check import corpus as corpus_mod

    target = tmp_path / "mod.py"
    target.write_text("def unused_fn():\n    pass\n", encoding="utf-8")

    def _boom(_cls, _files):
        raise AssertionError("corpus=None 的 fallback 必須逐檔串流,不得呼叫 Corpus.load")

    monkeypatch.setattr(corpus_mod.Corpus, "load", classmethod(_boom))
    findings = scan_dead_code([str(target)])
    assert len(findings) == 1


def test_detect_side_effects_without_corpus_streams(monkeypatch, tmp_path):
    """同上,副作用掃描的 fallback 也必須串流."""
    from pyci_check import corpus as corpus_mod

    target = tmp_path / "danger.py"
    target.write_text("import requests\nresponse = requests.get('http://example.com')\n", encoding="utf-8")

    def _boom(_cls, _files):
        raise AssertionError("corpus=None 的 fallback 必須逐檔串流,不得呼叫 Corpus.load")

    monkeypatch.setattr(corpus_mod.Corpus, "load", classmethod(_boom))
    warnings = detect_side_effects([str(target)])
    assert len(warnings) == 1


def test_iter_trees_prefers_corpus_and_ignores_python_files(tmp_path):
    """Corpus 提供時以語料為準;python_files 只是 standalone 用途的參數."""
    from pyci_check.corpus import Corpus, iter_trees

    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("x = 1\n", encoding="utf-8")
    b.write_text("y = 2\n", encoding="utf-8")

    full = Corpus.load([str(a), str(b)])
    pairs = dict(iter_trees([str(a)], corpus=full))  # 只傳一個檔案也會掃到兩個
    assert set(pairs) == {str(a), str(b)}


def test_iter_trees_streams_valid_files_and_skips_broken(tmp_path):
    """Standalone 模式逐檔 yield 已解析的樹;讀不到或語法錯誤的靜默略過."""
    from pyci_check.corpus import iter_trees

    good = tmp_path / "good.py"
    bad = tmp_path / "bad.py"
    good.write_text("x = 1\n", encoding="utf-8")
    bad.write_text("def broken(:\n", encoding="utf-8")
    missing = str(tmp_path / "missing.py")

    pairs = dict(iter_trees([str(good), str(bad), missing]))
    assert list(pairs) == [str(good)]
    assert isinstance(pairs[str(good)], __import__("ast").Module)


def test_a_decorated_definition_is_not_reported_as_dead():
    """
    A route's caller is its framework, and that call is not in the source.

    The scan matched names, so every `@app.get(...)` handler, lifecycle hook and
    fixture read as an orphan: one real project returned sixteen entries, all of them
    live registered handlers. Sixteen is the count at which people stop reading the
    output, which costs more than the orphans it would have found.
    """
    import ast

    from pyci_check.deadcode import DefinitionVisitor

    module = """
@app.get("/")
async def index(request):
    return None

@app.before_server_start
async def open_db(app, loop):
    return None

def helper():
    return None
"""
    collector = DefinitionVisitor("web.py")
    collector.visit(ast.parse(module))

    assert "helper" in collector.definitions, "an undecorated function is still scanned"
    assert "index" not in collector.definitions
    assert "open_db" not in collector.definitions
