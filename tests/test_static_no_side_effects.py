"""
驗證 check_module_importable_static 不會執行使用者 __init__.py 副作用.

回歸防護: 此檔的存在意義是抓住「靜態檢查暗中執行使用者程式碼」的 regression
(典型誘因: 使用 importlib.util.find_spec 對 dotted name 觸發 parent import)。
"""

import sys
from pathlib import Path

import pytest

from pyci_check.imports import check_module_importable_static


def _make_pkg_with_side_effect(root: Path, pkg_name: str, side_effect_marker: Path) -> None:
    """建立一個 __init__.py 帶副作用的 package."""
    pkg_dir = root / pkg_name
    pkg_dir.mkdir(parents=True)
    init_py = pkg_dir / "__init__.py"
    # __init__.py 在執行時會 touch marker 檔; 靜態檢查若呼叫到 import 機制就會留痕跡
    init_py.write_text(
        f"from pathlib import Path\nPath(r'{side_effect_marker}').write_text('PWNED')\n",
        encoding="utf-8",
    )


def test_top_level_package_check_does_not_execute_init(tmp_path: Path) -> None:
    """check_module_importable_static('foo') 不該執行 foo/__init__.py."""
    marker = tmp_path / "EXECUTED.flag"
    _make_pkg_with_side_effect(tmp_path, "sideeffect_pkg", marker)

    _module, error = check_module_importable_static(
        "sideeffect_pkg",
        project_dir=str(tmp_path),
        src_dirs=None,
    )

    assert error is None, f"應找到 sideeffect_pkg，實際: {error}"
    assert not marker.exists(), f"靜態檢查不該執行 __init__.py 但 marker 出現: {marker}"


def test_dotted_submodule_check_does_not_execute_parent_init(tmp_path: Path) -> None:
    """
    check_module_importable_static('foo.bar') 不該執行 foo/__init__.py。

    這是 find_spec 的最大陷阱: 對 dotted name，find_spec("foo.bar") 必定 import
    foo 來取得 foo.__path__。新的 4 層 probe 完全避開此行為。
    """
    parent_marker = tmp_path / "PARENT_EXECUTED.flag"
    pkg_dir = tmp_path / "parent_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        f"from pathlib import Path\nPath(r'{parent_marker}').write_text('PWNED')\n",
        encoding="utf-8",
    )
    (pkg_dir / "child.py").write_text("X = 1\n", encoding="utf-8")

    _module, error = check_module_importable_static(
        "parent_pkg.child",
        project_dir=str(tmp_path),
    )

    assert error is None, f"應找到 parent_pkg.child，實際: {error}"
    assert not parent_marker.exists(), f"父 package __init__.py 不該被觸發: {parent_marker}"


def test_namespace_package_without_init_is_recognized(tmp_path: Path) -> None:
    """PEP 420 namespace package (沒 __init__.py) 也要被視為可找到."""
    ns_dir = tmp_path / "myns" / "submod"
    ns_dir.mkdir(parents=True)
    (ns_dir / "leaf.py").write_text("X = 1\n", encoding="utf-8")
    # 注意: 沒有 __init__.py

    _module, error = check_module_importable_static(
        "myns.submod.leaf",
        project_dir=str(tmp_path),
    )
    assert error is None, f"namespace package 路徑應可找到，實際: {error}"


def test_missing_module_reports_error(tmp_path: Path) -> None:
    """確認真的找不到時會回報錯誤，不是濫過."""
    _module, error = check_module_importable_static(
        "definitely_not_a_real_module_xyz_123",
        project_dir=str(tmp_path),
    )
    assert error is not None, "找不到的模組應回報 module not found"


def test_stdlib_check_is_constant_time_and_silent(tmp_path: Path) -> None:
    """Stdlib lookup 走 sys.stdlib_module_names，不該有任何 I/O 副作用."""
    # 任意 stdlib 模組
    for stdlib_mod in ("os", "json", "ast", "pathlib", "collections.abc"):
        _module, error = check_module_importable_static(stdlib_mod, project_dir=str(tmp_path))
        assert error is None, f"stdlib 模組 {stdlib_mod} 應通過，實際: {error}"


def test_installed_package_top_level_recognized(tmp_path: Path) -> None:
    """已安裝套件 (例如 pytest 自己) 應被 metadata layer 抓到."""
    # pytest 一定裝了 (跑 test 必定有)
    _module, error = check_module_importable_static("pytest", project_dir=str(tmp_path))
    assert error is None, f"pytest 應被識別為已安裝，實際: {error}"


def test_installed_package_unknown_submodule_reports_missing_without_executing_parent(tmp_path: Path) -> None:
    """
    檢查已裝套件的子模組路徑時，不能只因 top-level package 存在就通過.

    同時不能 import pytest parent package，避免 plugin discovery 等副作用。
    """
    # 監看 sys.modules: 檢查前後不能多出 'pytest' (若已存在則不能變化)
    before = "pytest" in sys.modules
    _module, error = check_module_importable_static("pytest.does_not_exist_subname", project_dir=str(tmp_path))
    after = "pytest" in sys.modules
    assert error is not None, "已安裝套件的不存在子模組應回報 missing"
    if not before:
        assert not after, "靜態檢查不該真的 import pytest"


