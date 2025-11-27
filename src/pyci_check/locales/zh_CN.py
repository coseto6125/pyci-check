"""Simplified Chinese (China) translations."""

TRANSLATIONS = {
    # CLI help
    "cli.description": "快速的 Python 语法与 import 检查工具,专为 Git hooks 设计",
    "cli.help.quiet": "减少输出信息",
    "cli.help.fail_fast": "发现错误时立即停止",
    "cli.help.timeout": "Import 检查超时秒数 (默认: 30)",
    "cli.help.check_relative": "禁止相对导入 (发现时视为错误)",
    "cli.help.venv": "虚拟环境路径 (如: . 或 /path/to/project)",
    "cli.help.i_understand": "我理解 import 检查会实际载入并执行所有模块的代码",
    "cli.help.subcommand": "子命令",
    "cli.help.syntax": "检查 Python 语法",
    "cli.help.imports": "检查 import 依赖",
    "cli.help.install_hooks": "安装 Git hooks",
    "cli.help.uninstall_hooks": "移除 Git hooks",
    "cli.help.hook_type": "Hook 类型 (默认: pre-commit)",
    "cli.examples": """示例:
  pyci-check syntax                                        # 仅检查语法
  pyci-check imports --i-understand-this-will-execute-code # 检查 import (会执行代码)
  pyci-check --quiet --i-understand-this-will-execute-code # 安静模式执行所有检查
  pyci-check install-hooks                                 # 安装 pre-commit hook
  pyci-check install-hooks --type pre-push                 # 安装 pre-push hook
  pyci-check uninstall-hooks                               # 移除所有 hooks
""",
    # Syntax check
    "syntax.no_files": "未找到 Python 文件",
    "syntax.checking": "检查 {} 个文件的语法...",
    "syntax.success": "✓ 所有文件语法正确",
    # Import check - execution
    "imports.checking": "检查 import 依赖...",
    "imports.pythonpath": "PYTHONPATH: {}",
    "imports.venv": "虚拟环境: {}",
    "imports.mode_static": "✓ 模式: 静态分析 (安全,不执行代码)",
    "imports.mode_static_hint": "💡 提示: 如需检测运行时错误,可加上 --i-understand-this-will-execute-code 参数",
    "imports.mode_execute": "⚠️  模式: 真实执行 import (会载入执行所有代码)",
    "imports.mode_execute_warning": "⚠️  安全提醒: 可能触发副作用 (文件写入、网络请求、系统变更等)",
    "imports.relative_import_warning": "⚠️  相对导入: {}:{} - {}",
    "imports.module_failed": "❌ 载入失败: {}",
    "imports.file": "   文件: {}:{}",
    "imports.statement": "   语句: {}",
    "imports.reason": "   原因: {}",
    "imports.success": "✓ 所有 import 依赖正确",
    # Check all
    "check_all.start": "开始执行检查...",
    "check_all.syntax_phase": "[1/2] 语法检查",
    "check_all.imports_phase": "[2/2] Import 检查",
    "check_all.success": "✓ 所有检查通过",
    "check_all.errors": "✗ 发现错误",
    # Git hooks
    "hooks.find_git_error": "错误: 找不到 .git 目录",
    "hooks.find_git_hint": "请确认你在 Git repository 中执行此命令",
    "hooks.create_error": "创建 hook 失败: {}",
    "hooks.malformed_markers": "⚠️  Hook 文件格式错误: 找到开始标记但缺少结束标记",
    "hooks.remove_error": "移除 hook 区块失败: {}",
    "hooks.file_exists": "⚠️  {} 已存在",
    "hooks.overwrite_prompt": "是否覆盖? (y/N): ",
    "hooks.skip": "跳过 {} hook",
    "hooks.install_success": "✓ 已安装 {} hook: {}",
    "hooks.uninstall_success": "✓ 已移除 {} hook",
    "hooks.uninstall_not_pyci": "⚠️  {} 不是由 pyci-check 生成,跳过",
    "hooks.uninstall_none_found": "没有找到需要移除的 hooks",
    # Hook templates
    "hooks.template.no_py_files": "没有 Python 文件需要检查",
    "hooks.template.checking": "执行 Python 检查...",
    "hooks.template.not_installed": "错误: pyci-check 未安装",
    "hooks.template.install_hint": "请执行: pip install pyci-check",
    # Import check (standalone mode - when imports.py is run directly)
    "imports.standalone.relative_warning": "[警告] 相对导入: {} 第 {} 行: {}",
    "imports.standalone.load_failed": "[错误] 载入失败: {}",
    "imports.standalone.file_line": "       文件: {} 第 {} 行",
    "imports.standalone.statement": "       语句: {}",
    "imports.standalone.reason": "       原因: {}",
    "imports.standalone.summary_line": "-" * 60,
    "imports.standalone.summary_time": "检查结束,总耗时: {:.2f} 秒",
    "imports.standalone.summary_modules": "检查到共 {} 个独立模块",
    "imports.standalone.summary_failed": "发现 {} 个模块载入失败",
    "imports.standalone.summary_success": "所有模块载入成功 ✓",
    "imports.standalone.start_check": "开始检查: {}",
    "imports.standalone.pythonpath": "PYTHONPATH: {}",
    "imports.standalone.exclude_dirs": "排除目录: {}",
    "imports.standalone.exclude_files": "排除文件: {}",
    "imports.standalone.mode": "使用 subprocess 并行检查（真正执行 import）",
    "imports.standalone.found_modules": "找到 {} 个独立模块,开始检查...",
    "imports.standalone.run_dynamic": "执行动态 import 检查: {}",
    # Import error messages
    "imports.error.find_spec_failed": "find_spec 失败: {}",
    "imports.error.module_not_found": "静态分析找不到模块: {}",
    "imports.error.invalid_module_name": "Invalid module name: {}",
    "imports.error.import_timeout": "Import timeout ({}s)",
    "imports.error.failed_to_execute": "Failed to execute Python: {}",
    "imports.error.unexpected_error": "Unexpected error: {}",
    # Syntax error messages
    "syntax.error.syntax_error": "SyntaxError: {}",
    "syntax.error.encoding_error": "Encoding Error: {}",
    "syntax.error.file_error": "File Error: {}",
    "syntax.error.unexpected_error": "Unexpected Error: {}",
    "syntax.error.exception": "Exception: {}",
}
