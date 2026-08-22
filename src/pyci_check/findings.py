"""
掃描結果的統一契約 (Finding) 與輸出.

所有掃描器 (signature / side_effects / deadcode / ...) 都回傳 list[Finding];
顯示格式 (相對路徑、行號、訊息) 集中在這個 module,CLI wrapper 只負責呼叫.
"""

from dataclasses import dataclass
from typing import Literal

from pyci_check.utils import safe_relpath


@dataclass(frozen=True, slots=True)
class Finding:
    """
    單一掃描發現.

    Attributes:
        file: 檔案路徑 (掃描時的路徑原樣保留)
        line: 行號
        message: 完整原因描述;可含換行以呈現多行細節
        severity: "error" 使 wrapper 回傳非零 exit code;"warning" 僅提示
    """

    file: str
    line: int
    message: str
    severity: Literal["error", "warning"] = "warning"


def has_errors(findings: list[Finding]) -> bool:
    """是否存在 severity="error" 的發現;wrapper 的 exit code 由這裡決定."""
    return any(f.severity == "error" for f in findings)


def render_findings(findings: list[Finding], project_dir: str) -> list[str]:
    """把 Finding 轉成 CLI 輸出行;相對路徑的計算集中在這裡."""
    return [f"  - {safe_relpath(f.file, project_dir)}:{f.line} -> {f.message}" for f in findings]
