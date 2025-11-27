# pyci-check

> **語言**: [English](README.md) | [繁體中文](#繁體中文) | [简体中文](README.zh-CN.md)

---

快速的 Python 語法與 import 檢查工具，專為 CI/CD 與 Git hooks 設計。

## 特色

- ⚡ **高效能並行處理** - 使用 ThreadPoolExecutor 並行檢查
- 🔍 **雙層檢查機制**:
  - **語法檢查** - AST 靜態分析，快速且完全安全
  - **Import 檢查** - 靜態分析或動態執行，可偵測運行時錯誤
- 🎯 **彈性檢查範圍** - 支援檢查整個專案、特定目錄或特定檔案
- 🔧 **自動整合 ruff 設定** - 從 `pyproject.toml` 讀取 exclude 與 src 設定
- 🪝 **Git hooks 支援** - 採用追加模式，不會覆蓋現有 hooks
- 📦 **零外部依賴** - 僅使用 Python 標準庫
- ⚠️ **明確同意機制** - 動態 import 檢查需明確同意才會執行程式碼
- 🌐 **多語言支援** - 支援英文、繁體中文、簡體中文

## 安裝

```bash
pip install pyci-check
```

或使用 uv（推薦）：

```bash
# 首選（會加入 pyproject.toml）
uv add pyci-check

# 或直接安裝
uv pip install pyci-check
```

## 快速開始

### 基本用法

```bash
# 檢查整個專案（語法 + import 靜態分析）
pyci-check check

# 僅檢查語法
pyci-check syntax

# 檢查 import（靜態分析，安全）
pyci-check imports

# 檢查 import（動態執行，會實際載入模組）
pyci-check imports --i-understand-this-will-execute-code
```

### 檢查特定檔案或目錄

```bash
# 檢查特定檔案
pyci-check check src/main.py tests/test_main.py

# 檢查特定目錄
pyci-check check src/ tests/

# 混合使用
pyci-check check src/ scripts/deploy.py
```

### Git Hooks 整合

```bash
# 安裝 pre-commit hook（預設）
pyci-check install-hooks

# 安裝 pre-push hook
pyci-check install-hooks --type pre-push

# 移除 pyci-check 的 hooks（保留其他 hooks）
pyci-check uninstall-hooks
```

**注意**: `install-hooks` 採用追加模式，不會覆蓋你現有的 hooks（如 black、mypy 等）。

## 主要指令

- `check [paths...]` - 執行所有檢查（語法 + import 靜態分析）
- `syntax [paths...]` - 僅檢查 Python 語法
- `imports [paths...]` - 僅檢查 import 依賴
- `install-hooks` - 安裝 Git hooks（追加模式）
- `uninstall-hooks` - 移除 pyci-check 的 Git hooks

## 常用選項

- `--quiet` - 減少輸出訊息
- `--fail-fast` - 發現錯誤時立即停止
- `--timeout SECONDS` - Import 檢查超時秒數（預設：30）
- `--check-relative` - 禁止相對導入（發現時視為錯誤）
- `--venv PATH` - 指定虛擬環境路徑
- `--i-understand-this-will-execute-code` - 執行動態 import 檢查（會載入模組）

### 進階範例

```bash
# 檢查相對導入
pyci-check check --check-relative

# 發現錯誤立即停止
pyci-check check --fail-fast

# 設定 import 超時（秒）
pyci-check imports --timeout 60

# 使用指定虛擬環境（支援 uv .venv）
pyci-check imports --venv .
pyci-check imports --venv /path/to/project

# 安靜模式執行完整檢查
pyci-check check --quiet --i-understand-this-will-execute-code
```

## 重要安全提醒

**動態 import 檢查會實際執行程式碼**:
- ⚠️ 會載入並執行所有模組層級的程式碼
- ⚠️ 可能觸發副作用（寫入檔案、網路請求等）
- ⚠️ 會消耗系統資源
- ✅ 能準確偵測運行時錯誤（環境變數缺失、相依性問題等）

**預設為靜態分析**:
- `pyci-check imports` - 使用靜態分析，不執行程式碼（安全）
- `pyci-check imports --i-understand-this-will-execute-code` - 動態執行（需明確同意）

**Git hooks 行為**:
- pre-commit: 僅檢查語法（快速且安全）
- pre-push: 可選擇性加入動態 import 檢查

## 設定檔

在 `pyproject.toml` 中設定：

```toml
[tool.pyci-check]
# 語言設定（預設: en）
language = "zh_TW"  # 或 "en", "zh_CN"

# 虛擬環境路徑（可選）
# venv = "."  # 使用當前目錄的 .venv（推薦，適合 uv）

# Import 檢查超時（秒，預設: 30）
import-timeout = 30
```

**自動整合 ruff 設定**:

pyci-check 會自動讀取 `[tool.ruff]` 的 `exclude`、`extend-exclude` 和 `src` 設定，建議排除規則統一在 ruff 中管理：

```toml
[tool.ruff]
# src 目錄會自動加入 PYTHONPATH
src = ["src", "tests"]

# 排除目錄和檔案（pyci-check 會自動讀取）
exclude = [".venv", "build", "dist"]
extend-exclude = ["experiments/", "*.egg-info"]
```

## CI/CD 整合

### GitHub Actions 範例

```yaml
- name: 檢查 Python 語法與 import
  run: |
    pip install pyci-check
    pyci-check check .  # 語法 + import 靜態分析
```

### 配合 ruff 使用

```bash
# 建議的檢查順序
pyci-check check .      # 語法 + import 檢查
ruff check --fix        # Lint + 自動修復
ruff format             # 格式化
```

## 詳細文件

- **[USAGE.md](docs/zh_TW/USAGE.md)** - 詳細使用方法、進階選項、設定說明
- **[VALIDATION.md](docs/zh_TW/VALIDATION.md)** - 檢查項目詳述與範例

## 授權

MIT License
