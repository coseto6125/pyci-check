"""測試 import 檢查功能."""

import tempfile
from pathlib import Path

import pytest

from pyci_check.imports import (
    MODULE_NAME_PATTERN,
    check_module_importable,
    extract_imports_from_code,
    find_pyproject_toml,
    get_ruff_config_from_pyproject,
    read_file_with_encoding,
)


class TestImportChecker:
    """Import 檢查測試."""

    def test_module_name_validation_valid(self):
        """測試有效的模組名稱."""
        valid_names = [
            "os",
            "sys",
            "collections",
            "collections.abc",
            "my_module",
            "test123",
            "_private",
        ]

        for name in valid_names:
            assert MODULE_NAME_PATTERN.match(name), f"{name} should be valid"

    def test_module_name_validation_invalid(self):
        """測試無效的模組名稱."""
        invalid_names = [
            "os; import sys",  # 程式碼注入
            "../malicious",  # 路徑遍歷
            "123test",  # 數字開頭
            "my-module",  # 包含連字號
            "test module",  # 包含空格
            "__import__('os')",  # 函數呼叫
        ]

        for name in invalid_names:
            assert not MODULE_NAME_PATTERN.match(name), f"{name} should be invalid"

    def test_check_module_importable_builtin(self):
        """測試檢查內建模組."""
        module, error = check_module_importable("os", timeout=5)

        assert module == "os"
        assert error is None

    def test_check_module_importable_invalid_name(self):
        """測試無效模組名稱."""
        module, error = check_module_importable("os; rm -rf /", timeout=5)

        assert module == "os; rm -rf /"
        assert "Invalid module name" in error

    def test_extract_imports_from_code(self):
        """測試從程式碼提取 import."""
        code = """
import os
import sys
from pathlib import Path
from collections import defaultdict, Counter
"""

        imports, relative_imports = extract_imports_from_code(code, "test.py")

        assert len(imports) == 4
        assert len(relative_imports) == 0

        module_names = {imp["module"] for imp in imports}
        assert "os" in module_names
        assert "sys" in module_names
        assert "pathlib" in module_names
        assert "collections" in module_names

    def test_extract_relative_imports(self):
        """測試提取相對導入."""
        code = """
from . import module1
from ..utils import helper
"""

        imports, relative_imports = extract_imports_from_code(code, "test.py")

        assert len(imports) == 0
        assert len(relative_imports) == 2
        assert all(imp["type"] == "relative" for imp in relative_imports)

    def test_extract_imports_syntax_error(self):
        """測試語法錯誤的程式碼."""
        code = "import os\nprint('unclosed"

        imports, relative_imports = extract_imports_from_code(code, "test.py")

        assert imports == []
        assert relative_imports == []

    def test_read_file_with_encoding_utf8(self):
        """測試讀取 UTF-8 檔案."""
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".py", delete=False) as f:
            f.write("# -*- coding: utf-8 -*-\nprint('中文測試')\n")
            f.flush()
            temp_path = f.name

        content = read_file_with_encoding(temp_path)
        Path(temp_path).unlink()

        assert content is not None
        assert "中文測試" in content

    def test_read_file_nonexistent(self):
        """測試讀取不存在的檔案."""
        content = read_file_with_encoding("/nonexistent/file.py")

        assert content is None

    def test_find_pyproject_toml(self):
        """測試尋找 pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 創建 pyproject.toml
            pyproject_path = Path(tmpdir) / "pyproject.toml"
            pyproject_path.write_text("[tool.pyci-check]\nlanguage = 'en'\n")

            # 清除 cache
            find_pyproject_toml.cache_clear()

            result = find_pyproject_toml(tmpdir)

            assert result is not None
            assert Path(result).name == "pyproject.toml"

    def test_get_ruff_config_from_pyproject(self):
        """測試從 pyproject.toml 讀取 ruff 配置."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 創建 pyproject.toml
            pyproject_path = Path(tmpdir) / "pyproject.toml"
            pyproject_content = """
[tool.ruff]
src = ["src", "tests"]
exclude = [".venv", "build"]
extend-exclude = ["*.egg-info"]
"""
            pyproject_path.write_text(pyproject_content)

            # 清除 cache
            get_ruff_config_from_pyproject.cache_clear()

            config = get_ruff_config_from_pyproject(tmpdir)

            assert "src" in config
            assert "exclude_dirs" in config
            assert "exclude_files" in config
            assert config["src"] == ["src", "tests"]
            assert ".venv" in config["exclude_dirs"]
            assert "build" in config["exclude_dirs"]

    def test_get_ruff_config_no_pyproject(self):
        """測試沒有 pyproject.toml 的情況."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 清除 cache
            get_ruff_config_from_pyproject.cache_clear()

            config = get_ruff_config_from_pyproject(tmpdir)

            # 應該返回預設值
            assert config["src"] == []
            assert config["exclude_dirs"] == []
            assert config["exclude_files"] == []
