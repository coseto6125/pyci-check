"""
全局副作用偵測 (Global Side-Effect Detection).

檢查在模組的最外層 (Top-level) 是否有執行危險操作：
1. 啟動執行緒或進程 (Thread, Process)
2. 阻塞型網路呼叫 (requests.get, urlopen 等)

這些行為會導致 import 變慢，且可能引發不可預期的執行期問題。
僅作為警告輸出，不中斷 CI。
"""

import ast


class SideEffectVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.warnings: list[dict] = []

        # 追蹤作用域深度，只有 depth == 0 才是 top-level
        self.scope_depth = 0

        import os

        filename = os.path.basename(filepath)
        # 判斷是否為測試檔案
        self.is_test_file = filename.startswith("test_") or "tests" in filepath.split(os.sep)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.scope_depth += 1
        self.generic_visit(node)
        self.scope_depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.scope_depth += 1
        self.generic_visit(node)
        self.scope_depth -= 1

    def visit_ClassDef(self, node: ast.ClassDef):
        self.scope_depth += 1
        self.generic_visit(node)
        self.scope_depth -= 1

    def visit_Call(self, node: ast.Call):
        # 1. 頂層副作用：任何檔案的 scope_depth == 0
        # 2. 測試純潔度：測試檔案內的任何深度
        if self.scope_depth == 0 or self.is_test_file:
            func_name = self._get_call_name(node.func)
            if func_name:
                self._check_dangerous_call(func_name, node.lineno)

        self.generic_visit(node)

    def _get_call_name(self, node: ast.expr) -> str:
        """嘗試獲取函數呼叫的完整名稱."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            # 簡化處理：如果是 obj.method，我們只回傳 method 名稱
            # 若是 module.method，我們回傳 module.method
            if isinstance(node.value, ast.Name):
                return f"{node.value.id}.{node.attr}"
            return node.attr
        return ""

    def _check_dangerous_call(self, call_name: str, lineno: int):
        # 定義危險名單
        dangerous = {
            # 執行緒與進程
            "Thread": "Thread/Process creation",
            "threading.Thread": "Thread/Process creation",
            "Process": "Thread/Process creation",
            "multiprocessing.Process": "Thread/Process creation",
            # 常見網路請求
            "requests.get": "Network request",
            "requests.post": "Network request",
            "requests.request": "Network request",
            "urlopen": "Network request",
            "urllib.request.urlopen": "Network request",
            "socket.socket": "Socket creation",
            "httpx.get": "Network request",
            "httpx.post": "Network request",
        }

        if call_name in dangerous:
            reason_base = dangerous[call_name]

            reason = f"Top-level {reason_base.lower()}" if self.scope_depth == 0 else f"Impure test: {reason_base.lower()} detected"

            self.warnings.append({"file": self.filepath, "line": lineno, "call": call_name, "reason": reason})


def detect_side_effects(python_files: list[str], check_test_purity: bool = False) -> list[dict]:
    """
    掃描檔案尋找頂層副作用與不純潔的測試.

    Args:
        python_files: 要掃描的檔案列表
        check_test_purity: 是否開啟測試純潔度檢查

    Returns:
        包含警告資訊的列表
    """
    from pyci_check.imports import read_file_with_encoding

    all_warnings = []

    for filepath in python_files:
        code = read_file_with_encoding(filepath)
        if not code:
            continue

        try:
            tree = ast.parse(code)
            visitor = SideEffectVisitor(filepath)

            # 如果沒有開啟測試純潔度檢查，就強制把 is_test_file 設為 False，
            # 這樣就只會檢查頂層副作用 (scope_depth == 0)
            if not check_test_purity:
                visitor.is_test_file = False

            visitor.visit(tree)
            all_warnings.extend(visitor.warnings)
        except SyntaxError:
            pass

    return all_warnings
