"""測試 Git hooks 功能."""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from pyci_check.git_hook import (
    PRE_COMMIT_HOOK_CONTENT,
    PRE_PUSH_HOOK_CONTENT,
    PYCI_CHECK_END_MARKER,
    PYCI_CHECK_START_MARKER,
    RESOLVE_TOOL_SNIPPET,
    add_or_update_hook_content,
    find_git_directory,
    remove_pyci_check_block,
)


class TestGitHooks:
    """Git hooks 測試."""

    @pytest.fixture
    def temp_git_repo(self, temp_dir):
        """創建臨時 Git 倉庫."""
        git_dir = temp_dir / ".git"
        git_dir.mkdir()
        (git_dir / "hooks").mkdir()
        return temp_dir

    def test_find_git_directory_exists(self, temp_git_repo):
        """測試找到 .git 目錄."""
        os.chdir(temp_git_repo)
        git_dir = find_git_directory()

        assert git_dir is not None
        assert Path(git_dir).name == ".git"

    def test_find_git_directory_not_exists(self, temp_dir, monkeypatch):
        """測試找不到 .git 目錄."""
        os.chdir(temp_dir)
        # 強制讓任何 .git 的檢查都回傳 False
        original_exists = os.path.exists

        def mock_exists(path):
            if path.endswith(".git"):
                return False
            return original_exists(path)

        monkeypatch.setattr(os.path, "exists", mock_exists)
        git_dir = find_git_directory()

        assert git_dir is None

    def test_find_git_directory_parent(self, temp_git_repo):
        """測試在子目錄中找到父目錄的 .git."""
        subdir = temp_git_repo / "src" / "subdir"
        subdir.mkdir(parents=True)
        os.chdir(subdir)

        git_dir = find_git_directory()

        assert git_dir is not None
        assert Path(git_dir).name == ".git"

    # 新的追加模式測試

    def test_add_hook_to_new_file(self, temp_dir):
        """測試追加 hook 到新檔案."""
        hook_path = temp_dir / "pre-commit"
        hook_content = "echo 'test hook'"

        result = add_or_update_hook_content(str(hook_path), hook_content)

        assert result is True
        assert hook_path.exists()

        content = hook_path.read_text()
        assert "#!/usr/bin/env bash" in content
        assert PYCI_CHECK_START_MARKER in content
        assert hook_content in content
        assert PYCI_CHECK_END_MARKER in content

    def test_add_hook_to_existing_file(self, temp_dir):
        """測試追加 hook 到現有檔案 (保留原有內容)."""
        hook_path = temp_dir / "pre-commit"

        # 建立現有 hook
        existing_content = """#!/usr/bin/env bash
# My custom hook
echo "Running my checks..."
"""
        hook_path.write_text(existing_content, encoding="utf-8")

        hook_content = "echo 'pyci-check'"

        result = add_or_update_hook_content(str(hook_path), hook_content)

        assert result is True

        content = hook_path.read_text()
        # 原有內容應該保留
        assert "My custom hook" in content
        assert "Running my checks..." in content
        # 新內容應該追加
        assert PYCI_CHECK_START_MARKER in content
        assert hook_content in content
        assert PYCI_CHECK_END_MARKER in content

    def test_update_existing_hook_block(self, temp_dir):
        """測試更新現有的 pyci-check 區塊 (不重複添加)."""
        hook_path = temp_dir / "pre-commit"

        # 建立包含 pyci-check 區塊的 hook
        initial_content = f"""#!/usr/bin/env bash

{PYCI_CHECK_START_MARKER}
echo 'old content'
{PYCI_CHECK_END_MARKER}

echo 'other content'
"""
        hook_path.write_text(initial_content, encoding="utf-8")

        new_hook_content = "echo 'new content'"

        result = add_or_update_hook_content(str(hook_path), new_hook_content)

        assert result is True

        content = hook_path.read_text()
        # 舊內容應該被替換
        assert "old content" not in content
        assert "new content" in content
        # 其他內容應該保留
        assert "other content" in content
        # 只應該有一個 pyci-check 區塊
        assert content.count(PYCI_CHECK_START_MARKER) == 1

    def test_remove_pyci_check_block(self, temp_dir):
        """測試移除 pyci-check 區塊 (保留其他內容)."""
        hook_path = temp_dir / "pre-commit"

        # 建立包含 pyci-check 區塊和其他內容的 hook
        content_with_block = f"""#!/usr/bin/env bash
set -e

# Custom hook
echo "My custom logic"

{PYCI_CHECK_START_MARKER}
echo 'pyci-check content'
{PYCI_CHECK_END_MARKER}

echo "More custom logic"
"""
        hook_path.write_text(content_with_block, encoding="utf-8")

        result = remove_pyci_check_block(str(hook_path))

        assert result is True
        assert hook_path.exists()  # 檔案應該保留

        content = hook_path.read_text()
        # pyci-check 區塊應該被移除
        assert PYCI_CHECK_START_MARKER not in content
        assert PYCI_CHECK_END_MARKER not in content
        assert "pyci-check content" not in content
        # 自定義內容應該保留
        assert "My custom logic" in content
        assert "More custom logic" in content

    def test_remove_pyci_check_block_delete_file_if_empty(self, temp_dir):
        """測試移除 pyci-check 區塊後,如果只剩 shebang 則刪除檔案."""
        hook_path = temp_dir / "pre-commit"

        # 建立只包含 shebang 和 pyci-check 區塊的 hook
        content_only_pyci = f"""#!/usr/bin/env bash
set -e

{PYCI_CHECK_START_MARKER}
echo 'pyci-check content'
{PYCI_CHECK_END_MARKER}
"""
        hook_path.write_text(content_only_pyci, encoding="utf-8")

        result = remove_pyci_check_block(str(hook_path))

        assert result is True
        assert not hook_path.exists()  # 檔案應該被刪除

    def test_remove_pyci_check_block_not_found(self, temp_dir):
        """測試移除不存在的 pyci-check 區塊."""
        hook_path = temp_dir / "pre-commit"

        # 建立不包含 pyci-check 區塊的 hook
        hook_path.write_text("#!/usr/bin/env bash\necho 'test'", encoding="utf-8")

        result = remove_pyci_check_block(str(hook_path))

        assert result is False

    def test_hook_file_executable(self, temp_dir):
        """測試 hook 檔案有執行權限."""
        import sys

        hook_path = temp_dir / "pre-commit"

        hook_content = "echo 'test'"
        add_or_update_hook_content(str(hook_path), hook_content)

        # Windows 上沒有執行權限的概念,跳過此測試
        if sys.platform == "win32":
            pytest.skip("Windows does not support execute permissions")

        # 檢查檔案有執行權限
        assert os.access(hook_path, os.X_OK)
        file_stat = hook_path.stat()
        assert file_stat.st_mode & stat.S_IXUSR


