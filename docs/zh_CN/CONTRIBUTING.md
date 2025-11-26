# 参与貢獻 pyci-check

> **语言**: [English](../../CONTRIBUTING.md) | [繁體中文](#繁體中文) | [简体中文](../zh_CN/CONTRIBUTING.md)

---

感謝你有興趣为 pyci-check 做出貢獻！本文件提供专案貢獻指南。

## 行为准則

参与本专案时，请維护尊重和包容的环境。

## 如何貢獻

### 回报错误

如果发现错误，请建立 issue 并包含：
- 清楚的问题描述
- 重现步驟
- 预期与实际行为
- 你的环境（作業系统、Python 版本）
- 最小化的程式码范例（如适用）

### 建议改进

我們歡迎功能请求！请建立 issue 并包含：
- 清楚的功能描述
- 使用場景和好处
- 可能的实作方式（可选）

### Pull Requests

1. **Fork 倉庫**
   ```bash
   gh repo fork coseto6125/pyci-check --clone
   ```

2. **建立功能分支**
   ```bash
   git checkout -b feature/你的功能名稱
   # 或
   git checkout -b fix/你的错误修復
   ```

3. **进行变更**
   - 撰寫清楚、易读的程式码
   - 遵循现有的程式码风格
   - 为新功能添加测试
   - 视需要更新文件

4. **执行测试**
   ```bash
   # 执行所有测试
   uv run pytest
   
   # 执行特定测试类别
   uv run pytest tests/test_syntax.py
   uv run pytest tests/test_imports.py
   
   # 执行含覆盖率的测试
   uv run pytest --cov=pyci_check
   ```

5. **执行程式码品质检查**
   ```bash
   # 语法和 import 检查
   uv run pyci-check check .
   
   # Linting
   uv run ruff check .
   
   # 格式化
   uv run ruff format .
   ```

6. **提交变更**
   ```bash
   git add .
   git commit -m "feat: 新增功能"
   # 或
   git commit -m "fix: 修復 X 的问题"
   ```

   **Commit 讯息格式**:
   - `feat:` - 新功能
   - `fix:` - 错误修復
   - `docs:` - 文件变更
   - `test:` - 测试变更
   - `refactor:` - 程式码重构
   - `chore:` - 維护任務

7. **推送并建立 PR**
   ```bash
   git push origin feature/你的功能名稱
   gh pr create --fill
   ```

## 开发环境设定

### 前置需求

- Python 3.11, 3.12, 或 3.13
- Git

### 安裝

1. **Clone 倉庫**
   ```bash
   git clone https://github.com/coseto6125/pyci-check.git
   cd pyci-check
   ```

2. **建立虛擬环境**
   ```bash
   # 使用 uv（推荐）
   uv venv
   source .venv/bin/activate  # Linux/macOS
   # 或
   .venv\Scripts\activate  # Windows
   
   # 或使用标准 venv
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **以开发模式安裝**
   ```bash
   # 使用 uv（推荐）
   uv sync --extra dev

   # 或使用 pip
   pip install -e ".[dev]"
   ```

### 执行测试

```bash
# 所有测试
uv run pytest

# 特定测试档案
uv run pytest tests/test_syntax.py

# 含覆盖率报告
uv run pytest --cov=pyci_check --cov-report=html

# Watch 模式（需要 pytest-watch）
ptw
```

### 程式码风格

我們使用：
- **ruff** 进行 linting 和格式化
- **pyci-check** 进行语法和 import 验证
- **pytest** 进行测试

提交 PR 前，请确保：
```bash
uv run pyci-check check .
uv run ruff check .
uv run ruff format .
uv run pytest
```

## 专案结构

```
uv run pyci-check/
├── src/pyci_check/     # 主要原始码
│   ├── cli.py          # CLI 介面
│   ├── syntax.py       # 语法检查
│   ├── imports.py      # Import 检查
│   ├── git_hook.py     # Git hooks 功能
│   ├── i18n.py         # 國际化
│   └── locales/        # 语言档案
├── tests/              # 测试套件
├── docs/               # 文件
│   ├── en/            # 英文文件
│   ├── zh_TW/         # 繁體中文文件
│   └── zh_CN/         # 簡體中文文件
└── scripts/           # 輔助腳本
```

## 文件

新增功能时：
- 更新 `docs/` 中的相关文件
- 为函式和类别添加 docstrings
- 更新 `CHANGELOG.md`
- 考慮在 README 中添加范例

## 发布流程

发布透过 GitHub Actions 自动化。仅維护者可建立发布：

1. 在 `pyproject.toml` 中更新版本
2. 更新 `CHANGELOG.md`
3. 建立并推送 tag：`git tag -a v0.x.0 -m "Release v0.x.0"`
4. 推送 tag：`git push origin v0.x.0`
5. GitHub Actions 会自动建置并发布到 PyPI

## 有问题？

如果有问题，歡迎：
- 开啟 issue 討論
- 查看现有的 issues 和 PRs
- 阅读 `docs/` 中的文件

感謝你的貢獻！🎉
