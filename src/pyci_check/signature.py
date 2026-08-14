"""
跨檔案本地簽章驗證 (Cross-file Signature Check).

透過純靜態 AST 分析，抓出本地專案中函數與類別呼叫時的參數不匹配錯誤。
（例如：少傳必填參數、多傳了不存在的 kwargs 等）
"""

import ast
import os
from dataclasses import dataclass, replace

from pyci_check.corpus import Corpus
from pyci_check.findings import Finding
from pyci_check.i18n import t


@dataclass
class Signature:
    """函數或類別的參數簽章定義."""

    module: str
    name: str
    min_pos: int
    max_pos: int  # -1 代表無限 (有 *args)
    pos_arg_names: set[str]
    kwonly_args: set[str]
    required_kwonly: set[str]
    has_varargs: bool
    has_varkw: bool
    is_method: bool = False
    field_signature_kind: str | None = None
    field_signature_allows_missing: bool = False
    field_signature_required_names: frozenset[str] = frozenset()

    @property
    def all_arg_names(self) -> set[str]:
        return self.pos_arg_names | self.kwonly_args


class DefinitionCollector(ast.NodeVisitor):
    """第一階段：收集檔案內的函數與類別簽章."""

    def __init__(self, module_name: str):
        self.module_name = module_name
        # name -> Signature
        self.signatures: dict[str, Signature] = {}
        self.inherited_classes: dict[str, list[str]] = {}
        self.inherited_fields: dict[str, tuple[set[str], set[str]]] = {}
        self.imports: dict[str, str] = {}
        self.current_class: str | None = None

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports[alias.asname or alias.name] = alias.name

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if not node.module or node.level > 0:
            return

        for alias in node.names:
            self.imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def _resolve_name(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return self.imports.get(node.id, f"{self.module_name}.{node.id}")
        if isinstance(node, ast.Attribute) and (base := self._resolve_name(node.value)):
            return f"{base}.{node.attr}"
        return None

    def _decorator_name(self, decorator: ast.expr) -> str | None:
        if isinstance(decorator, ast.Call):
            decorator = decorator.func
        return self._resolve_name(decorator)

    def _class_fields(self, node: ast.ClassDef) -> list[ast.AnnAssign]:
        fields = []
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            annotation = stmt.annotation.value if isinstance(stmt.annotation, ast.Subscript) else stmt.annotation
            if self._resolve_name(annotation) != "typing.ClassVar":
                fields.append(stmt)
        return fields

    @staticmethod
    def _has_true_keyword(keywords: list[ast.keyword], name: str) -> bool:
        return any(keyword.arg == name and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in keywords)

    def _field_signature(self, node: ast.ClassDef, *, keyword_only: bool, allow_missing: bool = False) -> Signature:
        fields = self._class_fields(node)
        field_names = {field.target.id for field in fields}
        required_names = {field.target.id for field in fields if field.value is None}

        if keyword_only:
            return Signature(
                module=self.module_name,
                name=node.name,
                min_pos=0,
                max_pos=0,
                pos_arg_names=set(),
                kwonly_args=field_names,
                required_kwonly=set() if allow_missing else required_names,
                has_varargs=False,
                has_varkw=False,
                field_signature_kind="keyword_only",
                field_signature_allows_missing=allow_missing,
                field_signature_required_names=frozenset(required_names),
            )

        return Signature(
            module=self.module_name,
            name=node.name,
            min_pos=0 if allow_missing else len(required_names),
            max_pos=len(fields),
            pos_arg_names=field_names,
            kwonly_args=set(),
            required_kwonly=set(),
            has_varargs=False,
            has_varkw=False,
            field_signature_kind="positional",
            field_signature_allows_missing=allow_missing,
            field_signature_required_names=frozenset(required_names),
        )

    def visit_ClassDef(self, node: ast.ClassDef):
        if self.current_class is not None:
            return

        prev_class = self.current_class
        self.current_class = node.name

        decorator_names = {self._decorator_name(decorator) for decorator in node.decorator_list}
        is_dataclass = len(node.decorator_list) == 1 and (
            "dataclasses.dataclass" in decorator_names
            or any(
                isinstance(decorator.func if isinstance(decorator, ast.Call) else decorator, ast.Name)
                and (decorator.func if isinstance(decorator, ast.Call) else decorator).id == "dataclass"
                for decorator in node.decorator_list
            )
        )
        base_names = [name for base in node.bases if (name := self._resolve_name(base)) is not None]
        is_msgspec_struct = "msgspec.Struct" in base_names
        is_named_tuple = "typing.NamedTuple" in base_names or any(isinstance(base, ast.Name) and base.id == "NamedTuple" for base in node.bases)
        has_explicit_constructor = any(
            isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name in ("__init__", "__new__") for stmt in node.body
        )

        if not has_explicit_constructor:
            if is_dataclass:
                self.signatures[node.name] = self._field_signature(
                    node,
                    keyword_only=self._has_true_keyword(
                        [keyword for decorator in node.decorator_list if isinstance(decorator, ast.Call) for keyword in decorator.keywords],
                        "kw_only",
                    ),
                    allow_missing=True,
                )
            elif is_msgspec_struct and not node.decorator_list:
                self.signatures[node.name] = self._field_signature(
                    node,
                    keyword_only=self._has_true_keyword(node.keywords, "kw_only"),
                )
            elif is_named_tuple and not node.decorator_list:
                self.signatures[node.name] = self._field_signature(node, keyword_only=False)
            elif not node.bases and not node.decorator_list and not node.keywords:
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
            elif len(node.bases) == 1 and not node.decorator_list and not node.keywords and len(base_names) == 1:
                self.inherited_classes[node.name] = base_names
                fields = self._class_fields(node)
                self.inherited_fields[node.name] = (
                    {field.target.id for field in fields},
                    {field.target.id for field in fields if field.value is None},
                )

        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(stmt)

        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._parse_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._parse_function(node)

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        decorator_names = {self._decorator_name(decorator) for decorator in node.decorator_list}
        known_method_decorators = {
            f"{self.module_name}.classmethod",
            f"{self.module_name}.staticmethod",
        }
        signature_preserving_decorators = {
            "functools.cache",
            "functools.lru_cache",
        }
        known_decorators = known_method_decorators | signature_preserving_decorators
        if node.decorator_list and not decorator_names <= known_decorators:
            # Unknown decorators may replace the callable or alter its runtime
            # signature. Skipping loses coverage but avoids an unverifiable error.
            return

        is_method = self.current_class is not None
        is_staticmethod = f"{self.module_name}.staticmethod" in decorator_names

        # 收集參數
        pos_args = []
        if hasattr(node.args, "posonlyargs"):
            pos_args.extend(node.args.posonlyargs)
        pos_args.extend(node.args.args)

        # 扣掉 self/cls；staticmethod 沒有隱含接收者
        if is_method and not is_staticmethod and pos_args:
            pos_args = pos_args[1:]

        pos_arg_names = {a.arg for a in pos_args}

        # 計算預設值數量 (由後往前算)
        num_defaults = len(node.args.defaults)
        min_pos = max(0, len(pos_args) - num_defaults)
        max_pos = len(pos_args)

        # Keyword-only
        kwonly_args = {a.arg for a in node.args.kwonlyargs}
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

    def __init__(self, filepath: str, module_name: str, global_signatures: dict[str, Signature]):
        self.filepath = filepath
        self.module_name = module_name
        self.global_signatures = global_signatures
        self.errors: list[Finding] = []

        # 追蹤檔案內的 import： local_name -> fully_qualified_name
        # e.g., "safe_relpath" -> "pyci_check.utils.safe_relpath"
        self.imports: dict[str, str] = {}

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

        if isinstance(node, ast.Attribute):
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
                t("signature.error.too_many_positional", max_pos=sig.max_pos, provided=provided_pos),
                sig,
                provided_pos,
                provided_kws,
                t("signature.hint.too_many_positional", extra=provided_pos - sig.max_pos),
            )
            return

        # 2. 未知的 Keyword 參數
        if not sig.has_varkw:
            unknown_kws = provided_kws - sig.all_arg_names
            if unknown_kws:
                self._report(
                    node.lineno,
                    full_name,
                    t("signature.error.unknown_keywords", names=", ".join(unknown_kws)),
                    sig,
                    provided_pos,
                    provided_kws,
                    t("signature.hint.unknown_keywords", names=", ".join(unknown_kws)),
                )
                return

        # 3. 檢查必填參數
        matched_pos_kws = provided_kws.intersection(sig.pos_arg_names)
        total_matched_pos = provided_pos + len(matched_pos_kws)

        if total_matched_pos < sig.min_pos:
            self._report(
                node.lineno,
                full_name,
                t("signature.error.missing_positional", min_pos=sig.min_pos, total_matched=total_matched_pos),
                sig,
                provided_pos,
                provided_kws,
                t("signature.hint.missing_positional", missing=sig.min_pos - total_matched_pos),
            )

        missing_kwonly = sig.required_kwonly - provided_kws
        if missing_kwonly:
            self._report(
                node.lineno,
                full_name,
                t("signature.error.missing_kwonly", names=", ".join(missing_kwonly)),
                sig,
                provided_pos,
                provided_kws,
                t("signature.hint.missing_kwonly", names=", ".join(missing_kwonly)),
            )

    def _report(self, lineno: int, func: str, error_msg: str, sig: Signature, provided_pos: int, provided_kws: set[str], hint: str):
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

        self.errors.append(Finding(file=self.filepath, line=lineno, message=f"{func} ({detailed_reason})", severity="error"))


