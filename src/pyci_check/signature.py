"""
跨檔案本地簽章驗證 (Cross-file Signature Check).

透過純靜態 AST 分析，抓出本地專案中函數與類別呼叫時的參數不匹配錯誤。
（例如：少傳必填參數、多傳了不存在的 kwargs 等）
"""

import ast
import os
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional


@dataclass
class Signature:
    """函數或類別的參數簽章定義."""

    module: str
    name: str
    min_pos: int
    max_pos: int  # -1 代表無限 (有 *args)
    pos_arg_names: Set[str]
    kwonly_args: Set[str]
    required_kwonly: Set[str]
    has_varargs: bool
    has_varkw: bool
    is_method: bool = False

    @property
    def all_arg_names(self) -> Set[str]:
        return self.pos_arg_names | self.kwonly_args


class DefinitionCollector(ast.NodeVisitor):
    """第一階段：收集檔案內的函數與類別簽章."""

    def __init__(self, module_name: str):
        self.module_name = module_name
        # name -> Signature
        self.signatures: Dict[str, Signature] = {}
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        prev_class = self.current_class
        self.current_class = node.name

        # 檢查是否為 dataclass
        is_dataclass = any(
            isinstance(d, ast.Name) and d.id == "dataclass" or isinstance(d, ast.Call) and getattr(d.func, "id", "") == "dataclass"
            for d in node.decorator_list
        )

        if is_dataclass:
            # 蒐集所有的 field
            fields = []
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields.append(stmt.target.id)

            self.signatures[node.name] = Signature(
                module=self.module_name,
                name=node.name,
                min_pos=0,  # dataclass 的 default 值較難靜態推導，這裡放寬必填檢查
                max_pos=len(fields),
                pos_arg_names=set(fields),
                kwonly_args=set(),
                required_kwonly=set(),
                has_varargs=False,
                has_varkw=False,
            )
        else:
            # 預設一個空的建構子
            self.signatures[node.name] = Signature(
                module=self.module_name,
                name=node.name,
                min_pos=0,
                max_pos=0,
                pos_arg_names=set(),
                kwonly_args=set(),
                required_kwonly=set(),
                has_varargs=False,
                has_varkw=False,
            )

        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._parse_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._parse_function(node)
        self.generic_visit(node)

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        is_method = self.current_class is not None

        # 收集參數
        pos_args = []
        if hasattr(node.args, "posonlyargs"):
            pos_args.extend(node.args.posonlyargs)
        pos_args.extend(node.args.args)

        # 扣掉 self/cls
        if is_method and pos_args and not (node.name == "__new__" and not pos_args):
            pos_args = pos_args[1:]

        pos_arg_names = {a.arg for a in pos_args}

        # 計算預設值數量 (由後往前算)
        num_defaults = len(node.args.defaults)
        min_pos = max(0, len(pos_args) - num_defaults)
        max_pos = len(pos_args)

        # Keyword-only
        kwonly_args = {a.arg for a in node.args.kwonlyargs}
        kw_defaults_count = sum(1 for d in node.args.kw_defaults if d is not None)
        required_kwonly = {a.arg for a, d in zip(node.args.kwonlyargs, node.args.kw_defaults) if d is None}

        has_varargs = node.args.vararg is not None
        has_varkw = node.args.kwarg is not None

        if has_varargs:
            max_pos = -1

        sig = Signature(
            module=self.module_name,
            name=node.name,
            min_pos=min_pos,
            max_pos=max_pos,
            pos_arg_names=pos_arg_names,
            kwonly_args=kwonly_args,
            required_kwonly=required_kwonly,
            has_varargs=has_varargs,
            has_varkw=has_varkw,
            is_method=is_method,
        )

        if is_method:
            if node.name in ("__init__", "__new__"):
                # 覆寫 class 的簽章
                sig.name = self.current_class
                sig.is_method = False  # instantiation is treated like a function call
                self.signatures[self.current_class] = sig
            else:
                # 記錄 method (但我們可能只檢查明確的模組方法，動態方法太難追蹤)
                self.signatures[f"{self.current_class}.{node.name}"] = sig
        else:
            self.signatures[node.name] = sig


