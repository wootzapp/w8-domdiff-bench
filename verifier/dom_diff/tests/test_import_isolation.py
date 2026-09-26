import ast
from pathlib import Path


def test_source_has_no_old_or_sibling_imports():
    root = Path(__file__).parents[1] / "src"
    forbidden = {
        "webeval", "fara", "dom_diff_text", "microsoft_verifier",
        "scripts", "benchmarks", "ms_paper_execution",
    }
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".", 1)[0]}
            else:
                continue
            assert not names.intersection(forbidden), (path, names)
