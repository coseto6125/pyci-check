# 參與貢獻 pyci-check

> **語言**: [English](../../CONTRIBUTING.md) | [繁體中文](#繁體中文) | [简体中文](../zh_CN/CONTRIBUTING.md)

---

感謝你有興趣為 pyci-check 做出貢獻！本文件提供專案貢獻指南。

## 行為準則

參與本專案時，請維護尊重和包容的環境。

## 如何貢獻

### 回報錯誤

如果發現錯誤，請建立 issue 並包含：
- 清楚的問題描述
- 重現步驟
- 預期與實際行為
- 你的環境（作業系統、Python 版本）
- 最小化的程式碼範例（如適用）

### 建議改進

我們歡迎功能請求！請建立 issue 並包含：
- 清楚的功能描述
- 使用場景和好處
- 可能的實作方式（可選）

### Pull Requests

1. **Fork 倉庫**
   ```bash
   gh repo fork coseto6125/pyci-check --clone
   ```

2. **建立功能分支**
   ```bash
   git checkout -b feature/你的功能名稱
   # 或
   git checkout -b fix/你的錯誤修復
   ```

3. **進行變更**
   - 撰寫清楚、易讀的程式碼
   - 遵循現有的程式碼風格
   - 為新功能添加測試
   - 視需要更新文件

4. **執行測試**
   ```bash
   # 執行所有測試
   pytest
   
   # 執行特定測試類別
   pytest tests/test_syntax.py
   pytest tests/test_imports.py
   
   # 執行含覆蓋率的測試
   pytest --cov=pyci_check
   ```

5. **執行程式碼品質檢查**
   ```bash
   # 語法和 import 檢查
   pyci-check check .
   
   # Linting
   ruff check .
   
   # 格式化
   ruff format .
   ```

6. **提交變更**
   ```bash
   git add .
   git commit -m "feat: 新增功能"
   # 或
   git commit -m "fix: 修復 X 的問題"
   ```

   **Commit 訊息格式**:
   - `feat:` - 新功能
   - `fix:` - 錯誤修復
   - `docs:` - 文件變更
   - `test:` - 測試變更
   - `refactor:` - 程式碼重構
   - `chore:` - 維護任務

7. **推送並建立 PR**
   ```bash
   git push origin feature/你的功能名稱
   gh pr create --fill
   ```

## 開發環境設定

### 前置需求

- Python 3.11, 3.12, 或 3.13
- Git

### 安裝

1. **Clone 倉庫**
   ```bash
   git clone https://github.com/coseto6125/pyci-check.git
   cd pyci-check
   ```

2. **建立虛擬環境**
   ```bash
   # 使用 uv（推薦）
   uv venv
   source .venv/bin/activate  # Linux/macOS
   # 或
   .venv\Scripts\activate  # Windows
   
   # 或使用標準 venv
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **以開發模式安裝**
   ```bash
   # 使用 uv（推薦）
   uv pip install -e ".[dev]"

   # 或使用 pip
   pip install -e ".[dev]"
   ```

### 執行測試

```bash
# 所有測試
pytest

# 特定測試檔案
pytest tests/test_syntax.py

# 含覆蓋率報告
pytest --cov=pyci_check --cov-report=html

# Watch 模式（需要 pytest-watch）
ptw
```

### 程式碼風格

我們使用：
- **ruff** 進行 linting 和格式化
- **pyci-check** 進行語法和 import 驗證
- **pytest** 進行測試

提交 PR 前，請確保：
```bash
pyci-check check .
ruff check .
ruff format .
pytest
```

## 專案結構

```
pyci-check/
├── src/pyci_check/     # 主要原始碼
│   ├── cli.py          # CLI 介面
│   ├── syntax.py       # 語法檢查
│   ├── imports.py      # Import 檢查
│   ├── git_hook.py     # Git hooks 功能
│   ├── i18n.py         # 國際化
│   └── locales/        # 語言檔案
├── tests/              # 測試套件
├── docs/               # 文件
│   ├── en/            # 英文文件
│   ├── zh_TW/         # 繁體中文文件
│   └── zh_CN/         # 簡體中文文件
└── scripts/           # 輔助腳本
```

## 文件

新增功能時：
- 更新 `docs/` 中的相關文件
- 為函式和類別添加 docstrings
- 更新 `CHANGELOG.md`
- 考慮在 README 中添加範例

## 發布流程

發布透過 GitHub Actions 自動化。僅維護者可建立發布：

1. 在 `pyproject.toml` 中更新版本
2. 更新 `CHANGELOG.md`
3. 建立並推送 tag：`git tag -a v0.x.0 -m "Release v0.x.0"`
4. 推送 tag：`git push origin v0.x.0`
5. GitHub Actions 會自動建置並發布到 PyPI

## 有問題？

如果有問題，歡迎：
- 開啟 issue 討論
- 查看現有的 issues 和 PRs
- 閱讀 `docs/` 中的文件

感謝你的貢獻！🎉