class CallValidator(ast.NodeVisitor):
    """第二階段：驗證檔案內的函數呼叫."""

    def __init__(self, filepath: str, module_name: str, global_signatures: Dict[str, Signature]):
        self.filepath = filepath
        self.module_name = module_name
        self.global_signatures = global_signatures
        self.errors: List[dict] = []

        # 追蹤檔案內的 import： local_name -> fully_qualified_name
        # e.g., "safe_relpath" -> "pyci_check.utils.safe_relpath"
        self.imports: Dict[str, str] = {}

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            local_name = alias.asname or alias.name
            self.imports[local_name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if not node.module or node.level > 0:
            # 暫時略過相對導入的精確計算 (可以透過 level + module_name 算，但較複雜)
            self.generic_visit(node)
            return

        for alias in node.names:
            local_name = alias.asname or alias.name
            self.imports[local_name] = f"{node.module}.{alias.name}"
        self.generic_visit(node)

    def _resolve_name(self, node: ast.expr) -> str | None:
        """嘗試將 AST 節點解析為 Full Qualified Name."""
        if isinstance(node, ast.Name):
            # 1. 可能是 import 進來的
            if node.id in self.imports:
                return self.imports[node.id]
            # 2. 可能是同一個檔案內定義的 (module.func)
            return f"{self.module_name}.{node.id}"

        elif isinstance(node, ast.Attribute):
            # 例如 os.path.join -> 我們先解析 os.path
            base = self._resolve_name(node.value)
            if base:
                return f"{base}.{node.attr}"
        return None

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)

        full_name = self._resolve_name(node.func)
        if not full_name or full_name not in self.global_signatures:
            return

        sig = self.global_signatures[full_name]

        # 如果呼叫包含了 *args 或是 **kwargs，我們放棄嚴格檢查，避免誤判
        has_starred = any(isinstance(a, ast.Starred) for a in node.args)
        has_dict_unpack = any(k.arg is None for k in node.keywords)
        if has_starred or has_dict_unpack:
            return

        provided_pos = len(node.args)
        provided_kws = {k.arg for k in node.keywords if k.arg is not None}

        # 1. 位置參數過多
        if sig.max_pos != -1 and provided_pos > sig.max_pos:
            self._report(
                node.lineno,
                full_name,
                f"Too many positional arguments: expected at most {sig.max_pos}, got {provided_pos}",
                sig,
                provided_pos,
                provided_kws,
                f"Remove the extra {provided_pos - sig.max_pos} positional argument(s), or convert them to keyword arguments if the function accepts them.",
            )
            return

        # 2. 未知的 Keyword 參數
        if not sig.has_varkw:
            unknown_kws = provided_kws - sig.all_arg_names
            if unknown_kws:
                self._report(
                    node.lineno,
                    full_name,
                    f"Unexpected keyword arguments: {', '.join(unknown_kws)}",
                    sig,
                    provided_pos,
                    provided_kws,
                    f"Remove or rename the invalid keyword argument(s): {', '.join(unknown_kws)}. Check the function definition for correct parameter names.",
                )
                return

        # 3. 檢查必填參數
        matched_pos_kws = provided_kws.intersection(sig.pos_arg_names)
        total_matched_pos = provided_pos + len(matched_pos_kws)

        if total_matched_pos < sig.min_pos:
            self._report(
                node.lineno,
                full_name,
                f"Missing required positional arguments: expected at least {sig.min_pos}, got {total_matched_pos}",
                sig,
                provided_pos,
                provided_kws,
                f"Supply the missing {sig.min_pos - total_matched_pos} required positional argument(s). Review the function signature to see what is missing.",
            )

        missing_kwonly = sig.required_kwonly - provided_kws
        if missing_kwonly:
            self._report(
                node.lineno,
                full_name,
                f"Missing required keyword-only arguments: {', '.join(missing_kwonly)}",
                sig,
                provided_pos,
                provided_kws,
                f"You must explicitly pass the following arguments as keyword arguments (e.g., param=value): {', '.join(missing_kwonly)}.",
            )

    def _report(self, lineno: int, func: str, error_msg: str, sig: Signature, provided_pos: int, provided_kws: Set[str], hint: str):
        # 建立 Expected Signature 字串
        pos_info = f"pos_args: {sig.min_pos}" if sig.min_pos == sig.max_pos else f"pos_args: {sig.min_pos}~{sig.max_pos}"
        if sig.max_pos == -1:
            pos_info = f"pos_args: {sig.min_pos}+ (*args)"

        kw_info = f", kw_only: {sorted(sig.required_kwonly)}" if sig.required_kwonly else ""
        if sig.has_varkw:
            kw_info += ", **kwargs"

        expected_str = f"{func}({pos_info}{kw_info})"
        actual_str = f"provided {provided_pos} positional, {len(provided_kws)} keyword args ({sorted(provided_kws)})"

        detailed_reason = f"{error_msg}\n       Expected : {expected_str}\n       Actual   : {actual_str}\n       Hint     : {hint}"

        self.errors.append({"file": self.filepath, "line": lineno, "func": func, "reason": detailed_reason})


def _get_module_name(filepath: str, project_dir: str, src_dirs: List[str]) -> str:
    """將檔案路徑轉換為模組名稱."""
    abs_fp = os.path.abspath(filepath)
    roots = [os.path.abspath(project_dir)]
    roots.extend(os.path.abspath(os.path.join(project_dir, s)) for s in src_dirs)

    best_mod = None
    for root in roots:
        if abs_fp.startswith(root):
            rel = os.path.relpath(abs_fp, root)
            mod = rel.replace(os.sep, ".").removesuffix(".py").removesuffix(".__init__")
            if best_mod is None or len(mod) < len(best_mod):
                best_mod = mod
    return best_mod or os.path.basename(filepath).removesuffix(".py")


def check_signatures(python_files: List[str], project_dir: str, src_dirs: List[str]) -> List[dict]:
    """
    掃描專案，執行本地簽章驗證.

    Returns:
        包含錯誤資訊的列表
    """
    from pyci_check.imports import read_file_with_encoding

    # 1. 收集所有的簽章 (Full Qualified Name -> Signature)
    global_signatures: Dict[str, Signature] = {}
    file_asts = {}
    file_modules = {}

    for filepath in python_files:
        code = read_file_with_encoding(filepath)
        if not code:
            continue
        try:
            tree = ast.parse(code)
            mod_name = _get_module_name(filepath, project_dir, src_dirs)

            collector = DefinitionCollector(mod_name)
            collector.visit(tree)

            for local_name, sig in collector.signatures.items():
                global_signatures[f"{mod_name}.{local_name}"] = sig

            file_asts[filepath] = tree
            file_modules[filepath] = mod_name
        except SyntaxError:
            pass

    # 2. 驗證所有檔案
    all_errors = []
    for filepath, tree in file_asts.items():
        validator = CallValidator(filepath, file_modules[filepath], global_signatures)
        validator.visit(tree)
        all_errors.extend(validator.errors)

    return all_errors
