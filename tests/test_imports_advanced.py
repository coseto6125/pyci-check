"""Import 檢查進階測試."""

from pyci_check.i18n import t
from pyci_check.imports import (
    check_missing_modules,
    check_module_importable_static,
    extract_from_all_files,
    find_python_executable,
    get_venv_from_pyproject,
    process_single_file,
)


class TestImportAdvanced:
    """Import 檢查進階測試."""

    def test_process_single_file_valid(self, temp_dir):
        """測試處理有效的 Python 檔案."""
        test_file = temp_dir / "test.py"
        test_file.write_text("import os\nimport sys\nfrom pathlib import Path\n", encoding="utf-8")

        imports, relative_imports = process_single_file(str(test_file))

        assert len(imports) == 3
        assert len(relative_imports) == 0

    def test_process_single_file_with_relative_imports(self, temp_dir):
        """測試處理包含相對導入的檔案."""
        test_file = temp_dir / "test.py"
        test_file.write_text("from . import module1\nfrom ..utils import helper\n", encoding="utf-8")

        imports, relative_imports = process_single_file(str(test_file))

        assert len(imports) == 0
        assert len(relative_imports) == 2

    def test_process_single_file_encoding_error(self, temp_dir):
        """測試處理編碼錯誤的檔案."""
        test_file = temp_dir / "bad_encoding.py"
        # 寫入無效的 UTF-8 序列在字串中間
        test_file.write_bytes(b"import os\n\xff\xfe\nimport sys")

        imports, relative_imports = process_single_file(str(test_file))

        # read_file_with_encoding 使用 latin-1 作為 fallback，所以會成功讀取
        # 這個測試檢查即使有編碼問題，也能處理檔案
        assert isinstance(imports, list)
        assert isinstance(relative_imports, list)

    def test_extract_from_all_files(self, temp_project):
        """測試從所有檔案提取 import."""
        imports, _relative_imports = extract_from_all_files(str(temp_project))

        # temp_project 包含 src/main.py 和 tests/test_main.py
        assert len(imports) > 0
        module_names = {imp["module"] for imp in imports}
        assert "os" in module_names or "pytest" in module_names

    def test_extract_from_all_files_with_ignore(self, temp_dir):
        """測試忽略特定目錄和檔案."""
        # 創建檔案結構
        (temp_dir / "src").mkdir()
        (temp_dir / ".venv").mkdir()
        (temp_dir / "src" / "main.py").write_text("import os", encoding="utf-8")
        (temp_dir / ".venv" / "test.py").write_text("import sys", encoding="utf-8")

        imports, _ = extract_from_all_files(
            str(temp_dir),
            ignore_dirs={".venv"},
            ignore_files=set(),
        )

        # 應該只找到 src/main.py 的 import
        files = {imp["file"] for imp in imports}
        assert not any(".venv" in f for f in files)

    def test_check_module_importable_static_builtin(self):
        """測試靜態檢查內建模組."""
        module, error = check_module_importable_static("os")

        assert module == "os"
        assert error is None

    def test_check_module_importable_static_project_module(self, temp_project):
        """測試靜態檢查專案模組."""
        # 創建一個專案模組
        (temp_project / "src" / "mymodule.py").write_text("print('test')", encoding="utf-8")

        module, error = check_module_importable_static(
            "mymodule",
            project_dir=str(temp_project),
            src_dirs=["src"],
        )

        assert module == "mymodule"
        assert error is None

    def test_check_module_importable_static_missing(self):
        """測試靜態檢查不存在的模組."""
        module, error = check_module_importable_static("nonexistent_module_xyz")

        assert module == "nonexistent_module_xyz"
        assert error is not None
        # 使用多語系訊息檢查
        expected_error = t("imports.error.module_not_found", "nonexistent_module_xyz")
        assert error == expected_error

    def test_check_missing_modules_all_valid(self, temp_dir):
        """測試檢查所有有效的模組."""
        imports = [
            {"module": "os", "line": 1, "file": "test.py"},
            {"module": "sys", "line": 2, "file": "test.py"},
        ]

        missing = check_missing_modules(
            imports,
            project_dir=str(temp_dir),
            use_static=True,
        )

        assert len(missing) == 0

    def test_check_missing_modules_with_missing(self, temp_dir):
        """測試檢查包含缺少模組的情況."""
        imports = [
            {"module": "os", "line": 1, "file": "test.py"},
            {"module": "nonexistent_xyz", "line": 2, "file": "test.py"},
        ]

        missing = check_missing_modules(
            imports,
            project_dir=str(temp_dir),
            use_static=True,
        )

        assert "nonexistent_xyz" in missing
        assert "os" not in missing

    def test_find_python_executable_no_venv(self):
        """測試找不到虛擬環境時使用當前 Python."""
        import sys

        python = find_python_executable(venv_path=None)

        assert python == sys.executable

    def test_find_python_executable_invalid_venv(self, temp_dir):
        """測試無效的虛擬環境路徑."""
        import sys

        python = find_python_executable(venv_path=str(temp_dir / "nonexistent"))

        # 應該 fallback 到當前 Python
        assert python == sys.executable

    def test_get_venv_from_pyproject(self, temp_dir):
        """測試從 pyproject.toml 讀取虛擬環境設定."""
        pyproject = temp_dir / "pyproject.toml"
        pyproject.write_text("""
[tool.pyci-check]
venv = ".venv"
""")

        # 清除 cache
        get_venv_from_pyproject.cache_clear()

        venv = get_venv_from_pyproject(str(temp_dir))

        assert venv == ".venv"

    def test_get_venv_from_pyproject_no_setting(self, temp_dir):
        """測試沒有 venv 設定的情況."""
        pyproject = temp_dir / "pyproject.toml"
        pyproject.write_text("""
[tool.pyci-check]
language = "en"
""")

        # 清除 cache
        get_venv_from_pyproject.cache_clear()

        venv = get_venv_from_pyproject(str(temp_dir))

        assert venv is None

    def test_concurrent_import_checking(self, temp_dir):
        """測試並行檢查多個 import."""
        imports = [
            {"module": "os", "line": 1, "file": "test.py"},
            {"module": "sys", "line": 2, "file": "test.py"},
            {"module": "pathlib", "line": 3, "file": "test.py"},
            {"module": "collections", "line": 4, "file": "test.py"},
        ]

        missing = check_missing_modules(
            imports,
            project_dir=str(temp_dir),
            max_workers=2,
            use_static=True,
        )

        assert len(missing) == 0

    def test_extract_from_empty_directory(self, temp_dir):
        """測試從空目錄提取 import."""
        imports, relative_imports = extract_from_all_files(str(temp_dir))

        assert imports == []
        assert relative_imports == []

    def test_process_file_with_future_import(self, temp_dir):
        """測試處理包含 __future__ import 的檔案."""
        test_file = temp_dir / "test.py"
        test_file.write_text("from __future__ import annotations\nimport os\n", encoding="utf-8")

        imports, _ = process_single_file(str(test_file))

        # __future__ 和 os 都應該被提取
        module_names = {imp["module"] for imp in imports}
        assert "__future__" in module_names
        assert "os" in module_names

    def test_extract_from_files_with_custom_workers(self, temp_project):
        """測試使用自訂 worker 數量."""
        imports, _ = extract_from_all_files(
            str(temp_project),
            max_workers=1,  # 強制使用單執行緒
        )

        assert len(imports) > 0