def test_c_extension_suffix_recognized(tmp_path: Path, monkeypatch) -> None:
    """sys.path probe 應認得 C extension 副檔名 (.so / .pyd / .abi3.so)."""
    import importlib.machinery as im

    from pyci_check.imports import _probe_sys_path

    fake_lib = tmp_path / "fake_lib"
    fake_lib.mkdir()
    # 用當前平台的 C extension 後綴創一個假檔
    suffix = im.EXTENSION_SUFFIXES[0] if im.EXTENSION_SUFFIXES else ".so"
    (fake_lib / f"fake_cext{suffix}").touch()

    # 暫時把 fake_lib 注入 sys.path
    monkeypatch.syspath_prepend(str(fake_lib))
    # 強制清掉 lru_cache 確保新加的路徑被看到 (sys.path 不在簽名內,但 probe 直接讀 sys.path)
    assert _probe_sys_path("fake_cext"), "C extension 應被 sys.path probe 識別"
    assert not _probe_sys_path("nonexistent_cext_xxx_yyy"), "不存在的不該誤報"


def test_type_checking_guard_skipped() -> None:
    """If TYPE_CHECKING: 內的 import 不該進入檢查清單."""
    from pyci_check.imports import extract_imports_from_code

    code = """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    import some_type_only_dep
import os  # 真實 runtime import
"""
    imports, _ = extract_imports_from_code(code, "fake.py")
    modules = {info["module"] for info in imports}
    assert "os" in modules
    assert "sqlalchemy.orm" not in modules, "TYPE_CHECKING 守護下 import 不該被收集"
    assert "some_type_only_dep" not in modules


def test_type_checking_guard_qualified_attribute() -> None:
    """If typing.TYPE_CHECKING: 的限定形式也要識別."""
    from pyci_check.imports import extract_imports_from_code

    code = """
import typing
if typing.TYPE_CHECKING:
    from very_optional_dep import Foo
"""
    imports, _ = extract_imports_from_code(code, "fake.py")
    modules = {info["module"] for info in imports}
    assert "very_optional_dep" not in modules


def test_optional_import_via_try_except() -> None:
    """try/except ImportError: 包住的 import 應被標 optional."""
    from pyci_check.imports import extract_imports_from_code

    code = """
try:
    import zstandard
    from optional_pkg.helpers import speedup
except ImportError:
    zstandard = None
    speedup = None
import os  # 必需
"""
    imports, _ = extract_imports_from_code(code, "fake.py")
    by_module = {info["module"]: info for info in imports}

    assert by_module["zstandard"]["optional"] is True
    assert by_module["optional_pkg.helpers"]["optional"] is True
    assert by_module["os"]["optional"] is False


def test_optional_via_module_not_found_error() -> None:
    """Except ModuleNotFoundError 也要識別."""
    from pyci_check.imports import extract_imports_from_code

    code = """
try:
    import optional_dep
except ModuleNotFoundError:
    pass
"""
    imports, _ = extract_imports_from_code(code, "fake.py")
    assert imports[0]["optional"] is True


def test_optional_via_tuple_exception() -> None:
    """Except (ImportError, OSError) 元組形式要識別."""
    from pyci_check.imports import extract_imports_from_code

    code = """
try:
    import optional_dep
except (ImportError, OSError):
    pass
"""
    imports, _ = extract_imports_from_code(code, "fake.py")
    assert imports[0]["optional"] is True


def test_optional_module_missing_does_not_report(tmp_path: Path) -> None:
    """check_missing_modules 對全 optional 模組的 missing 不該回報."""
    from pyci_check.imports import check_missing_modules

    # 模擬: 兩個 import_info 全部標 optional
    imports = [
        {
            "module": "totally_not_installed_xyz",
            "line": 1,
            "statement": "import totally_not_installed_xyz",
            "file": str(tmp_path / "f.py"),
            "type": "absolute",
            "optional": True,
        },
    ]
    missing = check_missing_modules(imports, project_dir=str(tmp_path))
    assert missing == {}, f"全 optional 不該回報 missing，實際: {missing}"


def test_required_module_still_reports_when_missing(tmp_path: Path) -> None:
    """混合 optional / required: required 那條仍要回報."""
    from pyci_check.imports import check_missing_modules

    imports = [
        {
            "module": "totally_not_installed_xyz_abc",
            "line": 1,
            "statement": "import ...",
            "file": str(tmp_path / "f.py"),
            "type": "absolute",
            "optional": True,
        },
        {
            "module": "totally_not_installed_xyz_abc",
            "line": 5,
            "statement": "from ... import x",
            "file": str(tmp_path / "f.py"),
            "type": "absolute",
            "optional": False,
        },
    ]
    missing = check_missing_modules(imports, project_dir=str(tmp_path))
    assert "totally_not_installed_xyz_abc" in missing, "required 用法存在時仍要回報"
    # 但只回報 required 那條,optional 的不在 list
    reported_lines = {info["line"] for info in missing["totally_not_installed_xyz_abc"]}
    assert 5 in reported_lines
    assert 1 not in reported_lines, "optional 那條不該入回報"


def test_execute_mode_isolates_each_import_from_sys_modules_pollution(tmp_path: Path) -> None:
    """Execute 模式中，前一個 import 不可污染後一個模組的檢查結果."""
    from pyci_check.imports import check_missing_modules

    (tmp_path / "evil.py").write_text(
        "import sys, types\nsys.modules['missing_dep_xyz'] = types.ModuleType('missing_dep_xyz')\n",
        encoding="utf-8",
    )
    imports = [
        {
            "module": "evil",
            "line": 1,
            "statement": "import evil",
            "file": str(tmp_path / "f.py"),
            "type": "absolute",
            "optional": False,
        },
        {
            "module": "missing_dep_xyz",
            "line": 2,
            "statement": "import missing_dep_xyz",
            "file": str(tmp_path / "f.py"),
            "type": "absolute",
            "optional": False,
        },
    ]

    missing = check_missing_modules(imports, project_dir=str(tmp_path), use_static=False, timeout=5)

    assert "evil" not in missing
    assert "missing_dep_xyz" in missing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
