"""Git hooks 安裝與管理工具."""

import os
import stat
import subprocess

from pyci_check.i18n import t


def find_git_directory() -> str | None:
    """尋找 .git 目錄."""
    current = os.getcwd()

    # 檢查當前目錄
    git_dir = os.path.join(current, ".git")
    if os.path.exists(git_dir) and os.path.isdir(git_dir):
        return git_dir

    # 往上層找
    while True:
        parent = os.path.dirname(current)
        if parent == current:  # 已到根目錄
            break
        git_dir = os.path.join(parent, ".git")
        if os.path.exists(git_dir) and os.path.isdir(git_dir):
            return git_dir
        current = parent

    return None


def get_staged_python_files() -> list[str]:
    """取得 staged 的 Python 檔案."""
    try:
        result = subprocess.run(
            ["/usr/bin/git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.strip().split("\n")
        return [f for f in files if f.endswith(".py") and f]
    except subprocess.CalledProcessError:
        return []


def get_changed_python_files(remote_branch: str = "origin/main") -> list[str]:
    """取得相對於遠端分支變更的 Python 檔案."""
    try:
        result = subprocess.run(  # noqa: S603
            ["/usr/bin/git", "diff", "--name-only", f"{remote_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            # 如果 origin/main 不存在,嘗試其他分支
            result = subprocess.run(
                ["/usr/bin/git", "diff", "--name-only", "HEAD~1...HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )

        files = result.stdout.strip().split("\n")
        return [f for f in files if f.endswith(".py") and f]
    except subprocess.CalledProcessError:
        return []


# Hook 區塊標記
PYCI_CHECK_START_MARKER = "# >>> pyci-check start >>>"
PYCI_CHECK_END_MARKER = "# <<< pyci-check end <<<"

PRE_COMMIT_HOOK_CONTENT = """# Check for staged Python files
STAGED_PY_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\\.py$' || true)

if [ -n "$STAGED_PY_FILES" ]; then
    echo "Running pyci-check..."

    # Run checks
    if command -v pyci-check &> /dev/null; then
        pyci-check check $STAGED_PY_FILES --quiet --fail-fast
    else
        echo "Error: pyci-check not installed"
        echo "Please run: pip install pyci-check"
        exit 1
    fi
fi
"""

PRE_PUSH_HOOK_CONTENT = """# Check for changed Python files
CHANGED_PY_FILES=$(git diff --name-only origin/main...HEAD 2>/dev/null | grep -E '\\.py$' || \
                   git diff --name-only HEAD~1...HEAD 2>/dev/null | grep -E '\\.py$' || true)

if [ -n "$CHANGED_PY_FILES" ]; then
    echo "Running pyci-check..."

    # Run checks
    if command -v pyci-check &> /dev/null; then
        pyci-check check $CHANGED_PY_FILES --quiet --fail-fast
    else
        echo "Error: pyci-check not installed"
        echo "Please run: pip install pyci-check"
        exit 1
    fi
fi
"""


def add_or_update_hook_content(hook_path: str, hook_content: str) -> bool:
    """
    追加或更新 hook 內容.

    如果檔案不存在,建立新的 hook 檔案 (包含 shebang)
    如果檔案存在,追加或更新 pyci-check 區塊

    Args:
        hook_path: Hook 檔案路徑
        hook_content: pyci-check 的 hook 內容

    Returns:
        True 成功, False 失敗
    """
    try:
        # 讀取現有內容 (如果存在)
        if os.path.exists(hook_path):
            with open(hook_path, encoding="utf-8") as f:
                existing_content = f.read()
        else:
            # 新檔案,加入 shebang 和 set -e
            existing_content = "#!/usr/bin/env bash\nset -e\n\n"

        # 檢查是否已經有 pyci-check 區塊
        if PYCI_CHECK_START_MARKER in existing_content:
            # 更新現有區塊
            start_idx = existing_content.find(PYCI_CHECK_START_MARKER)
            end_idx = existing_content.find(PYCI_CHECK_END_MARKER)

            if end_idx == -1:
                # 只有開始標記,沒有結束標記 (不正常情況)
                print(t("hooks.malformed_markers"))
                return False

            # 取得 end marker 所在行的結尾
            end_line_end = existing_content.find("\n", end_idx)
            if end_line_end == -1:
                end_line_end = len(existing_content)
            else:
                end_line_end += 1  # 包含換行符

            # 替換區塊
            new_block = f"{PYCI_CHECK_START_MARKER}\n{hook_content}\n{PYCI_CHECK_END_MARKER}\n"
            new_content = existing_content[:start_idx] + new_block + existing_content[end_line_end:]
        else:
            # 追加新區塊
            new_block = f"\n{PYCI_CHECK_START_MARKER}\n{hook_content}\n{PYCI_CHECK_END_MARKER}\n"
            new_content = existing_content.rstrip() + new_block

        # 寫入檔案
        with open(hook_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        # 設定執行權限
        current_permissions = os.stat(hook_path).st_mode
        os.chmod(hook_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        return True
    except OSError as e:
        print(t("hooks.create_error", e))
        return False


def install_hooks(hook_type: str = "pre-commit") -> int:
    """
    安裝 Git hooks (追加模式).

    Args:
        hook_type: Hook 類型 (pre-commit, pre-push, both)

    Returns:
        0 成功, 1 失敗
    """
    git_dir = find_git_directory()

    if git_dir is None:
        print(t("hooks.find_git_error"))
        print(t("hooks.find_git_hint"))
        return 1

    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    success = True

    # 安裝 pre-commit hook
    if hook_type in {"pre-commit", "both"}:
        pre_commit_path = os.path.join(hooks_dir, "pre-commit")

        if add_or_update_hook_content(pre_commit_path, PRE_COMMIT_HOOK_CONTENT):
            if os.path.exists(pre_commit_path):
                with open(pre_commit_path, encoding="utf-8") as f:
                    if PYCI_CHECK_START_MARKER in f.read():
                        # 檢查是新增還是更新
                        print(t("hooks.install_success", "pre-commit", pre_commit_path))
            else:
                print(t("hooks.install_success", "pre-commit", pre_commit_path))
        else:
            success = False

    # 安裝 pre-push hook
    if hook_type in {"pre-push", "both"}:
        pre_push_path = os.path.join(hooks_dir, "pre-push")

        if add_or_update_hook_content(pre_push_path, PRE_PUSH_HOOK_CONTENT):
            print(t("hooks.install_success", "pre-push", pre_push_path))
        else:
            success = False

    return 0 if success else 1


def remove_pyci_check_block(hook_path: str) -> bool:
    """
    從 hook 檔案中移除 pyci-check 區塊.

    Args:
        hook_path: Hook 檔案路徑

    Returns:
        True 成功移除, False 沒有找到或失敗
    """
    try:
        if not os.path.exists(hook_path):
            return False

        with open(hook_path, encoding="utf-8") as f:
            content = f.read()

        # 檢查是否有 pyci-check 區塊
        if PYCI_CHECK_START_MARKER not in content:
            return False

        # 找到區塊位置
        start_idx = content.find(PYCI_CHECK_START_MARKER)
        end_idx = content.find(PYCI_CHECK_END_MARKER)

        if end_idx == -1:
            # 只有開始標記,沒有結束標記
            print(t("hooks.malformed_markers"))
            return False

        # 取得 end marker 所在行的結尾
        end_line_end = content.find("\n", end_idx)
        if end_line_end == -1:
            end_line_end = len(content)
        else:
            end_line_end += 1  # 包含換行符

        # 移除區塊 (包含前面的空行)
        # 檢查 start_idx 前面是否有空行
        start_line_start = start_idx
        while start_line_start > 0 and content[start_line_start - 1] in {"\n", " ", "\t"}:
            start_line_start -= 1
            if content[start_line_start] == "\n" and (start_line_start == 0 or content[start_line_start - 1] == "\n"):
                break

        new_content = content[:start_line_start] + content[end_line_end:]

        # 如果移除後只剩 shebang 和 set -e,刪除整個檔案
        stripped = new_content.strip()
        if stripped in {"#!/usr/bin/env bash", "#!/usr/bin/env bash\nset -e", "#!/bin/bash", "#!/bin/bash\nset -e"}:
            os.remove(hook_path)
        else:
            # 寫回檔案
            with open(hook_path, "w", encoding="utf-8") as f:
                f.write(new_content)

        return True
    except OSError as e:
        print(t("hooks.remove_error", e))
        return False


def uninstall_hooks() -> int:
    """
    移除 Git hooks 中的 pyci-check 區塊 (保留其他內容).

    Returns:
        0 成功, 1 失敗
    """
    git_dir = find_git_directory()

    if git_dir is None:
        print(t("hooks.find_git_error"))
        return 1

    hooks_dir = os.path.join(git_dir, "hooks")
    removed_count = 0

    for hook_name in ["pre-commit", "pre-push"]:
        hook_path = os.path.join(hooks_dir, hook_name)

        if remove_pyci_check_block(hook_path):
            print(t("hooks.uninstall_success", hook_name))
            removed_count += 1

    if removed_count == 0:
        print(t("hooks.uninstall_none_found"))

    return 0
