"""
共用 AST 語料:一次讀檔、一次 parse,多個掃描器重複使用.

讀檔與 parse 的失敗處理 (編碼、SyntaxError) 集中在 Corpus.load;
掃描器只面對已解析的 AST,不再各自處理 I/O 與解析錯誤.
"""

import ast
import contextlib
from collections.abc import Iterator
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
        return cls(dict(iter_trees(python_files)))


def iter_trees(
    python_files: list[str],
    corpus: "Corpus | None" = None,
) -> Iterator[tuple[str, ast.Module]]:
    """
    逐檔供應 (filepath, tree).

    corpus 提供時以語料為準,python_files 被忽略 (優先序集中在這裡);
    未提供時逐檔讀取-parse-yield,記憶體不同時持有全專案的 AST.
    讀取失敗或語法錯誤的檔案靜默略過.
    """
    if corpus is not None:
        yield from corpus.trees.items()
        return
    for filepath in python_files:
        code = read_file_with_encoding(filepath)
        if not code:
            continue
        with contextlib.suppress(SyntaxError):
            yield filepath, ast.parse(code)
