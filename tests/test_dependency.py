"""測試依賴健康度檢查."""

from pyci_check.dependency import find_dependency_issues, get_declared_dependencies, parse_pyproject_dependencies, parse_requirements_txt


def test_parse_pyproject_dependencies(tmp_path):
    """測試解析標準 PEP 621 格式的 pyproject.toml"""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[project]
dependencies = [
    "requests>=2.0.0",
    "numpy",
]

[project.optional-dependencies]
dev = ["pytest"]
""", encoding="utf-8")

    deps = parse_pyproject_dependencies(str(pyproject))
    assert deps == {"requests", "numpy", "pytest"}

def test_parse_pyproject_poetry(tmp_path):
    """測試解析 Poetry 格式的 pyproject.toml"""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.100.0"

[tool.poetry.group.dev.dependencies]
pytest-cov = "^4.0.0"
""", encoding="utf-8")

    deps = parse_pyproject_dependencies(str(pyproject))
    # python 應該被排除
    assert deps == {"fastapi", "pytest-cov"}

def test_parse_empty_or_missing_pyproject(tmp_path):
    """測試缺少檔案或空檔案的容錯"""
    assert parse_pyproject_dependencies(str(tmp_path / "not_exist.toml")) == set()

    empty_toml = tmp_path / "empty.toml"
    empty_toml.write_text("", encoding="utf-8")
    assert parse_pyproject_dependencies(str(empty_toml)) == set()

def test_parse_requirements_txt(tmp_path):
    """測試解析 requirements.txt"""
    reqs = tmp_path / "requirements.txt"
    reqs.write_text("""
requests==2.25.1
# 註解行
-r other.txt
--index-url https://...
numpy>=1.19 ; python_version < '3.8'
my-custom_pkg
""", encoding="utf-8")

    deps = parse_requirements_txt(str(reqs))
    # 應忽略註解、特殊指令，並處理分號與符號
    assert deps == {"requests", "numpy", "my-custom-pkg"}

def test_find_dependency_issues_phantom():
    """測試幽靈依賴偵測"""
    project_dir = "."
    # 假設我們匯入了 requests, os(內建), my_local(本地) 和 bs4(第三方未宣告)
    imported_modules = {"requests", "os", "my_local", "bs4"}
    local_modules = {"my_local"}

    import pyci_check.dependency as dep_mod
    original_get_deps = dep_mod.get_declared_dependencies

    # Mock 只宣告了 requests
    dep_mod.get_declared_dependencies = lambda _: {"requests"}

    try:
        issues = find_dependency_issues(project_dir, imported_modules, local_modules)

        # os 是內建，my_local 是本地，requests 有宣告
        # 只有 bs4 是幽靈依賴
        assert "bs4" in issues["phantom"]
        assert "requests" not in issues["phantom"]
        assert "os" not in issues["phantom"]

    finally:
        dep_mod.get_declared_dependencies = original_get_deps

def test_find_dependency_issues_orphan():
    """測試冗餘依賴偵測"""
    project_dir = "."
    # 程式碼中只有用到 requests
    imported_modules = {"requests"}
    local_modules = set()

    import pyci_check.dependency as dep_mod
    original_get_deps = dep_mod.get_declared_dependencies

    # 但設定檔宣告了 requests, pandas (沒用到), 和 pytest (工具套件，應被忽略)
    dep_mod.get_declared_dependencies = lambda _: {"requests", "pandas", "pytest"}

    try:
        issues = find_dependency_issues(project_dir, imported_modules, local_modules)

        # pandas 宣告了但沒 import -> Orphan
        assert "pandas" in issues["orphan"]
        # pytest 是白名單工具 -> 不算 Orphan
        assert "pytest" not in issues["orphan"]
        # requests 有用到 -> 不算 Orphan
        assert "requests" not in issues["orphan"]

    finally:
        dep_mod.get_declared_dependencies = original_get_deps

def test_get_declared_dependencies_integration(tmp_path):
    """測試整合尋找專案內所有依賴檔案"""
    (tmp_path / "pyproject.toml").write_text("[project]\ndependencies=['httpx']\n", encoding="utf-8")
    (tmp_path / "requirements-dev.txt").write_text("black\n", encoding="utf-8")

    all_deps = get_declared_dependencies(str(tmp_path))
    assert all_deps == {"httpx", "black"}
