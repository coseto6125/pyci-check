# pyci-check 检查项目详述

本文件详細说明 pyci-check 会检查哪些项目，以及各種错误的范例。

## 目录

- [语法检查](#语法检查)
- [Import 检查](#import-检查)
- [相对导入检查](#相对导入检查)
- [错误讯息格式](#错误讯息格式)

## 语法检查

语法检查使用 Python 內建的 AST（抽象语法树）解析器，能夠侦测所有 Python 语法错误。

### 检查方式

```python
import ast

with open(file_path, encoding="utf-8") as f:
    source = f.read()
    ast.parse(source, filename=file_path)
```

### 常見语法错误

#### 1. 缩排错误

```python
# ❌ 错误：缩排不一致
def hello():
    print("Hello")
      print("World")  # 缩排过多
```

**错误讯息**:
```
src/example.py: unexpected indent (example.py, line 3)
```

#### 2. 未闭合的括号

```python
# ❌ 错误：缺少右括号
result = calculate(
    a, b, c
# 缺少 )
```

**错误讯息**:
```
src/example.py: '(' was never closed (example.py, line 2)
```

#### 3. 无效的语法

```python
# ❌ 错误：print 语句（Python 2 语法）
print "Hello"

# ❌ 错误：缺少冒号
def hello()
    pass

# ❌ 错误：非法的变数名稱
1st_variable = 10
```

**错误讯息**:
```
src/example.py: Missing parentheses in call to 'print'
src/example.py: invalid syntax
src/example.py: invalid decimal literal
```

#### 4. 字串未闭合

```python
# ❌ 错误：缺少结束引号
message = "Hello World
print(message)
```

**错误讯息**:
```
src/example.py: unterminated string literal
```

### 语法检查的特點

- ✅ **快速**: 使用 AST 解析，比实际执行快得多
- ✅ **安全**: 不执行程式码，无副作用
- ✅ **完整**: 能捕捉所有语法错误
- ✅ **并行**: 使用 ThreadPoolExecutor 并行检查所有档案
- ✅ **准确**: 显示精确的档案路徑、行号和错误讯息

### 不检查的项目

语法检查**不会**检查：
- ❌ 逻辑错误（如无限迴圈）
- ❌ 类型错误（使用 mypy）
- ❌ 风格问题（使用 ruff）
- ❌ 未使用的变数（使用 ruff）
- ❌ Import 错误（使用 `pyci-check imports`）

## Import 检查

Import 检查验证所有 import 语句是否正确，模组是否存在且可载入。

### 检查方式

pyci-check 提供兩種检查模式：

#### 1. 静态分析模式（预设）

使用 `importlib.util.find_spec()` 检查模组是否存在，不执行程式码。

```bash
pyci-check imports
```

**特點**:
- ✅ 完全安全（不执行程式码）
- ✅ 快速
- ⚠️ 可能无法侦测运行时错误

**检查逻辑**:
1. 使用 `find_spec()` 检查模组是否存在
2. 如果找不到，嘗试从档案系统查找（相对导入）
3. 兩者都失敗則报错

#### 2. 动态执行模式

实际载入并执行模组，能侦测运行时错误。

```bash
pyci-check imports --i-understand-this-will-execute-code
```

**特點**:
- ✅ 能侦测运行时错误（环境变数缺失、循环导入等）
- ⚠️ 会执行程式码（可能有副作用）
- ⚠️ 较慢

### 常見 Import 错误

#### 1. 模组不存在

```python
# ❌ 错误：模组不存在
import nonexistent_module
from fake_package import something
```

**错误讯息（静态分析）**:
```
src/example.py:1: import nonexistent_module
  模组 'nonexistent_module' 无法导入: No module named 'nonexistent_module'
```

#### 2. 循环导入（仅动态模式可侦测）

**module_a.py**:
```python
from module_b import b_function

def a_function():
    return b_function()
```

**module_b.py**:
```python
from module_a import a_function

def b_function():
    return a_function()
```

**错误讯息（动态执行模式）**:
```
src/module_a.py:1: from module_b import b_function
  导入失敗: cannot import name 'b_function' from partially initialized module 'module_b'
```

**注意**: 静态分析模式可能无法侦测此错误。

#### 3. 套件未安裝

```python
# ❌ 错误：套件未安裝在当前环境
import numpy
import pandas
```

**错误讯息**:
```
src/example.py:1: import numpy
  模组 'numpy' 无法导入: No module named 'numpy'
```

**解決方法**:
- 安裝缺失的套件: `pip install numpy`
- 或使用正确的虛擬环境: `pyci-check imports --venv .`

### Import 检查的特點

#### 静态分析模式

- ✅ **安全**: 不执行程式码
- ✅ **快速**: 仅使用 `find_spec()`
- ✅ **适合**: 日常开发、pre-commit hooks
- ⚠️ **限制**: 无法侦测运行时错误

#### 动态执行模式

- ✅ **完整**: 能侦测所有 import 错误（包含运行时）
- ✅ **准确**: 实际载入模组
- ✅ **适合**: CI/CD、发布前检查
- ⚠️ **副作用**: 会执行模组层级的程式码
- ⚠️ **较慢**: 需要实际载入所有模组

## 相对导入检查

当使用 `--check-relative` 选项时，pyci-check 会禁止相对导入。

### 啟用方式

```bash
pyci-check check . --check-relative
```

或在 `pyproject.toml` 中设定：

```toml
[tool.pyci-check]
allow-relative-imports = false
```

### 相对导入范例

#### ❌ 禁止的相对导入

```python
# 从当前 package 导入
from . import module
from .module import function
from . import *

# 从父 package 导入
from .. import parent_module
from ..parent import function
```

**错误讯息**:
```
src/package/module.py:1: from . import module
  发现相对导入（已设定禁止相对导入）
```

#### ✅ 允许的絕对导入

```python
# 使用絕对导入
from package import module
from package.module import function
from package.subpackage import something
```

### 为何要禁止相对导入？

**优點**:
- ✅ 路徑清晰明确
- ✅ 重构时更容易
- ✅ 避免混淆
- ✅ 适合大型专案

**缺點**:
- ❌ 路徑较長
- ❌ 需要设定 `PYTHONPATH` 或 `src` 目录

**建议**:
- 小型专案: 可以使用相对导入
- 大型专案: 建议使用絕对导入
- 函式庫: 建议使用絕对导入

## 错误讯息格式

### 语法错误

```
<相对路徑>: <错误讯息>
```

**范例**:
```
src/example.py: invalid syntax (example.py, line 10)
```

**包含资讯**:
- 档案相对路徑
- 详細错误讯息
- 原始档案名稱
- 行号

### Import 错误

```
<相对路徑>:<行号>: <import 语句>
  <错误原因>
```

**范例（静态分析）**:
```
src/main.py:5: import nonexistent_module
  模组 'nonexistent_module' 无法导入: No module named 'nonexistent_module'
```

**范例（动态执行）**:
```
src/main.py:5: import broken_module
  导入失敗: division by zero
```

**包含资讯**:
- 档案相对路徑
- 行号
- 完整的 import 语句
- 详細错误原因

## 检查总结表格

| 检查类型 | 指令 | 执行程式码 | 速度 | 适用場景 |
|---------|------|-----------|------|---------|
| 语法检查 | `pyci-check syntax` | ❌ 否 | ⚡ 快 | pre-commit, CI/CD |
| Import 静态 | `pyci-check imports` | ❌ 否 | ⚡ 快 | 日常开发, pre-commit |
| Import 动态 | `pyci-check imports --i-understand-this-will-execute-code` | ✅ 是 | 🐢 慢 | CI/CD, 发布前 |
| 完整检查（静态） | `pyci-check check .` | ❌ 否 | ⚡ 快 | 日常开发 |
| 完整检查（动态） | `pyci-check check . --i-understand-this-will-execute-code` | ✅ 是 | 🐢 慢 | CI/CD |

## 最佳实踐

### 开发阶段

```bash
# 快速检查（语法 + import 静态分析）
pyci-check check .
```

### Git Hooks

```bash
# pre-commit: 仅语法检查（最快）
pyci-check syntax

# pre-push: 可加入 import 静态分析
pyci-check check .
```

### CI/CD

```bash
# 完整检查（包含动态 import）
pyci-check check . --i-understand-this-will-execute-code
```

### 发布前

```bash
# 完整检查 + 其他工具
pyci-check check . --i-understand-this-will-execute-code
mypy .
ruff check .
pytest
```

## 另見

- [README.md](../../README.md) - 专案簡介与快速开始
- [USAGE.md](USAGE.md) - 详細使用方法与设定说明
