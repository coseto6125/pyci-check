"""測試國際化功能."""

import tempfile
from pathlib import Path

from pyci_check.i18n import _normalize_locale, get_locale, t


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
        """測試往上層尋找存在的 pyproject.toml."""
        from pyci_check.config import clear_cache, find_pyproject

        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "nested"
            subdir.mkdir()
            Path(tmpdir).joinpath("pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")

            clear_cache()
            try:
                result = find_pyproject(str(subdir))
                assert result is not None
                assert Path(result).name == "pyproject.toml"
            finally:
                clear_cache()

    def test_find_pyproject_toml_not_exists(self):
        """測試找不到 pyproject.toml 時回傳 None (上層若恰好有設定檔則只驗證路徑合理)."""
        from pyci_check.config import clear_cache, find_pyproject

        with tempfile.TemporaryDirectory() as tmpdir:
            deep = Path(tmpdir) / "a" / "b"
            deep.mkdir(parents=True)
            clear_cache()
            try:
                result = find_pyproject(str(deep))
                assert result is None or result.endswith("pyproject.toml")
            finally:
                clear_cache()

    def test_get_locale_from_pyproject(self):
        """測試從 pyproject.toml 讀取語言設定."""
        from pyci_check.config import clear_cache

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir).joinpath("pyproject.toml").write_text('[tool.pyci-check]\nlanguage = "zh_CN"\n', encoding="utf-8")
            clear_cache()

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                locale = get_locale()
                assert locale == "zh_CN"
            finally:
                os.chdir(original_cwd)
                clear_cache()
