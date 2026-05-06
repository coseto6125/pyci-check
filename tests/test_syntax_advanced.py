"""語法檢查進階測試."""

from pathlib import Path

from pyci_check.syntax import check_file_syntax, check_files_parallel, find_python_files


class TestSyntaxAdvanced:
    """語法檢查進階測試."""

    def test_check_file_with_unicode(self, temp_dir):
        """測試包含 Unicode 字元的檔案."""
        test_file = temp_dir / "unicode.py"
        test_file.write_text("# -*- coding: utf-8 -*-\nprint('你好世界 🌍')\n", encoding="utf-8")

        is_valid, error = check_file_syntax(str(test_file))

        assert is_valid is True
        assert error == ""

    def test_check_file_with_bom(self, temp_dir):
        """測試包含 BOM 的檔案."""
        test_file = temp_dir / "bom.py"
        # UTF-8 BOM + 有效的 Python 程式碼
        test_file.write_bytes(b"\xef\xbb\xbf# -*- coding: utf-8 -*-\nprint('test')\n")

        is_valid, error = check_file_syntax(str(test_file))

        # Python 的 ast.parse 可以處理 UTF-8 BOM
        assert is_valid is True
        assert error == ""

    def test_check_file_encoding_error(self, temp_dir):
        """測試編碼錯誤的檔案."""
        test_file = temp_dir / "bad_encoding.py"
        # 寫入無效的 UTF-8 序列
        test_file.write_bytes(b"print('test')\n\xff\xfe")

        is_valid, error = check_file_syntax(str(test_file))

        assert is_valid is False
        assert "Encoding Error" in error or "Error" in error

    def test_check_file_nonexistent(self):
        """測試不存在的檔案."""
        is_valid, error = check_file_syntax("/nonexistent/file.py")

        assert is_valid is False
        assert "Error" in error

    def test_find_python_files_with_subdirs(self, temp_project):
        """測試查找包含子目錄的 Python 檔案."""
        # 創建更多子目錄和檔案
        (temp_project / "src" / "subdir").mkdir()
        (temp_project / "src" / "subdir" / "module.py").write_text("import os", encoding="utf-8")

        files = find_python_files(str(temp_project))

        # 應該找到 src 和 tests 中的檔案，排除 .venv 和 build
        py_files = [Path(f).name for f in files]
        assert "main.py" in py_files
        assert "module.py" in py_files
        assert "test_main.py" in py_files

        # 確認沒有 venv 和 build 中的檔案
        assert not any(".venv" in f for f in files)
        assert not any("build" in f for f in files)

    def test_find_python_files_custom_exclude(self, temp_dir):
        """測試自定義排除目錄."""
        # 創建檔案結構
        (temp_dir / "src").mkdir()
        (temp_dir / "custom_exclude").mkdir()
        (temp_dir / "src" / "test.py").write_text("import os", encoding="utf-8")
        (temp_dir / "custom_exclude" / "test.py").write_text("import sys", encoding="utf-8")

        files = find_python_files(str(temp_dir), exclude_dirs=["custom_exclude"])

        # 應該只找到 src 中的檔案
        assert len([f for f in files if "src" in f]) > 0
        assert not any("custom_exclude" in f for f in files)

    def test_check_files_parallel_mixed_results(self, temp_dir):
        """測試並行檢查混合結果（有效和無效檔案）."""
        # 創建多個檔案
        valid1 = temp_dir / "valid1.py"
        valid1.write_text("import os\nprint('test1')", encoding="utf-8")

        valid2 = temp_dir / "valid2.py"
        valid2.write_text("def func():\n    return True", encoding="utf-8")

        invalid1 = temp_dir / "invalid1.py"
        invalid1.write_text("print('unclosed", encoding="utf-8")

        invalid2 = temp_dir / "invalid2.py"
        invalid2.write_text("def incomplete(", encoding="utf-8")

        files = [str(valid1), str(valid2), str(invalid1), str(invalid2)]
        success_count, error_count, errors = check_files_parallel(files)

        assert success_count == 2
        assert error_count == 2
        assert len(errors) == 2

    def test_check_files_parallel_all_valid(self, temp_dir):
        """測試並行檢查全部有效的檔案."""
        files = []
        for i in range(10):
            f = temp_dir / f"file{i}.py"
            f.write_text(f"print('file {i}')", encoding="utf-8")
            files.append(str(f))

        success_count, error_count, errors = check_files_parallel(files)

        assert success_count == 10
        assert error_count == 0
        assert len(errors) == 0

    def test_check_files_parallel_all_invalid(self, temp_dir):
        """測試並行檢查全部無效的檔案."""
        files = []
        for i in range(5):
            f = temp_dir / f"invalid{i}.py"
            f.write_text("print('unclosed", encoding="utf-8")
            files.append(str(f))

        success_count, error_count, errors = check_files_parallel(files)

        assert success_count == 0
        assert error_count == 5
        assert len(errors) == 5

    def test_check_file_complex_syntax(self, temp_dir):
        """測試複雜的 Python 語法."""
        complex_code = '''
import asyncio
from typing import List, Dict, Optional, Union
from dataclasses import dataclass

@dataclass
class MyClass:
    name: str
    value: int = 0

async def async_func(items: List[Dict[str, Union[int, str]]]) -> Optional[str]:
    """複雜的非同步函數."""
    result = [x for x in items if x.get("value", 0) > 0]
    return result[0]["name"] if result else None

def decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@decorator
def main():
    with open("test.txt", "w") as f:
        f.write("test")

if __name__ == "__main__":
    main()
'''
        test_file = temp_dir / "complex.py"
        test_file.write_text(complex_code, encoding="utf-8")

        is_valid, error = check_file_syntax(str(test_file))

        assert is_valid is True
        assert error == ""

    def test_check_file_f_string(self, temp_dir):
        """測試 f-string 語法."""
        code = """
name = "World"
value = 42
print(f"Hello, {name}!")
print(f"Value: {value:>10}")
print(f"Expression: {2 + 2}")
"""
        test_file = temp_dir / "fstring.py"
        test_file.write_text(code, encoding="utf-8")

        is_valid, error = check_file_syntax(str(test_file))

        assert is_valid is True
        assert error == ""

    def test_check_file_walrus_operator(self, temp_dir):
        """測試海象運算符 := (Python 3.8+)."""
        code = """
if (n := len([1, 2, 3])) > 2:
    print(f"Length is {n}")

while (line := input()) != "quit":
    print(f"You entered: {line}")
"""
        test_file = temp_dir / "walrus.py"
        test_file.write_text(code, encoding="utf-8")

        is_valid, error = check_file_syntax(str(test_file))

        assert is_valid is True
        assert error == ""

    def test_check_file_match_statement(self, temp_dir):
        """測試 match 語句 (Python 3.10+)."""
        code = """
def http_error(status):
    match status:
        case 400:
            return "Bad request"
        case 404:
            return "Not found"
        case 418:
            return "I'm a teapot"
        case _:
            return "Something's wrong"
"""
        test_file = temp_dir / "match.py"
        test_file.write_text(code, encoding="utf-8")

        is_valid, _error = check_file_syntax(str(test_file))

        # 根據 Python 版本決定結果

        assert is_valid is True
