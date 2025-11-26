"""Internationalization support."""

import os
import tomllib
from functools import lru_cache

# 效能優化: 預先定義語言對照表避免重複創建字典
# 所有鍵都使用小寫,且統一將 - 轉為 _
_LOCALE_MAP = {
    "zh_tw": "zh_TW",
    "zh_cn": "zh_CN",
    "zh": "zh_CN",  # 中文預設使用簡體
    "en": "en",
    "en_us": "en",
}


@lru_cache(maxsize=1)
def _find_pyproject_toml() -> str | None:
    """
    尋找 pyproject.toml 檔案.

    優化: 使用 lru_cache 快取結果,避免重複遍歷目錄
    """
    try:
        current = os.getcwd()
    except (FileNotFoundError, OSError):
        # 當前目錄不存在（例如在測試中被刪除）
        return None

    while True:
        pyproject = os.path.join(current, "pyproject.toml")
        if os.path.exists(pyproject):
            return pyproject
        parent = os.path.dirname(current)
        if parent == current:  # 已到根目錄
            break
        current = parent
    return None


@lru_cache(maxsize=1)
def get_locale() -> str:
    """
    取得當前語言設定.

    優先順序:
    1. pyproject.toml 中的 [tool.pyci-check] language 設定
    2. 預設 en
    """
    # 從 pyproject.toml 讀取
    pyproject_path = _find_pyproject_toml()
    if not pyproject_path:
        return "en"

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return "en"

    # 讀取 [tool.pyci-check] language
    pyci_check = data.get("tool", {}).get("pyci-check", {})
    lang = pyci_check.get("language")

    if lang and isinstance(lang, str):
        return _normalize_locale(lang.strip())

    return "en"


def _normalize_locale(lang: str) -> str:
    """
    正規化語言代碼.

    優化:
    - 使用預定義的 _LOCALE_MAP 常數避免重複創建字典
    - 統一轉小寫並將 - 替換為 _,字典從 14 項縮減到 5 項
    """
    lang = lang.split(".", maxsplit=1)[0].lower().replace("-", "_")
    return _LOCALE_MAP.get(lang, "en")


@lru_cache(maxsize=3)
def _load_translations(locale: str) -> dict[str, str]:
    """載入翻譯檔."""
    if locale == "zh_TW":
        from pyci_check.locales.zh_TW import TRANSLATIONS
    elif locale == "zh_CN":
        from pyci_check.locales.zh_CN import TRANSLATIONS
    else:
        from pyci_check.locales.en import TRANSLATIONS
    return TRANSLATIONS


def t(key: str, *args, **kwargs) -> str:
    """
    翻譯函數.

    Args:
        key: 翻譯鍵值
        *args: 格式化參數 (用於 str.format())
        **kwargs: 格式化參數 (用於 str.format())

    Returns:
        翻譯後的字串

    Examples:
        t("syntax.checking", 5)  # "Checking syntax of 5 files..."
        t("imports.venv", path="/path/to/venv")  # "Virtual environment: /path/to/venv"
    """
    locale = get_locale()
    translations = _load_translations(locale)

    text = translations.get(key, key)

    # 如果有參數則進行格式化
    if args or kwargs:
        try:
            return text.format(*args, **kwargs)
        except (IndexError, KeyError):
            # 格式化失敗則返回原始文字
            return text

    return text
