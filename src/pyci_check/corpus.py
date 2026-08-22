"""
共用 AST 語料:一次讀檔、一次 parse,多個掃描器重複使用.

讀檔與 parse 的失敗處理 (編碼、SyntaxError) 集中在 Corpus.load;
掃描器只面對已解析的 AST,不再各自處理 I/O 與解析錯誤.
"""

import ast
import contextlib
from dataclasses import dataclass, field

from pyci_check.imports import read_file_with_encoding


@dataclass(frozen=True, slots=True)
class Corpus:
    """
    已解析的專案 AST 語料.

    Attributes:
        trees: filepath -> ast.Module (讀取失敗或語法錯誤的檔案不在其中)
    """

    trees: dict[str, ast.Module] = field(default_factory=dict)

    @classmethod
    def load(cls, python_files: list[str]) -> "Corpus":
        """讀取並 parse 檔案清單;失敗的檔案靜默略過 (與各掃描器原本的行為一致)."""
        trees: dict[str, ast.Module] = {}
        for filepath in python_files:
            code = read_file_with_encoding(filepath)
            if not code:
                continue
            with contextlib.suppress(SyntaxError):
                trees[filepath] = ast.parse(code)
        return cls(trees)