class TestToolResolution:
    """Hook 產生的 shell 片段必須優先採用專案 venv 內的工具."""

    @staticmethod
    def _run_resolver(
        cwd: Path,
        tool: str,
        path_dir: Path | None = None,
        *,
        keep_system_path: bool = False,
        git_env: dict[str, str] | None = None,
    ) -> str:
        """
        在 cwd 執行 resolver 片段，回傳它挑中的路徑.

        PATH 只放測試準備的目錄，才能斷言 fallback 行為，所以直譯器要用絕對路徑呼叫。
        """
        shell = shutil.which("sh")
        script = f"{RESOLVE_TOOL_SNIPPET}\npyci_resolve {tool}\n"
        env = dict(os.environ)
        path = str(path_dir) if path_dir else ""
        if keep_system_path:
            # The resolver shells out to git for the worktree lookup. Git prepends
            # its own exec-path to the hook's PATH, so git is always reachable
            # there; nothing else from coreutils is.
            path = os.pathsep.join(filter(None, (path, "/usr/bin", "/bin")))
        env["PATH"] = path
        env.pop("GIT_DIR", None)
        env.pop("GIT_COMMON_DIR", None)
        env.update(git_env or {})
        result = subprocess.run([shell, "-c", script], cwd=cwd, env=env, capture_output=True, text=True, check=False)
        # The hooks run under `set -e` and assign this with `TOOL=$(pyci_resolve ...)`,
        # so a non-zero exit here would abort the commit. Every case has to exit 0.
        assert result.returncode == 0, f"resolver exited {result.returncode}: {result.stderr}"
        return result.stdout.strip()

    @staticmethod
    def _make_executable(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    @pytest.mark.skipif(sys.platform == "win32" or shutil.which("sh") is None, reason="POSIX shell hook")
    def test_prefers_venv_tool_over_path(self, tmp_path: Path):
        self._make_executable(tmp_path / ".venv" / "bin" / "ruff")
        path_dir = tmp_path / "elsewhere"
        self._make_executable(path_dir / "ruff")

        assert self._run_resolver(tmp_path, "ruff", path_dir) == "./.venv/bin/ruff"

    @pytest.mark.skipif(sys.platform == "win32" or shutil.which("sh") is None, reason="POSIX shell hook")
    def test_falls_back_to_path_when_no_venv(self, tmp_path: Path):
        path_dir = tmp_path / "elsewhere"
        path_ruff = self._make_executable(path_dir / "ruff")

        assert self._run_resolver(tmp_path, "ruff", path_dir) == str(path_ruff)

    @pytest.mark.skipif(sys.platform == "win32" or shutil.which("sh") is None, reason="POSIX shell hook")
    def test_returns_nothing_when_tool_is_absent(self, tmp_path: Path):
        assert self._run_resolver(tmp_path, "ruff") == ""

    @pytest.mark.skipif(sys.platform == "win32" or shutil.which("sh") is None, reason="POSIX shell hook")
    def test_absent_tool_does_not_abort_under_set_e(self, tmp_path: Path):
        """Hook 以 set -e 執行，找不到工具要印出跳過訊息，不是中止 commit."""
        shell = shutil.which("sh")
        script = f'{RESOLVE_TOOL_SNIPPET}\nset -e\nTOOL=$(pyci_resolve absent-tool)\necho "survived:[$TOOL]"\n'
        result = subprocess.run([shell, "-c", script], cwd=tmp_path, env={"PATH": ""}, capture_output=True, text=True, check=False)

        assert result.returncode == 0
        assert result.stdout.strip() == "survived:[]"

    @pytest.mark.skipif(sys.platform == "win32" or shutil.which("sh") is None, reason="POSIX shell hook")
    def test_finds_windows_scripts_layout(self, tmp_path: Path):
        self._make_executable(tmp_path / ".venv" / "Scripts" / "ruff")

        assert self._run_resolver(tmp_path, "ruff") == "./.venv/Scripts/ruff"

    @pytest.mark.skipif(sys.platform == "win32" or shutil.which("sh") is None, reason="POSIX shell hook")
    def test_skips_a_directory_named_like_the_tool(self, tmp_path: Path):
        (tmp_path / ".venv" / "bin" / "ruff").mkdir(parents=True)
        path_dir = tmp_path / "elsewhere"
        path_ruff = self._make_executable(path_dir / "ruff")

        assert self._run_resolver(tmp_path, "ruff", path_dir) == str(path_ruff)

    @pytest.mark.skipif(
        sys.platform == "win32" or shutil.which("sh") is None or shutil.which("git") is None,
        reason="POSIX shell hook with git",
    )
    def test_linked_worktree_uses_the_main_checkout_venv(self, tmp_path: Path):
        """Linked worktree 通常沒有自己的 venv，要沿用主 checkout 的那一份."""
        git = shutil.which("git")
        main = tmp_path / "main"
        main.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
        for argv in (
            ["init", "-q", "."],
            ["commit", "-q", "--allow-empty", "-m", "init"],
            ["worktree", "add", "-q", "../linked", "-b", "feat"],
        ):
            subprocess.run([git, *argv], cwd=main, env=env, capture_output=True, check=True)
        main_ruff = self._make_executable(main / ".venv" / "bin" / "ruff")
        path_dir = tmp_path / "elsewhere"
        self._make_executable(path_dir / "ruff")

        selected = self._run_resolver(tmp_path / "linked", "ruff", path_dir, keep_system_path=True)

        assert selected == str(main_ruff)

    @pytest.mark.skipif(
        sys.platform == "win32" or shutil.which("sh") is None or shutil.which("git") is None,
        reason="POSIX shell hook with git",
    )
    def test_repo_under_a_worktrees_named_directory_keeps_its_own_root(self, tmp_path: Path):
        """`worktrees` 只是合法目錄名，不能當成 git worktree metadata 的結構標記."""
        git = shutil.which("git")
        repo = tmp_path / "base" / "worktrees" / "project"
        repo.mkdir(parents=True)
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
        subprocess.run([git, "init", "-q", "."], cwd=repo, env=env, capture_output=True, check=True)
        # 這個 venv 屬於別的專案，剛好落在「多剝一層」會踩到的位置。
        self._make_executable(tmp_path / ".venv" / "bin" / "ruff")
        path_dir = tmp_path / "elsewhere"
        path_ruff = self._make_executable(path_dir / "ruff")
        # git 以 --git-dir 啟動時會把絕對路徑匯出給 hook，正是誤判的觸發條件。
        git_env = {"GIT_DIR": str(repo / ".git")}

        selected = self._run_resolver(repo, "ruff", path_dir, keep_system_path=True, git_env=git_env)

        assert selected == str(path_ruff)

    def test_both_hooks_embed_the_resolver(self):
        assert "pyci_resolve()" in RESOLVE_TOOL_SNIPPET
        assert RESOLVE_TOOL_SNIPPET in PRE_COMMIT_HOOK_CONTENT
        assert RESOLVE_TOOL_SNIPPET in PRE_PUSH_HOOK_CONTENT
        assert "command -v ruff" not in PRE_COMMIT_HOOK_CONTENT
        assert "command -v pyci-check" not in PRE_PUSH_HOOK_CONTENT
