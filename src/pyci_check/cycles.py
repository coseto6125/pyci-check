"""
循環引用偵測 (Import Cycle Detection).

分析專案中檔案間的匯入關係，找出構成循環引用的路徑。
"""

import os


def find_import_cycles(
    all_imports: list[dict],
    all_relative_imports: list[dict],
    project_dir: str,
    src_dirs: list[str]
) -> list[list[str]]:
    """
    找出專案中的循環引用.

    Args:
        all_imports: 所有絕對匯入資訊
        all_relative_imports: 所有相對匯入資訊
        project_dir: 專案根目錄
        src_dirs: 原始碼目錄 (PYTHONPATH)

    Returns:
        包含路徑環的列表，例如 [["a.py", "b.py", "a.py"]]
    """
    # 1. 建立檔案到模組名的對應，以及模組名到檔案的對應
    file_to_module: dict[str, str] = {}
    module_to_file: dict[str, str] = {}

    # 收集所有本地模組
    from pyci_check.utils import get_exclude_dirs_set, walk_python_files
    python_files = walk_python_files(project_dir, get_exclude_dirs_set())

    # 建立映射
    roots = [project_dir]
    roots.extend(os.path.join(project_dir, s) for s in src_dirs)

    for fp in python_files:

        abs_fp = os.path.abspath(fp)
        # 尋找最短模組名 (最深層的 root)
        best_mod = None
        for root in roots:
            abs_root = os.path.abspath(root)
            if abs_fp.startswith(abs_root):
                rel = os.path.relpath(abs_fp, abs_root)
                mod = rel.replace(os.sep, ".").removesuffix(".py").removesuffix(".__init__")
                if best_mod is None or len(mod) < len(best_mod):
                    best_mod = mod
        if best_mod:
            file_to_module[abs_fp] = best_mod
            module_to_file[best_mod] = abs_fp

    # 2. 建立匯入圖 (Adjacency List)
    graph: dict[str, set[str]] = {fp: set() for fp in file_to_module}

    # 處理絕對匯入
    for imp in all_imports:
        src_file = os.path.abspath(imp["file"])
        if src_file not in graph:
            continue

        target_mod = imp["module"]
        # 尋找匹配的本地檔案 (處理 dotted submodules)
        # 例如 import a.b.c，可能是 a/b/c.py 或 a/b/__init__.py
        current = target_mod
        while current:
            if current in module_to_file:
                graph[src_file].add(module_to_file[current])
                break
            if "." not in current:
                break
            current = current.rsplit(".", 1)[0]

    # 處理相對匯入
    for imp in all_relative_imports:
        src_file = os.path.abspath(imp["file"])
        if src_file not in graph:
            continue

        level = imp["level"]
        module = imp["module"]

        # 解析相對路徑
        src_dir = os.path.dirname(src_file)
        target_dir = src_dir
        for _ in range(level - 1):
            target_dir = os.path.dirname(target_dir)

        # 拼接模組名
        if module == ".":
            # from . import x -> target is the current dir's __init__.py
            potential_file = os.path.join(target_dir, "__init__.py")
        else:
            potential_file = os.path.join(target_dir, *module.split(".")) + ".py"
            if not os.path.exists(potential_file):
                potential_file = os.path.join(target_dir, *module.split("."), "__init__.py")

        abs_target = os.path.abspath(potential_file)
        if abs_target in graph:
            graph[src_file].add(abs_target)

    # 3. 尋找環 (DFS)
    cycles = []
    visited = set()
    stack = []
    stack_set = set()

    def dfs(node: str):
        visited.add(node)
        stack.append(node)
        stack_set.add(node)

        for neighbor in graph.get(node, []):
            if neighbor == node: # 排除自我引用 (雖然在 Python 很少見)
                continue
            if neighbor in stack_set:
                # 發現環
                idx = stack.index(neighbor)
                cycle = [*stack[idx:], neighbor]
                cycles.append(cycle)
            elif neighbor not in visited:
                dfs(neighbor)

        stack.pop()
        stack_set.remove(node)

    for node in graph:
        if node not in visited:
            dfs(node)

    return cycles
