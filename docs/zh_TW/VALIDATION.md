# pyci-check 檢查項目詳述

本文件詳細說明 pyci-check 會檢查哪些項目，以及各種錯誤的範例。

## 目錄

- [語法檢查](#語法檢查)
- [Import 檢查](#import-檢查)
- [相對導入檢查](#相對導入檢查)
- [錯誤訊息格式](#錯誤訊息格式)

## 語法檢查

語法檢查使用 Python 內建的 AST（抽象語法樹）解析器，能夠偵測所有 Python 語法錯誤。

### 檢查方式

```python
import ast

with open(file_path, encoding="utf-8") as f:
    source = f.read()
    ast.parse(source, filename=file_path)
```

### 常見語法錯誤

#### 1. 縮排錯誤

```python
# ❌ 錯誤：縮排不一致
def hello():
    print("Hello")
      print("World")  # 縮排過多
```

**錯誤訊息**:
```
src/example.py: unexpected indent (example.py, line 3)
```

#### 2. 未閉合的括號

```python
# ❌ 錯誤：缺少右括號
result = calculate(
    a, b, c
# 缺少 )
```

**錯誤訊息**:
```
src/example.py: '(' was never closed (example.py, line 2)
```

#### 3. 無效的語法

```python
# ❌ 錯誤：print 語句（Python 2 語法）
print "Hello"

# ❌ 錯誤：缺少冒號
def hello()
    pass

# ❌ 錯誤：非法的變數名稱
1st_variable = 10
```

**錯誤訊息**:
```
src/example.py: Missing parentheses in call to 'print'
src/example.py: invalid syntax
src/example.py: invalid decimal literal
```

#### 4. 字串未閉合

```python
# ❌ 錯誤：缺少結束引號
message = "Hello World
print(message)
```

**錯誤訊息**:
```
src/example.py: unterminated string literal
```

### 語法檢查的特點

- ✅ **快速**: 使用 AST 解析，比實際執行快得多
- ✅ **安全**: 不執行程式碼，無副作用
- ✅ **完整**: 能捕捉所有語法錯誤
- ✅ **並行**: 使用 ThreadPoolExecutor 並行檢查所有檔案
- ✅ **準確**: 顯示精確的檔案路徑、行號和錯誤訊息

### 不檢查的項目

語法檢查**不會**檢查：
- ❌ 邏輯錯誤（如無限迴圈）
- ❌ 類型錯誤（使用 mypy）
- ❌ 風格問題（使用 ruff）
- ❌ 未使用的變數（使用 ruff）
- ❌ Import 錯誤（使用 `pyci-check imports`）

## Import 檢查

Import 檢查驗證所有 import 語句是否正確，模組是否存在且可載入。

### 檢查方式

pyci-check 提供兩種檢查模式：

#### 1. 靜態分析模式（預設）

使用 `importlib.util.find_spec()` 檢查模組是否存在，不執行程式碼。

```bash
pyci-check imports
```

**特點**:
- ✅ 完全安全（不執行程式碼）
- ✅ 快速
- ⚠️ 可能無法偵測運行時錯誤

**檢查邏輯**:
1. 使用 `find_spec()` 檢查模組是否存在
2. 如果找不到，嘗試從檔案系統查找（相對導入）
3. 兩者都失敗則報錯

#### 2. 動態執行模式

實際載入並執行模組，能偵測運行時錯誤。

```bash
pyci-check imports --i-understand-this-will-execute-code
```

**特點**:
- ✅ 能偵測運行時錯誤（環境變數缺失、循環導入等）
- ⚠️ 會執行程式碼（可能有副作用）
- ⚠️ 較慢

### 常見 Import 錯誤

#### 1. 模組不存在

```python
# ❌ 錯誤：模組不存在
import nonexistent_module
from fake_package import something
```

**錯誤訊息（靜態分析）**:
```
src/example.py:1: import nonexistent_module
  模組 'nonexistent_module' 無法導入: No module named 'nonexistent_module'
```

#### 2. 循環導入（僅動態模式可偵測）

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

**錯誤訊息（動態執行模式）**:
```
src/module_a.py:1: from module_b import b_function
  導入失敗: cannot import name 'b_function' from partially initialized module 'module_b'
```

**注意**: 靜態分析模式可能無法偵測此錯誤。

#### 3. 套件未安裝

```python
# ❌ 錯誤：套件未安裝在當前環境
import numpy
import pandas
```

**錯誤訊息**:
```
src/example.py:1: import numpy
  模組 'numpy' 無法導入: No module named 'numpy'
```

**解決方法**:
- 安裝缺失的套件: `pip install numpy`
- 或使用正確的虛擬環境: `pyci-check imports --venv .`

### Import 檢查的特點

#### 靜態分析模式

- ✅ **安全**: 不執行程式碼
- ✅ **快速**: 僅使用 `find_spec()`
- ✅ **適合**: 日常開發、pre-commit hooks
- ⚠️ **限制**: 無法偵測運行時錯誤

#### 動態執行模式

- ✅ **完整**: 能偵測所有 import 錯誤（包含運行時）
- ✅ **準確**: 實際載入模組
- ✅ **適合**: CI/CD、發布前檢查
- ⚠️ **副作用**: 會執行模組層級的程式碼
- ⚠️ **較慢**: 需要實際載入所有模組

## 相對導入檢查

當使用 `--check-relative` 選項時，pyci-check 會禁止相對導入。

### 啟用方式

```bash
pyci-check check --check-relative
```

或在 `pyproject.toml` 中設定：

```toml
[tool.pyci-check]
allow-relative-imports = false
```

### 相對導入範例

#### ❌ 禁止的相對導入

```python
# 從當前 package 導入
from . import module
from .module import function
from . import *

# 從父 package 導入
from .. import parent_module
from ..parent import function
```

**錯誤訊息**:
```
src/package/module.py:1: from . import module
  發現相對導入（已設定禁止相對導入）
```

#### ✅ 允許的絕對導入

```python
# 使用絕對導入
from package import module
from package.module import function
from package.subpackage import something
```

### 為何要禁止相對導入？

**優點**:
- ✅ 路徑清晰明確
- ✅ 重構時更容易
- ✅ 避免混淆
- ✅ 適合大型專案

**缺點**:
- ❌ 路徑較長
- ❌ 需要設定 `PYTHONPATH` 或 `src` 目錄

**建議**:
- 小型專案: 可以使用相對導入
- 大型專案: 建議使用絕對導入
- 函式庫: 建議使用絕對導入

## 錯誤訊息格式

### 語法錯誤

```
<相對路徑>: <錯誤訊息>
```

**範例**:
```
src/example.py: invalid syntax (example.py, line 10)
```

**包含資訊**:
- 檔案相對路徑
- 詳細錯誤訊息
- 原始檔案名稱
- 行號

### Import 錯誤

```
<相對路徑>:<行號>: <import 語句>
  <錯誤原因>
```

**範例（靜態分析）**:
```
src/main.py:5: import nonexistent_module
  模組 'nonexistent_module' 無法導入: No module named 'nonexistent_module'
```

**範例（動態執行）**:
```
src/main.py:5: import broken_module
  導入失敗: division by zero
```

**包含資訊**:
- 檔案相對路徑
- 行號
- 完整的 import 語句
- 詳細錯誤原因

## 檢查總結表格

| 檢查類型 | 指令 | 執行程式碼 | 速度 | 適用場景 |
|---------|------|-----------|------|---------|
| 語法檢查 | `pyci-check syntax` | ❌ 否 | ⚡ 快 | pre-commit, CI/CD |
| Import 靜態 | `pyci-check imports` | ❌ 否 | ⚡ 快 | 日常開發, pre-commit |
| Import 動態 | `pyci-check imports --i-understand-this-will-execute-code` | ✅ 是 | 🐢 慢 | CI/CD, 發布前 |
| 完整檢查（靜態） | `pyci-check check` | ❌ 否 | ⚡ 快 | 日常開發 |
| 完整檢查（動態） | `pyci-check check --i-understand-this-will-execute-code` | ✅ 是 | 🐢 慢 | CI/CD |

## 最佳實踐

### 開發階段

```bash
# 快速檢查（語法 + import 靜態分析）
pyci-check check
```

### Git Hooks

```bash
# pre-commit: 僅語法檢查（最快）
pyci-check syntax

# pre-push: 可加入 import 靜態分析
pyci-check check
```

### CI/CD

```bash
# 完整檢查（包含動態 import）
pyci-check check --i-understand-this-will-execute-code
```

### 發布前

```bash
# 完整檢查 + 其他工具
pyci-check check --i-understand-this-will-execute-code
mypy .
ruff check .
pytest
```

## 另見

- [README.md](../../README.md) - 專案簡介與快速開始
- [USAGE.md](USAGE.md) - 詳細使用方法與設定說明
