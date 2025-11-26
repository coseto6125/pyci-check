"""Traditional Chinese (Taiwan) translations."""

TRANSLATIONS = {
    # CLI help
    "cli.description": "快速的 Python 語法與 import 檢查工具,專為 Git hooks 設計",
    "cli.help.quiet": "減少輸出訊息",
    "cli.help.fail_fast": "發現錯誤時立即停止",
    "cli.help.timeout": "Import 檢查超時秒數 (預設: 30)",
    "cli.help.check_relative": "禁止相對導入 (發現時視為錯誤)",
    "cli.help.venv": "虛擬環境路徑 (如: . 或 /path/to/project)",
    "cli.help.i_understand": "我理解 import 檢查會實際載入並執行所有模組的程式碼",
    "cli.help.subcommand": "子指令",
    "cli.help.syntax": "檢查 Python 語法",
    "cli.help.imports": "檢查 import 依賴",
    "cli.help.install_hooks": "安裝 Git hooks",
    "cli.help.uninstall_hooks": "移除 Git hooks",
    "cli.help.hook_type": "Hook 類型 (預設: pre-commit)",
    "cli.examples": """範例:
  pyci-check syntax                                        # 僅檢查語法
  pyci-check imports --i-understand-this-will-execute-code # 檢查 import (會執行程式碼)
  pyci-check --quiet --i-understand-this-will-execute-code # 安靜模式執行所有檢查
  pyci-check install-hooks                                 # 安裝 pre-commit hook
  pyci-check install-hooks --type pre-push                 # 安裝 pre-push hook
  pyci-check uninstall-hooks                               # 移除所有 hooks
""",
    # Syntax check
    "syntax.no_files": "未找到 Python 檔案",
    "syntax.checking": "檢查 {} 個檔案的語法...",
    "syntax.success": "✓ 所有檔案語法正確",
    # Import check - execution
    "imports.checking": "檢查 import 依賴...",
    "imports.pythonpath": "PYTHONPATH: {}",
    "imports.venv": "虛擬環境: {}",
    "imports.mode_static": "✓ 模式: 靜態分析 (安全,不執行程式碼)",
    "imports.mode_static_hint": "💡 提示: 如需檢測運行時錯誤,可加上 --i-understand-this-will-execute-code 參數",
    "imports.mode_execute": "⚠️  模式: 真實執行 import (會載入執行所有程式碼)",
    "imports.mode_execute_warning": "⚠️  安全提醒: 可能觸發副作用 (檔案寫入、網路請求、系統變更等)",
    "imports.relative_import_warning": "⚠️  相對導入: {}:{} - {}",
    "imports.module_failed": "❌ 載入失敗: {}",
    "imports.file": "   檔案: {}:{}",
    "imports.statement": "   敘述: {}",
    "imports.reason": "   原因: {}",
    "imports.success": "✓ 所有 import 依賴正確",
    # Check all
    "check_all.start": "開始執行檢查...",
    "check_all.syntax_phase": "[1/2] 語法檢查",
    "check_all.imports_phase": "[2/2] Import 檢查",
    "check_all.success": "✓ 所有檢查通過",
    "check_all.errors": "✗ 發現錯誤",
    # Git hooks
    "hooks.find_git_error": "錯誤: 找不到 .git 目錄",
    "hooks.find_git_hint": "請確認你在 Git repository 中執行此指令",
    "hooks.create_error": "建立 hook 失敗: {}",
    "hooks.malformed_markers": "⚠️  Hook 檔案格式錯誤: 找到開始標記但缺少結束標記",
    "hooks.remove_error": "移除 hook 區塊失敗: {}",
    "hooks.file_exists": "⚠️  {} 已存在",
    "hooks.overwrite_prompt": "是否覆蓋? (y/N): ",
    "hooks.skip": "跳過 {} hook",
    "hooks.install_success": "✓ 已安裝 {} hook: {}",
    "hooks.uninstall_success": "✓ 已移除 {} hook",
    "hooks.uninstall_not_pyci": "⚠️  {} 不是由 pyci-check 產生,跳過",
    "hooks.uninstall_none_found": "沒有找到需要移除的 hooks",
    # Hook templates
    "hooks.template.no_py_files": "沒有 Python 檔案需要檢查",
    "hooks.template.checking": "執行 Python 檢查...",
    "hooks.template.not_installed": "錯誤: pyci-check 未安裝",
    "hooks.template.install_hint": "請執行: pip install pyci-check",
    # Import check (standalone mode - when imports.py is run directly)
    "imports.standalone.relative_warning": "[警告] 相對導入: {} 第 {} 行: {}",
    "imports.standalone.load_failed": "[錯誤] 載入失敗: {}",
    "imports.standalone.file_line": "       檔案: {} 第 {} 行",
    "imports.standalone.statement": "       敘述: {}",
    "imports.standalone.reason": "       原因: {}",
    "imports.standalone.summary_line": "-" * 60,
    "imports.standalone.summary_time": "檢查結束,總耗時: {:.2f} 秒",
    "imports.standalone.summary_modules": "檢查到共 {} 個獨立模組",
    "imports.standalone.summary_failed": "發現 {} 個模組載入失敗",
    "imports.standalone.summary_success": "所有模組載入成功 ✓",
    "imports.standalone.start_check": "開始檢查: {}",
    "imports.standalone.pythonpath": "PYTHONPATH: {}",
    "imports.standalone.exclude_dirs": "排除目錄: {}",
    "imports.standalone.exclude_files": "排除檔案: {}",
    "imports.standalone.mode": "使用 subprocess 並行檢查（真正執行 import）",
    "imports.standalone.found_modules": "找到 {} 個獨立模組,開始檢查...",
    "imports.standalone.run_dynamic": "執行動態 import 檢查: {}",
}
