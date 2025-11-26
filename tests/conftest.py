"""Pytest 配置和共用 fixtures."""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root():
    """返回專案根目錄的絕對路徑."""
    return Path(__file__).parent.parent.absolute()


@pytest.fixture(autouse=True)
def clear_caches():
    """每個測試前後保存目錄並清除所有 lru_cache."""
    # 測試執行前保存當前目錄
    original_cwd = os.getcwd()

    yield

    # 測試執行後恢復目錄
    try:
        if os.path.exists(original_cwd):
            os.chdir(original_cwd)
    except (FileNotFoundError, OSError):
        # 如果原目錄不存在，切換到專案根目錄
        os.chdir(Path(__file__).parent.parent)

    # 清除 cache
    from pyci_check.i18n import _find_pyproject_toml, get_locale
    from pyci_check.imports import find_pyproject_toml, get_ruff_config_from_pyproject, get_venv_from_pyproject

    _find_pyproject_toml.cache_clear()
    get_locale.cache_clear()
    find_pyproject_toml.cache_clear()
    get_ruff_config_from_pyproject.cache_clear()
    get_venv_from_pyproject.cache_clear()


@pytest.fixture
def temp_dir():
    """創建臨時目錄."""
    tmpdir = tempfile.mkdtemp()
    try:
        yield Path(tmpdir)
    finally:
        # Windows 上需要重試刪除,因為可能有檔案被鎖定
        if sys.platform == "win32":
            for _ in range(3):
                try:
                    shutil.rmtree(tmpdir, ignore_errors=False)
                    break
                except (PermissionError, OSError):
                    time.sleep(0.1)
            else:
                # 最後一次嘗試,忽略錯誤
                shutil.rmtree(tmpdir, ignore_errors=True)
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_python_file(temp_dir):
    """創建臨時 Python 檔案."""
    test_file = temp_dir / "test.py"
    test_file.write_text("print('hello')\n", encoding="utf-8")
    return test_file


@pytest.fixture
def temp_project(temp_dir):
    """創建臨時專案結構."""
    # 創建目錄結構
    (temp_dir / "src").mkdir()
    (temp_dir / "tests").mkdir()
    (temp_dir / ".venv").mkdir()
    (temp_dir / "build").mkdir()

    # 創建檔案
    (temp_dir / "src" / "__init__.py").write_text("", encoding="utf-8")
    (temp_dir / "src" / "main.py").write_text("import os\nimport sys\n", encoding="utf-8")
    (temp_dir / "tests" / "test_main.py").write_text("import pytest\n", encoding="utf-8")
    (temp_dir / ".venv" / "test.py").write_text("# venv file", encoding="utf-8")
    (temp_dir / "build" / "test.py").write_text("# build file", encoding="utf-8")

    # 創建 pyproject.toml
    pyproject = temp_dir / "pyproject.toml"
    pyproject.write_text("""
[tool.pyci-check]
language = "en"

[tool.ruff]
src = ["src", "tests"]
exclude = [".venv", "build"]
""", encoding="utf-8")

    return temp_dir


@pytest.fixture
def sample_python_code():
    """範例 Python 程式碼."""
    return """
import os
import sys
from pathlib import Path
from collections import defaultdict, Counter

def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
"""


@pytest.fixture
def sample_code_with_relative_imports():
    """包含相對導入的程式碼."""
    return """
from . import module1
from ..utils import helper
from ...core import base
"""


@pytest.fixture
def invalid_python_code():
    """無效的 Python 程式碼."""
    return """
def incomplete_function(
    print('unclosed string
    invalid syntax here
"""


@pytest.fixture
def pythonpath_env():
    """設定 PYTHONPATH 環境變數."""
    original_path = os.environ.get("PYTHONPATH", "")
    src_path = os.path.join(os.getcwd(), "src")

    env = os.environ.copy()
    env["PYTHONPATH"] = src_path

    yield env

    # 恢復原始環境
    if original_path:
        os.environ["PYTHONPATH"] = original_path
    elif "PYTHONPATH" in os.environ:
        del os.environ["PYTHONPATH"]
