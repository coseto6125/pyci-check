"""測試 pyci_check.config 專案設定模組."""

import dataclasses
import tempfile
from pathlib import Path

import pytest

from pyci_check.config import clear_cache, find_pyproject, load, resolve_venv


def _write_pyproject(tmpdir: str, content: str) -> None:
    Path(tmpdir).joinpath("pyproject.toml").write_text(content, encoding="utf-8")


class TestFindPyproject:
    """find_pyproject 的搜尋規則."""

    def test_find_pyproject_in_project_dir_itself(self):
        """專案目錄本層就有 pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, "[project]\nname = 'x'\n")
            assert find_pyproject(tmpdir) == str(Path(tmpdir) / "pyproject.toml")

    def test_find_pyproject_walks_up_to_parent(self):
        """子目錄沒有時往上層找."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, "[project]\nname = 'x'\n")
            nested = Path(tmpdir) / "a" / "b"
            nested.mkdir(parents=True)
            assert find_pyproject(str(nested)) == str(Path(tmpdir) / "pyproject.toml")

    def test_find_pyproject_returns_none_when_absent(self):
        """整條上層都沒有時回傳 None (上層檔案系統若恰有 pyproject 則只驗證路徑合理)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            deep = Path(tmpdir) / "a" / "b"
            deep.mkdir(parents=True)
            result = find_pyproject(str(deep))
            assert result is None or result.endswith("pyproject.toml")


class TestLoad:
    """load 的合併與正規化."""

    def test_load_defaults_without_pyproject(self):
        """沒有 pyproject.toml 時回傳預設值."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = load(tmpdir)
            assert cfg.pyproject_path is None
            assert cfg.src_dirs == ()
            assert cfg.exclude_dirs == frozenset()
            assert cfg.exclude_files == frozenset()
            assert cfg.check_test_purity is False
            assert cfg.venv_setting is None
            assert cfg.language == "en"

    def test_load_merges_pyci_and_ruff_excludes_with_dedup(self):
        """四個 exclude 來源合併去重,字串值也接受."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(
                tmpdir,
                """
[tool.pyci-check]
exclude = [".venv", "build"]
extend-exclude = "experiments/"

[tool.ruff]
exclude = ["build", "node_modules"]
""",
            )
            cfg = load(tmpdir)
            assert cfg.exclude_dirs == frozenset({".venv", "build", "experiments", "node_modules"})

    def test_load_classifies_files_by_extension(self):
        """Basename 有副檔名且不以 . 開頭者歸為檔案排除."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, '[tool.ruff]\nextend-exclude = ["starlette_app.py", ".venv"]\n')
            cfg = load(tmpdir)
            assert cfg.exclude_files == frozenset({"starlette_app.py"})
            assert cfg.exclude_dirs == frozenset({".venv"})

    def test_load_src_accepts_single_string(self):
        """Src 允許單一字串."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, '[tool.ruff]\nsrc = "src"\n')
            assert load(tmpdir).src_dirs == ("src",)

    def test_load_reads_check_test_purity(self):
        """check-test-purity 旗標."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, "[tool.pyci-check]\ncheck-test-purity = true\n")
            assert load(tmpdir).check_test_purity is True

    def test_load_venv_setting(self):
        """Venv 設定原值取出."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, '[tool.pyci-check]\nvenv = "/opt/myenv"\n')
            assert load(tmpdir).venv_setting == "/opt/myenv"

    def test_load_language_defaults_to_en_when_key_missing(self):
        """缺 language key 時為 en."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, "[project]\nname = 'x'\n")
            assert load(tmpdir).language == "en"

    def test_load_invalid_toml_falls_back_to_defaults(self):
        """TOML 解析失敗時退回預設值,不 raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, "not [valid toml")
            cfg = load(tmpdir)
            assert cfg.src_dirs == ()
            assert cfg.language == "en"

    def test_load_result_is_cached_and_clearable(self):
        """同路徑快取同一物件;clear_cache 後重新載入."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, "[project]\nname = 'x'\n")
            first = load(tmpdir)
            assert load(tmpdir) is first
            clear_cache()
            second = load(tmpdir)
            assert second == first
            assert second is not first

    def test_config_is_immutable(self):
        """ProjectConfig 是 frozen dataclass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = load(tmpdir)
            with pytest.raises(dataclasses.FrozenInstanceError):
                cfg.language = "fr"


class TestResolveVenv:
    """venv 優先順序: CLI 參數 > pyproject > 自動偵測 .venv."""

    @staticmethod
    def _cfg_with(venv_setting: str | None) -> str:
        return f'[tool.pyci-check]\nvenv = "{venv_setting}"\n' if venv_setting else "[project]\nname = 'x'\n"

    def test_resolve_venv_explicit_arg_wins(self):
        """CLI 參數優先於一切."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, self._cfg_with(".venvx"))
            assert resolve_venv("cli-venv", load(tmpdir)) == "cli-venv"

    def test_resolve_venv_pyproject_setting_second(self):
        """其次讀 pyproject 設定."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, self._cfg_with(".venvx"))
            assert resolve_venv(None, load(tmpdir)) == ".venvx"

    def test_resolve_venv_autodetect_dot_venv_third(self):
        """.venv 目錄存在時回傳 "."."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, self._cfg_with(None))
            (Path(tmpdir) / ".venv").mkdir()
            assert resolve_venv(None, load(tmpdir)) == "."

    def test_resolve_venv_returns_none_when_nothing_found(self):
        """三者皆無時回傳 None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_pyproject(tmpdir, self._cfg_with(None))
            assert resolve_venv(None, load(tmpdir)) is None
