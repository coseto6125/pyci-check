"""測試國際化功能."""

import tempfile
from pathlib import Path

import pytest

from pyci_check.i18n import _find_pyproject_toml, _normalize_locale, get_locale, t


class TestI18n:
    """國際化測試."""

    def test_normalize_locale_zh_tw(self):
        """測試正規化繁體中文."""
        assert _normalize_locale("zh_TW") == "zh_TW"
        assert _normalize_locale("zh-TW") == "zh_TW"
        assert _normalize_locale("zh_tw") == "zh_TW"

    def test_normalize_locale_zh_cn(self):
        """測試正規化簡體中文."""
        assert _normalize_locale("zh_CN") == "zh_CN"
        assert _normalize_locale("zh-CN") == "zh_CN"
        assert _normalize_locale("zh_cn") == "zh_CN"
        assert _normalize_locale("zh") == "zh_CN"

    def test_normalize_locale_en(self):
        """測試正規化英文."""
        assert _normalize_locale("en") == "en"
        assert _normalize_locale("en_US") == "en"
        assert _normalize_locale("en-US") == "en"

    def test_normalize_locale_unknown(self):
        """測試未知語言."""
        assert _normalize_locale("fr") == "en"
        assert _normalize_locale("ja") == "en"

    def test_translation_function(self):
        """測試翻譯函數."""
        import os

        original_cwd = os.getcwd()
        try:
            # 測試基本翻譯
            result = t("syntax.success")
            assert isinstance(result, str)
            assert len(result) > 0
        finally:
            # 確保恢復目錄
            if os.path.exists(original_cwd):
                os.chdir(original_cwd)

    def test_translation_with_args(self):
        """測試帶參數的翻譯."""
        import os

        original_cwd = os.getcwd()
        try:
            result = t("syntax.checking", 5)
            assert isinstance(result, str)
            assert "5" in result or "五" in result
        finally:
            if os.path.exists(original_cwd):
                os.chdir(original_cwd)

    def test_translation_missing_key(self):
        """測試缺失的翻譯鍵."""
        import os

        original_cwd = os.getcwd()
        try:
            result = t("nonexistent.key")
            # 應該返回鍵本身
            assert result == "nonexistent.key"
        finally:
            if os.path.exists(original_cwd):
                os.chdir(original_cwd)

    def test_find_pyproject_toml_exists(self):
        """測試尋找存在的 pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 創建 pyproject.toml
            pyproject_path = Path(tmpdir) / "pyproject.toml"
            pyproject_path.write_text("[project]\nname = 'test'\n")

            # 清除 cache
            _find_pyproject_toml.cache_clear()

            # 切換到臨時目錄
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = _find_pyproject_toml()
                assert result is not None
                # _find_pyproject_toml() 回傳字串而非 Path
                assert Path(result).name == "pyproject.toml"
            finally:
                os.chdir(original_cwd)
                _find_pyproject_toml.cache_clear()

    def test_find_pyproject_toml_not_exists(self):
        """測試尋找不存在的 pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 清除 cache
            _find_pyproject_toml.cache_clear()

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = _find_pyproject_toml()
                # 可能找到上層的 pyproject.toml 或返回 None
                assert result is None or Path(result).exists()
            finally:
                os.chdir(original_cwd)
                _find_pyproject_toml.cache_clear()

    def test_get_locale_from_pyproject(self):
        """測試從 pyproject.toml 讀取語言設定."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 創建 pyproject.toml
            pyproject_path = Path(tmpdir) / "pyproject.toml"
            pyproject_content = """
[tool.pyci-check]
language = "zh_CN"
"""
            pyproject_path.write_text(pyproject_content)

            # 清除 cache
            _find_pyproject_toml.cache_clear()
            get_locale.cache_clear()

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                locale = get_locale()
                assert locale == "zh_CN"
            finally:
                os.chdir(original_cwd)
                # 恢復 cache
                _find_pyproject_toml.cache_clear()
                get_locale.cache_clear()
