"""測試死代碼掃描與副作用偵測."""

from pyci_check.deadcode import scan_dead_code
from pyci_check.side_effects import detect_side_effects


def test_side_effects(tmp_path):
    safe_file = tmp_path / "safe.py"
    safe_file.write_text("""
import requests
def fetch():
    requests.get('http://example.com')
""", encoding="utf-8")

    danger_file = tmp_path / "danger.py"
    danger_file.write_text("""
import requests
# 頂層副作用
response = requests.get('http://example.com')
""", encoding="utf-8")

    warnings = detect_side_effects([str(safe_file), str(danger_file)])

    assert len(warnings) == 1
    assert "danger.py" in warnings[0]["file"]
    assert "requests.get" in warnings[0]["call"]


def test_deadcode_scan(tmp_path):
    a_py = tmp_path / "a.py"
    a_py.write_text("""
def used_func():
    pass

def unused_func():
    pass
""", encoding="utf-8")

    b_py = tmp_path / "b.py"
    b_py.write_text("""
from a import used_func

def main():
    used_func()
""", encoding="utf-8")

    # 執行死代碼掃描
    warnings = scan_dead_code([str(a_py), str(b_py)])

    # 預期 main 會在 whitelist 中被忽略
    # used_func 被使用了
    # 只有 unused_func 應該被報告
    dead_names = [w["name"] for w in warnings]
    assert "unused_func" in dead_names
    assert "used_func" not in dead_names
    assert "main" not in dead_names
