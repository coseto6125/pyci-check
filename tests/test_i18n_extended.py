"""測試多語系支援 (i18n)."""

from unittest.mock import patch

from pyci_check.i18n import _normalize_locale, t


def test_normalize_locale():
    """測試語言代碼的正規化邏輯."""
    assert _normalize_locale("zh-TW") == "zh_TW"
    assert _normalize_locale("ZH_tw") == "zh_TW"
    assert _normalize_locale("zh-CN") == "zh_CN"
    assert _normalize_locale("zh") == "zh_CN"
    assert _normalize_locale("en-US") == "en"
    assert _normalize_locale("fr") == "en"  # 不支援的語言退回預設 en


def test_t_function_fallback():
    """測試未定義的 key 應該直接回傳 key 本身."""
    assert t("non_existent.key") == "non_existent.key"
    assert t("non_existent.key", "arg1") == "non_existent.key"


@patch("pyci_check.i18n.get_locale", return_value="en")
def test_t_function_en(*_args):
    """測試英文翻譯與格式化."""
    assert t("syntax.checking", 5) == "Checking syntax of 5 files..."
    assert t("imports.checking") == "Checking import dependencies..."


@patch("pyci_check.i18n.get_locale", return_value="zh_TW")
def test_t_function_zh_tw(*_args):
    """測試繁體中文翻譯與格式化."""
    assert t("syntax.checking", 5) == "檢查 5 個檔案的語法..."
    assert t("imports.checking") == "檢查 import 依賴..."


@patch("pyci_check.i18n.get_locale", return_value="zh_CN")
def test_t_function_zh_cn(*_args):
    """測試簡體中文翻譯與格式化."""
    assert t("syntax.checking", 5) == "检查 5 个文件的语法..."
    assert t("imports.checking") == "检查 import 依赖..."


def test_t_function_new_features():
    """測試新功能 (dependency / cycles) 的翻譯是否都有定義."""
    # 我們不 assert 具體文字，只 assert 它不等於 key (代表有翻到)
    keys_to_check = [
        "dependency.checking",
        "dependency.phantom",
        "dependency.orphan",
        "dependency.success",
        "cycles.checking",
        "cycles.found",
        "cycles.success",
    ]

    for locale in ["en", "zh_TW", "zh_CN"]:
        with patch("pyci_check.i18n.get_locale", return_value=locale):
            for key in keys_to_check:
                assert t(key) != key, f"Missing translation for {key} in {locale}"
