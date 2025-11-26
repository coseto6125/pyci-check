# pyci-check 使用指南

本文件提供 pyci-check 的詳細使用方法、進階選項與設定說明。

## 目錄

- [指令參考](#指令參考)
- [CLI 選項](#cli-選項)
- [設定檔](#設定檔)
- [虛擬環境處理](#虛擬環境處理)
- [Git Hooks](#git-hooks)
- [進階使用](#進階使用)
- [效能優化](#效能優化)
- [故障排除](#故障排除)

## 指令參考

### `check [paths...]`

執行所有檢查（語法 + import 靜態分析）。

```bash
# 檢查整個專案
pyci-check check .

# 檢查特定目錄
pyci-check check src/ tests/

# 檢查特定檔案
pyci-check check src/main.py

# 混合使用
pyci-check check src/ scripts/deploy.py tests/test_main.py
```

**行為**:
- 不指定路徑時預設檢查當前目錄（`.`）
- 支援多個路徑參數
- 路徑可以是檔案或目錄
- 自動遞迴搜尋目錄中的 `.py` 檔案
- 自動排除 `.venv`、`__pycache__` 等目錄（根據 ruff 設定）

### `syntax [paths...]`

僅檢查 Python 語法，使用 AST 靜態分析。

```bash
# 檢查語法
pyci-check syntax

# 檢查特定目錄的語法
pyci-check syntax src/
```

**特點**:
- 快速且完全安全（不執行程式碼）
- 使用 Python 內建的 `ast.parse()`
- 並行處理所有檔案
- 適合在 pre-commit hook 中使用

### `imports [paths...]`

僅檢查 import 依賴。

```bash
# 靜態分析（預設，不執行程式碼）
pyci-check imports

# 動態執行（會實際載入模組）
pyci-check imports --i-understand-this-will-execute-code

# 檢查特定目錄的 imports
pyci-check imports src/
```

**兩種模式**:

1. **靜態分析模式**（預設）:
   - 使用 `importlib.util.find_spec()` 檢查模組是否存在
   - 不執行程式碼，完全安全
   - 可能無法偵測運行時錯誤（如環境變數缺失）

2. **動態執行模式**（需加 `--i-understand-this-will-execute-code`）:
   - 實際載入並執行所有模組
   - 能偵測運行時錯誤
   - ⚠️ 會觸發副作用（檔案寫入、網路請求等）

### `install-hooks`

安裝 Git hooks（使用追加模式，不會覆蓋現有 hooks）。

```bash
# 安裝 pre-commit hook（預設）
pyci-check install-hooks

# 安裝 pre-push hook
pyci-check install-hooks --type pre-push
```

**追加模式說明**:
- 使用 `# >>> pyci-check start >>>` 和 `# <<< pyci-check end <<<` 標記
- 如果 hook 檔案已存在，會追加 pyci-check 的區塊
- 保留所有其他內容（如 black、mypy、ruff 等）
- 如果已有 pyci-check 區塊，會更新該區塊（不重複添加）

### `uninstall-hooks`

移除 pyci-check 的 Git hooks（保留其他 hooks）。

```bash
# 移除所有 pyci-check 的 hooks
pyci-check uninstall-hooks
```

**行為**:
- 僅移除 `# >>> pyci-check start >>>` 和 `# <<< pyci-check end <<<` 之間的內容
- 保留所有其他 hooks（black、mypy 等）
- 如果移除後只剩 shebang 和 `set -e`，會刪除整個 hook 檔案
- 如果 hook 不是由 pyci-check 產生，會跳過並顯示警告

## CLI 選項

### 全域選項

這些選項可用於所有指令：

#### `--quiet`

減少輸出訊息，僅顯示錯誤。

```bash
pyci-check check . --quiet
```

#### `--fail-fast`

發現第一個錯誤時立即停止檢查。

```bash
pyci-check check . --fail-fast
```

**適用場景**:
- 快速發現問題
- CI/CD 中節省時間
- Git hooks 中快速失敗

#### `--timeout SECONDS`

設定 import 檢查的超時秒數（預設：30）。

```bash
pyci-check imports --timeout 60
```

**注意**:
- 僅適用於動態 import 檢查
- 超時會視為檢查失敗

#### `--check-relative`

禁止相對導入，發現時視為錯誤。

```bash
pyci-check check . --check-relative
```

**範例錯誤**:
```python
# 會被標記為錯誤
from . import module
from .. import parent_module
from .submodule import function
```

#### `--venv PATH`

指定虛擬環境路徑。

```bash
# 使用當前目錄的 .venv
pyci-check imports --venv .

# 使用指定專案的 .venv
pyci-check imports --venv /path/to/project

# 使用 venv/ 目錄
pyci-check imports --venv venv
```

**行為**:
- `.` - 使用當前目錄的 `.venv/`
- `/path/to/project` - 使用指定專案的 `.venv/`
- `venv` - 使用 `venv/` 目錄

#### `--i-understand-this-will-execute-code`

執行動態 import 檢查（會實際載入模組）。

```bash
pyci-check imports --i-understand-this-will-execute-code
pyci-check check . --i-understand-this-will-execute-code
```

**安全提醒**:
- ⚠️ 會載入並執行所有模組層級的程式碼
- ⚠️ 可能觸發副作用（檔案寫入、網路請求、系統變更等）
- ⚠️ 會消耗系統資源
- ✅ 僅在受信任的專案中使用

## 設定檔

pyci-check 從 `pyproject.toml` 讀取設定。

### 基本設定

```toml
[tool.pyci-check]
# 語言設定（預設: en）
# 支援: "en" (英文) | "zh_CN" (簡體中文) | "zh_TW" (繁體中文)
language = "zh_TW"

# Import 檢查超時（秒，預設: 30）
import-timeout = 30
```

### 虛擬環境設定

```toml
[tool.pyci-check]
# 虛擬環境路徑（可選）
venv = "."  # 使用當前目錄的 .venv（推薦，適合 uv）
```

**優先順序**（由高至低）:
1. CLI 參數 `--venv`
2. `pyproject.toml` 中的 `venv` 設定
3. 自動偵測：若專案根目錄有 `.venv/` 則使用
4. 當前 Python 環境（`sys.executable`）

### 自動整合 ruff 設定

pyci-check 會自動讀取 `[tool.ruff]` 的設定：

```toml
[tool.ruff]
# src 目錄會自動加入 PYTHONPATH
src = ["src", "tests"]

# 排除目錄和檔案（pyci-check 會自動讀取）
exclude = [".venv", "build", "dist"]
extend-exclude = ["experiments/", "*.egg-info"]
```

**讀取行為**:
- `exclude` 和 `extend-exclude` 會自動合併
- 支援目錄（如 `.venv`）和檔案模式（如 `*.egg-info`）
- `src` 目錄會自動加入 `PYTHONPATH`

## 虛擬環境處理

### 自動偵測

pyci-check 會按照以下優先順序偵測虛擬環境：

1. **CLI 參數**: `--venv .`
2. **設定檔**: `[tool.pyci-check] venv = "."`
3. **自動偵測**: 專案根目錄的 `.venv/`
4. **當前環境**: `sys.executable`

### 使用 uv 虛擬環境

```bash
# 建議在 pyproject.toml 中設定
[tool.pyci-check]
venv = "."
```

或使用 CLI 參數：

```bash
pyci-check imports --venv .
```

## Git Hooks

### Pre-commit Hook

**行為**:
- 僅檢查 **staged** 的 `.py` 檔案
- 執行語法檢查（快速且安全）
- 發現錯誤時阻止 commit
- 快速失敗（fail-fast）

**安裝**:
```bash
pyci-check install-hooks
```

### 與其他 Hooks 共存

pyci-check 使用追加模式，可與其他工具的 hooks 共存：

**範例**: 同時使用 black、mypy、pyci-check

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
- 更新：再次執行 `install-hooks` 會更新 pyci-check 區塊
- 移除：`uninstall-hooks` 僅移除 pyci-check 區塊，保留其他內容

## 進階使用

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

### 與其他工具整合

#### 配合 ruff

```bash
# 建議的檢查順序
pyci-check check .      # 語法 + import 檢查
ruff check --fix        # Lint + 自動修復
ruff format             # 格式化
```

## 效能優化

### 核心優化技術

pyci-check 使用多種優化技術以達到最佳效能：

1. **僅讀取一次檔案**: 使用 `ast.parse()` 取代 `py_compile.compile()`（2x 提升）
2. **集合查找**: 使用 `frozenset` 進行 O(1) 查找，取代 O(n×m) 字串比對（10-20x 提升）
3. **快取配置**: 使用 `@lru_cache` 避免重複讀取 `pyproject.toml`
4. **並行處理**: 使用 `ThreadPoolExecutor`，自動計算最佳 worker 數量（CPU 核心數 × 2，上限 32）
5. **Git hook 模式**: 僅檢查 staged/changed 檔案

## 故障排除

### 常見問題

#### 1. Import 檢查失敗但模組確實存在

**原因**: 虛擬環境路徑不正確

**解決方法**:
```bash
# 指定正確的虛擬環境
pyci-check imports --venv .

# 或在 pyproject.toml 中設定
[tool.pyci-check]
venv = "."
```

#### 2. Hook 安裝後沒有生效

**原因**: Hook 檔案沒有執行權限

**解決方法**:
```bash
# pyci-check 會自動設定執行權限，但如果沒有：
chmod +x .git/hooks/pre-commit
```

## 退出碼

- `0`: 所有檢查通過
- `1`: 發現錯誤（阻止 commit/push）

## 另見

- [README.md](../../README.md) - 專案簡介與快速開始
- [VALIDATION.md](VALIDATION.md) - 檢查項目詳述與範例
