"""測試 Git hooks 功能."""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from pyci_check.git_hook import (
    PYCI_CHECK_END_MARKER,
    PYCI_CHECK_START_MARKER,
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

    def test_find_git_directory_not_exists(self, temp_dir):
        """測試找不到 .git 目錄."""
        os.chdir(temp_dir)
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
