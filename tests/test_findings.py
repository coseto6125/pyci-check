"""測試 Finding 契約與輸出渲染."""

from pyci_check.findings import Finding, has_errors, render_findings


def test_render_findings_relative_path_line_and_message(tmp_path):
    """輸出格式:縮排 + 相對路徑:行號 -> 訊息."""
    finding = Finding(str(tmp_path / "a.py"), 3, "'f' is defined but never used across the project")
    assert render_findings([finding], str(tmp_path)) == ["  - a.py:3 -> 'f' is defined but never used across the project"]


def test_has_errors_maps_severity_to_exit_decision():
    """Exit code 判定只看 severity="error";warning 與空清單都是 0."""
    assert has_errors([]) is False
    assert has_errors([Finding("a.py", 1, "m")]) is False  # 預設 warning
    assert has_errors([Finding("a.py", 1, "m", "warning")]) is False
    assert has_errors([Finding("a.py", 1, "m", "error")]) is True
    mixed = [Finding("a.py", 1, "w"), Finding("b.py", 2, "e", "error")]
    assert has_errors(mixed) is True


def test_finding_is_frozen():
    """Finding 凍結:掃描器產出後不可被 wrapper 改寫."""
    import dataclasses

    import pytest

    f = Finding("a.py", 1, "m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.severity = "error"
