"""測試循環引用偵測."""

import os
from pyci_check.cycles import find_import_cycles

def test_find_import_cycles_absolute(tmp_path):
    """測試絕對匯入造成的循環引用 (a -> b -> a)"""
    a_py = tmp_path / "a.py"
    b_py = tmp_path / "b.py"
    
    a_py.write_text("import b", encoding="utf-8")
    b_py.write_text("import a", encoding="utf-8")
    
    all_imports = [
        {"file": str(a_py), "module": "b", "line": 1, "statement": "import b", "type": "absolute", "optional": False},
        {"file": str(b_py), "module": "a", "line": 1, "statement": "import a", "type": "absolute", "optional": False},
    ]
    
    cycles = find_import_cycles(all_imports, [], str(tmp_path), [])
    
    assert len(cycles) > 0
    # 檢查是否有環包含 a 和 b
    found_ab = False
    for cycle in cycles:
        names = [os.path.basename(f) for f in cycle]
        if "a.py" in names and "b.py" in names:
            found_ab = True
            break
    assert found_ab

def test_find_import_cycles_relative(tmp_path):
    """測試相對匯入造成的循環引用"""
    # 目錄結構:
    # pkg/
    #   __init__.py
    #   x.py -> from . import y
    #   y.py -> from . import x
    
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    
    x_py = pkg_dir / "x.py"
    y_py = pkg_dir / "y.py"
    
    x_py.write_text("from . import y", encoding="utf-8")
    y_py.write_text("from . import x", encoding="utf-8")
    
    all_relative_imports = [
        {"file": str(x_py), "module": "y", "level": 1, "line": 1, "statement": "from . import y", "type": "relative", "optional": False},
        {"file": str(y_py), "module": "x", "level": 1, "line": 1, "statement": "from . import x", "type": "relative", "optional": False},
    ]
    
    cycles = find_import_cycles([], all_relative_imports, str(tmp_path), ["pkg"])
    
    assert len(cycles) > 0
    found_xy = False
    for cycle in cycles:
        names = [os.path.basename(f) for f in cycle]
        if "x.py" in names and "y.py" in names:
            found_xy = True
            break
    assert found_xy

def test_no_cycles(tmp_path):
    """測試沒有循環引用的情況"""
    a_py = tmp_path / "a.py"
    b_py = tmp_path / "b.py"
    
    a_py.write_text("import b", encoding="utf-8")
    b_py.write_text("X = 1", encoding="utf-8")
    
    all_imports = [
        {"file": str(a_py), "module": "b", "line": 1, "statement": "import b", "type": "absolute", "optional": False},
    ]
    
    cycles = find_import_cycles(all_imports, [], str(tmp_path), [])
    assert len(cycles) == 0

def test_empty_project(tmp_path):
    """測試空專案"""
    cycles = find_import_cycles([], [], str(tmp_path), [])
    assert len(cycles) == 0

def test_self_reference_ignored(tmp_path):
    """測試自我引用不應被視為循環 (Python 少見，但要防呆)"""
    a_py = tmp_path / "a.py"
    a_py.write_text("import a", encoding="utf-8")
    
    all_imports = [
        {"file": str(a_py), "module": "a", "line": 1, "statement": "import a", "type": "absolute", "optional": False},
    ]
    
    cycles = find_import_cycles(all_imports, [], str(tmp_path), [])
    assert len(cycles) == 0