def _get_module_name(filepath: str, project_dir: str, src_dirs: list[str]) -> str:
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


def check_signatures(
    python_files: list[str],
    project_dir: str,
    src_dirs: list[str],
    *,
    corpus: Corpus | None = None,
) -> list[Finding]:
    """
    掃描專案，執行本地簽章驗證.

    Args:
        python_files: 要掃描的檔案列表
        project_dir: 專案根目錄
        src_dirs: source 目錄 (相對於 project_dir)
        corpus: 共用的已解析語料;未提供時自行載入

    Returns:
        簽章錯誤 (Finding) 的列表
    """
    # 1. 收集所有的簽章 (Full Qualified Name -> Signature)
    global_signatures: dict[str, Signature] = {}
    inherited_classes: dict[str, list[str]] = {}
    inherited_fields: dict[str, tuple[set[str], set[str]]] = {}
    file_asts: dict[str, ast.Module] = {}
    file_modules: dict[str, str] = {}

    # 簽章驗證需先收集全專案定義再比對,整批持有 AST 是本質需求 (與 base 相同);
    # standalone 也走 Corpus,記憶體特性與 13e3e7d 一致
    trees = corpus.trees if corpus is not None else Corpus.load(python_files).trees
    for filepath, tree in trees.items():
        mod_name = _get_module_name(filepath, project_dir, src_dirs)

        collector = DefinitionCollector(mod_name)
        collector.visit(tree)

            for local_name, sig in collector.signatures.items():
                global_signatures[f"{mod_name}.{local_name}"] = sig
            for local_name, bases in collector.inherited_classes.items():
                class_name = f"{mod_name}.{local_name}"
                inherited_classes[class_name] = bases
                inherited_fields[class_name] = collector.inherited_fields[local_name]

        file_asts[filepath] = tree
        file_modules[filepath] = mod_name

    # 只有單一父類的簽章能被明確解析時才沿用；其餘類別不做推測。
    while inherited_classes:
        resolved = {
            class_name: bases[0] for class_name, bases in inherited_classes.items() if len(bases) == 1 and bases[0] in global_signatures
        }
        if not resolved:
            break
        for class_name, base_name in resolved.items():
            module, name = class_name.rsplit(".", 1)
            base_signature = global_signatures[base_name]
            field_names, required_fields = inherited_fields[class_name]
            signature = replace(base_signature, module=module, name=name, is_method=False)
            merged_required_fields = (set(base_signature.field_signature_required_names) - field_names) | required_fields
            effective_required_fields = set() if base_signature.field_signature_allows_missing else merged_required_fields
            if base_signature.field_signature_kind == "keyword_only":
                signature = replace(
                    signature,
                    kwonly_args=base_signature.kwonly_args | field_names,
                    required_kwonly=effective_required_fields,
                    field_signature_required_names=frozenset(merged_required_fields),
                )
            elif base_signature.field_signature_kind == "positional":
                positional_names = base_signature.pos_arg_names | field_names
                signature = replace(
                    signature,
                    min_pos=len(effective_required_fields),
                    max_pos=len(positional_names),
                    pos_arg_names=positional_names,
                    field_signature_required_names=frozenset(merged_required_fields),
                )
            global_signatures[class_name] = signature
            del inherited_classes[class_name]
            del inherited_fields[class_name]

    # 2. 驗證所有檔案
    all_errors: list[Finding] = []
    for filepath, tree in file_asts.items():
        validator = CallValidator(filepath, file_modules[filepath], global_signatures)
        validator.visit(tree)
        all_errors.extend(validator.errors)

    return all_errors
