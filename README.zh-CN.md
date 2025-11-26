# pyci-check

> **语言**: [English](README.md) | [繁體中文](#繁體中文) | [简体中文](README.zh-CN.md)

---

快速的 Python 语法与 import 检查工具，专为 CI/CD 与 Git hooks 设计。

## 特色

- ⚡ **高效能并行处理** - 使用 ThreadPoolExecutor 并行检查
- 🔍 **雙层检查机制**:
  - **语法检查** - AST 静态分析，快速且完全安全
  - **Import 检查** - 静态分析或动态执行，可侦测运行时错误
- 🎯 **弹性检查范围** - 支援检查整个专案、特定目录或特定档案
- 🔧 **自动整合 ruff 设定** - 从 `pyproject.toml` 读取 exclude 与 src 设定
- 🪝 **Git hooks 支援** - 採用追加模式，不会覆盖现有 hooks
- 📦 **零外部依赖** - 仅使用 Python 标准庫
- ⚠️ **明确同意机制** - 动态 import 检查需明确同意才会执行程式码
- 🌐 **多语言支援** - 支援英文、繁體中文、簡體中文

## 安裝

```bash
pip install pyci-check
```

或使用 uv（推薦）：

```bash
uv pip install pyci-check
```

或：

```bash
uv add pyci-check
```

## 快速开始

### 基本用法

```bash
# 检查整个专案（语法 + import 静态分析）
pyci-check check .

# 仅检查语法
pyci-check syntax

# 检查 import（静态分析，安全）
pyci-check imports

# 检查 import（动态执行，会实际载入模组）
pyci-check imports --i-understand-this-will-execute-code
```

### 检查特定档案或目录

```bash
# 检查特定档案
pyci-check check src/main.py tests/test_main.py

# 检查特定目录
pyci-check check src/ tests/

# 混合使用
pyci-check check src/ scripts/deploy.py
```

### Git Hooks 整合

```bash
# 安裝 pre-commit hook（预设）
pyci-check install-hooks

# 安裝 pre-push hook
pyci-check install-hooks --type pre-push

# 移除 pyci-check 的 hooks（保留其他 hooks）
pyci-check uninstall-hooks
```

**注意**: `install-hooks` 採用追加模式，不会覆盖你现有的 hooks（如 black、mypy 等）。

## 主要指令

- `check [paths...]` - 执行所有检查（语法 + import 静态分析）
- `syntax [paths...]` - 仅检查 Python 语法
- `imports [paths...]` - 仅检查 import 依赖
- `install-hooks` - 安裝 Git hooks（追加模式）
- `uninstall-hooks` - 移除 pyci-check 的 Git hooks

## 常用选项

- `--quiet` - 減少輸出讯息
- `--fail-fast` - 发现错误时立即停止
- `--timeout SECONDS` - Import 检查超时秒数（预设：30）
- `--check-relative` - 禁止相对导入（发现时视为错误）
- `--venv PATH` - 指定虛擬环境路徑
- `--i-understand-this-will-execute-code` - 执行动态 import 检查（会载入模组）

### 进阶范例

```bash
# 检查相对导入
pyci-check check . --check-relative

# 发现错误立即停止
pyci-check check . --fail-fast

# 设定 import 超时（秒）
pyci-check imports --timeout 60

# 使用指定虛擬环境（支援 uv .venv）
pyci-check imports --venv .
pyci-check imports --venv /path/to/project

# 安静模式执行完整检查
pyci-check check . --quiet --i-understand-this-will-execute-code
```

## 重要安全提醒

**动态 import 检查会实际执行程式码**:
- ⚠️ 会载入并执行所有模组层级的程式码
- ⚠️ 可能触发副作用（寫入档案、网路请求等）
- ⚠️ 会消耗系统资源
- ✅ 能准确侦测运行时错误（环境变数缺失、相依性问题等）

**预设为静态分析**:
- `pyci-check imports` - 使用静态分析，不执行程式码（安全）
- `pyci-check imports --i-understand-this-will-execute-code` - 动态执行（需明确同意）

**Git hooks 行为**:
- pre-commit: 仅检查语法（快速且安全）
- pre-push: 可选择性加入动态 import 检查

## 设定档

在 `pyproject.toml` 中设定：

```toml
[tool.pyci-check]
# 语言设定（预设: en）
language = "zh_TW"  # 或 "en", "zh_CN"

# 虛擬环境路徑（可选）
# venv = "."  # 使用当前目录的 .venv（推薦，适合 uv）

# Import 检查超时（秒，预设: 30）
import-timeout = 30
```

**自动整合 ruff 设定**:

pyci-check 会自动读取 `[tool.ruff]` 的 `exclude`、`extend-exclude` 和 `src` 设定，建议排除規則统一在 ruff 中管理：

```toml
[tool.ruff]
# src 目录会自动加入 PYTHONPATH
src = ["src", "tests"]

# 排除目录和档案（pyci-check 会自动读取）
exclude = [".venv", "build", "dist"]
extend-exclude = ["experiments/", "*.egg-info"]
```

## CI/CD 整合

### GitHub Actions 范例

```yaml
- name: 检查 Python 语法与 import
  run: |
    pip install pyci-check
    pyci-check check .  # 语法 + import 静态分析
```

### 配合 ruff 使用

```bash
# 建议的检查顺序
pyci-check check .      # 语法 + import 检查
ruff check --fix        # Lint + 自动修復
ruff format             # 格式化
```

## 详細文件

- **[USAGE.md](docs/zh_TW/USAGE.md)** - 详細使用方法、进阶选项、设定说明
- **[VALIDATION.md](docs/zh_TW/VALIDATION.md)** - 检查项目详述与范例

## 授权

MIT License
