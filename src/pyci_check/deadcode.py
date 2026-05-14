"""
死代碼深層掃描 (Deep Dead Code Elimination).

掃描整個專案，找出定義了但在整個專案中完全沒有被呼叫過的函數或類別。
這是一種啟發式掃描，僅作為警告輸出。

由於 Python 的動態特性，這可能會產生 False Positives (例如透過反射呼叫、
或者作為 API 暴露給外部使用)。
"""

import ast


class DefinitionVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        # 定義的符號: name -> lineno
        self.definitions: dict[str, int] = {}
        # 標記在 __all__ 裡的符號 (視為 public API，不應報警)
        self.exported: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 排除魔術方法
        if not (node.name.startswith("__") and node.name.endswith("__")):
            self.definitions[node.name] = node.lineno
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if not (node.name.startswith("__") and node.name.endswith("__")):
            self.definitions[node.name] = node.lineno
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.definitions[node.name] = node.lineno
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # 嘗試解析 __all__ = ["func1", "func2"]
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        self.exported.add(elt.value)
        self.generic_visit(node)


class UsageVisitor(ast.NodeVisitor):
    def __init__(self):
        # 所有被使用的符號名稱
        self.used_names: set[str] = set()

    def visit_Name(self, node: ast.Name):
        # 如果作為變數被讀取，我們也視為被使用 (例如當作 callback 傳遞)
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # obj.method 的情況
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.attr)
        self.generic_visit(node)

    # 不需要特別覆蓋 visit_Call，因為 call 的 func 通常是 Name 或 Attribute，
    # 會被上面的方法捕獲。


def scan_dead_code(python_files: list[str]) -> list[dict]:
    """
    掃描專案尋找可能未被呼叫的定義.

    Returns:
        包含死代碼資訊的列表
    """
    from pyci_check.imports import read_file_with_encoding

    # name -> list of {file, line}
    all_definitions: dict[str, list[dict]] = {}
    all_exported: set[str] = set()

    # 存放所有使用的名字
    usage_visitor = UsageVisitor()

    # Pass 1 & 2: 收集定義與使用
    for filepath in python_files:
        code = read_file_with_encoding(filepath)
        if not code:
            continue

        try:
            tree = ast.parse(code)

            # 收集定義
            def_visitor = DefinitionVisitor(filepath)
            def_visitor.visit(tree)

            for name, lineno in def_visitor.definitions.items():
                if name not in all_definitions:
                    all_definitions[name] = []
                all_definitions[name].append({"file": filepath, "line": lineno})

            all_exported.update(def_visitor.exported)

            # 收集使用
            usage_visitor.visit(tree)

        except SyntaxError:
            pass

    # 分析結果
    warnings = []

    # 常見的框架鉤子/白名單 (不應被報警)
    whitelist = {
        "main",
        "setup",
        "run",
        "cli",  # 入口
        "pytest_configure",
        "pytest_addoption",  # pytest 鉤子
    }

    for name, locations in all_definitions.items():
        if name in all_exported or name in whitelist:
            continue

        # 測試檔案中的定義 (例如 test_foo) 不算死代碼，它們是由測試運行器呼叫的
        [loc for loc in locations if not loc["file"].endswith("test_" + name + ".py")]

        # 簡化判斷：如果一個符號的定義都在 test 檔案裡 (或者開頭是 test_)，略過
        if name.startswith(("test_", "fixture_")):
            continue

        if name not in usage_visitor.used_names:
            warnings.extend(
                {"file": loc["file"], "line": loc["line"], "name": name, "reason": "Definition appears to be unused across the project"}
                for loc in locations
            )

    return warnings
