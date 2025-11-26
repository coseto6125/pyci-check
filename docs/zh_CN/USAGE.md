# pyci-check 使用指南

本文件提供 pyci-check 的详細使用方法、进阶选项与设定说明。

## 目录

- [指令参考](#指令参考)
- [CLI 选项](#cli-选项)
- [设定档](#设定档)
- [虛擬环境处理](#虛擬环境处理)
- [Git Hooks](#git-hooks)
- [进阶使用](#进阶使用)
- [效能优化](#效能优化)
- [故障排除](#故障排除)

## 指令参考

### `check [paths...]`

执行所有检查（语法 + import 静态分析）。

```bash
# 检查整个专案
pyci-check check .

# 检查特定目录
pyci-check check src/ tests/

# 检查特定档案
pyci-check check src/main.py

# 混合使用
pyci-check check src/ scripts/deploy.py tests/test_main.py
```

**行为**:
- 不指定路徑时预设检查当前目录（`.`）
- 支援多个路徑参数
- 路徑可以是档案或目录
- 自动递迴搜尋目录中的 `.py` 档案
- 自动排除 `.venv`、`__pycache__` 等目录（根据 ruff 设定）

### `syntax [paths...]`

仅检查 Python 语法，使用 AST 静态分析。

```bash
# 检查语法
pyci-check syntax

# 检查特定目录的语法
pyci-check syntax src/
```

**特點**:
- 快速且完全安全（不执行程式码）
- 使用 Python 內建的 `ast.parse()`
- 并行处理所有档案
- 适合在 pre-commit hook 中使用

### `imports [paths...]`

仅检查 import 依賴。

```bash
# 静态分析（预设，不执行程式码）
pyci-check imports

# 动态执行（会实际载入模组）
pyci-check imports --i-understand-this-will-execute-code

# 检查特定目录的 imports
pyci-check imports src/
```

**兩種模式**:

1. **静态分析模式**（预设）:
   - 使用 `importlib.util.find_spec()` 检查模组是否存在
   - 不执行程式码，完全安全
   - 可能无法侦测运行时错误（如环境变数缺失）

2. **动态执行模式**（需加 `--i-understand-this-will-execute-code`）:
   - 实际载入并执行所有模组
   - 能侦测运行时错误
   - ⚠️ 会触发副作用（档案寫入、网路请求等）

### `install-hooks`

安裝 Git hooks（使用追加模式，不会覆盖现有 hooks）。

```bash
# 安裝 pre-commit hook（预设）
pyci-check install-hooks

# 安裝 pre-push hook
pyci-check install-hooks --type pre-push
```

**追加模式说明**:
- 使用 `# >>> pyci-check start >>>` 和 `# <<< pyci-check end <<<` 标记
- 如果 hook 档案已存在，会追加 pyci-check 的区块
- 保留所有其他內容（如 black、mypy、ruff 等）
- 如果已有 pyci-check 区块，会更新该区块（不重复添加）

### `uninstall-hooks`

移除 pyci-check 的 Git hooks（保留其他 hooks）。

```bash
# 移除所有 pyci-check 的 hooks
pyci-check uninstall-hooks
```

**行为**:
- 仅移除 `# >>> pyci-check start >>>` 和 `# <<< pyci-check end <<<` 之间的內容
- 保留所有其他 hooks（black、mypy 等）
- 如果移除后只剩 shebang 和 `set -e`，会刪除整个 hook 档案
- 如果 hook 不是由 pyci-check 产生，会跳过并显示警告

## CLI 选项

### 全域选项

这些选项可用于所有指令：

#### `--quiet`

減少輸出讯息，仅显示错误。

```bash
pyci-check check . --quiet
```

#### `--fail-fast`

发现第一个错误时立即停止检查。

```bash
pyci-check check . --fail-fast
```

**适用場景**:
- 快速发现问题
- CI/CD 中节省时间
- Git hooks 中快速失敗

#### `--timeout SECONDS`

设定 import 检查的超时秒数（预设：30）。

```bash
pyci-check imports --timeout 60
```

**注意**:
- 仅适用于动态 import 检查
- 超时会视为检查失敗

#### `--check-relative`

禁止相对导入，发现时视为错误。

```bash
pyci-check check . --check-relative
```

**范例错误**:
```python
# 会被标记为错误
from . import module
from .. import parent_module
from .submodule import function
```

#### `--venv PATH`

指定虛擬环境路徑。

```bash
# 使用当前目录的 .venv
pyci-check imports --venv .

# 使用指定专案的 .venv
pyci-check imports --venv /path/to/project

# 使用 venv/ 目录
pyci-check imports --venv venv
```

**行为**:
- `.` - 使用当前目录的 `.venv/`
- `/path/to/project` - 使用指定专案的 `.venv/`
- `venv` - 使用 `venv/` 目录

#### `--i-understand-this-will-execute-code`

执行动态 import 检查（会实际载入模组）。

```bash
pyci-check imports --i-understand-this-will-execute-code
pyci-check check . --i-understand-this-will-execute-code
```

**安全提醒**:
- ⚠️ 会载入并执行所有模组层级的程式码
- ⚠️ 可能触发副作用（档案寫入、网路请求、系统变更等）
- ⚠️ 会消耗系统资源
- ✅ 仅在受信任的专案中使用

## 设定档

pyci-check 从 `pyproject.toml` 读取设定。

### 基本设定

```toml
[tool.pyci-check]
# 语言设定（预设: en）
# 支援: "en" (英文) | "zh_CN" (簡體中文) | "zh_TW" (繁體中文)
language = "zh_TW"

# Import 检查超时（秒，预设: 30）
import-timeout = 30
```

### 虛擬环境设定

```toml
[tool.pyci-check]
# 虛擬环境路徑（可选）
venv = "."  # 使用当前目录的 .venv（推薦，适合 uv）
```

**优先顺序**（由高至低）:
1. CLI 参数 `--venv`
2. `pyproject.toml` 中的 `venv` 设定
3. 自动侦测：若专案根目录有 `.venv/` 則使用
4. 当前 Python 环境（`sys.executable`）

### 自动整合 ruff 设定

pyci-check 会自动读取 `[tool.ruff]` 的设定：

```toml
[tool.ruff]
# src 目录会自动加入 PYTHONPATH
src = ["src", "tests"]

# 排除目录和档案（pyci-check 会自动读取）
exclude = [".venv", "build", "dist"]
extend-exclude = ["experiments/", "*.egg-info"]
```

**读取行为**:
- `exclude` 和 `extend-exclude` 会自动合併
- 支援目录（如 `.venv`）和档案模式（如 `*.egg-info`）
- `src` 目录会自动加入 `PYTHONPATH`

## 虛擬环境处理

### 自动侦测

pyci-check 会按照以下优先顺序侦测虛擬环境：

1. **CLI 参数**: `--venv .`
2. **设定档**: `[tool.pyci-check] venv = "."`
3. **自动侦测**: 专案根目录的 `.venv/`
4. **当前环境**: `sys.executable`

### 使用 uv 虛擬环境

```bash
# 建议在 pyproject.toml 中设定
[tool.pyci-check]
venv = "."
```

或使用 CLI 参数：

```bash
pyci-check imports --venv .
```

## Git Hooks

### Pre-commit Hook

**行为**:
- 仅检查 **staged** 的 `.py` 档案
- 执行语法检查（快速且安全）
- 发现错误时阻止 commit
- 快速失敗（fail-fast）

**安裝**:
```bash
pyci-check install-hooks
```

### 与其他 Hooks 共存

pyci-check 使用追加模式，可与其他工具的 hooks 共存：

**范例**: 同时使用 black、mypy、pyci-check

```bash
#!/usr/bin/env bash
set -e

# black 的 hook
black --check .

# mypy 的 hook
mypy .

# >>> pyci-check start >>>
# pyci-check 的 hook
PY_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
if [ -n "$PY_FILES" ]; then
    pyci-check syntax $PY_FILES
fi
# <<< pyci-check end <<<
```

**更新/移除**:
- 更新：再次执行 `install-hooks` 会更新 pyci-check 区块
- 移除：`uninstall-hooks` 仅移除 pyci-check 区块，保留其他內容

## 进阶使用

### CI/CD 整合

#### GitHub Actions

```yaml
name: Python Checks

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install pyci-check
        run: pip install pyci-check

      - name: Check syntax
        run: pyci-check syntax

      - name: Check imports
        run: pyci-check imports --i-understand-this-will-execute-code
```

### 与其他工具整合

#### 配合 ruff

```bash
# 建议的检查顺序
pyci-check check .      # 语法 + import 检查
ruff check --fix        # Lint + 自动修復
ruff format             # 格式化
```

## 效能优化

### 核心优化技術

pyci-check 使用多種优化技術以达到最佳效能：

1. **仅读取一次档案**: 使用 `ast.parse()` 取代 `py_compile.compile()`（2x 提升）
2. **集合查找**: 使用 `frozenset` 进行 O(1) 查找，取代 O(n×m) 字串比对（10-20x 提升）
3. **快取配置**: 使用 `@lru_cache` 避免重复读取 `pyproject.toml`
4. **并行处理**: 使用 `ThreadPoolExecutor`，自动计算最佳 worker 数量（CPU 核心数 × 2，上限 32）
5. **Git hook 模式**: 仅检查 staged/changed 档案

## 故障排除

### 常見问题

#### 1. Import 检查失敗但模组确实存在

**原因**: 虛擬环境路徑不正确

**解決方法**:
```bash
# 指定正确的虛擬环境
pyci-check imports --venv .

# 或在 pyproject.toml 中设定
[tool.pyci-check]
venv = "."
```

#### 2. Hook 安裝后沒有生效

**原因**: Hook 档案沒有执行權限

**解決方法**:
```bash
# pyci-check 会自动设定执行權限，但如果沒有：
chmod +x .git/hooks/pre-commit
```

## 退出码

- `0`: 所有检查通过
- `1`: 发现错误（阻止 commit/push）

## 另見

- [README.md](../../README.md) - 专案簡介与快速开始
- [VALIDATION.md](VALIDATION.md) - 检查项目详述与范例
