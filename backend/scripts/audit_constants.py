# -*- coding: utf-8 -*-
"""P0.6/P8 · Sweep số + CI gate. Quét literal số trong backend/src/: mỗi hằng phải hoặc
thuộc whitelist kỹ thuật, hoặc có comment nguồn (`# nguồn:`) trên chính dòng đó. Kèm 2
CI gate: không `_ground_truth` và không `import pandas` trong runtime.

Chạy: `python backend/scripts/audit_constants.py`  (exit 1 nếu có vi phạm).
ponytail: heuristic dòng-comment (không phân tích luồng); nâng lên gắn nguồn theo AST-node
nếu sau này cần chặt hơn.
"""
from __future__ import annotations

import ast
import sys
import tokenize
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):        # Windows cp1252 -> UTF-8 cho tiếng Việt
    sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(__file__).resolve().parent.parent / "src"

# Số kỹ thuật miễn khai nguồn: index/sentinel, làm tròn nghìn, %/tỉ lệ cơ bản, HTTP code,
# kích thước golden cố định (8 ga / 7 leg / 40 ghế) — bản thân là spec kịch bản (§2 nguồn 5).
WHITELIST = {0, 1, -1, 2, 3, 100, 1000,
             200, 201, 400, 404, 409, 410, 422, 503,
             7, 8, 40}
SOURCE_TAGS = ("# nguồn:", "# nguon:", "# ponytail:", "# spec")


def _comment_lines(path: Path) -> dict[int, str]:
    """map lineno -> nội dung comment trên dòng đó (nếu có)."""
    out: dict[int, str] = {}
    with path.open("rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            if tok.type == tokenize.COMMENT:
                out[tok.start[0]] = tok.string
    return out


def _has_source_tag(comment: str | None) -> bool:
    return bool(comment) and any(t in comment.lower() for t in SOURCE_TAGS)


def _skip_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """Dòng của self-check (không phải runtime) -> miễn quét: hàm demo/_demo/test_*
    và block `if __name__ == "__main__"`."""
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and (
                node.name in ("demo", "_demo") or node.name.startswith("test")):
            ranges.append((node.lineno, node.end_lineno or node.lineno))
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) \
                and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__":
            ranges.append((node.lineno, node.end_lineno or node.lineno))
    return ranges


def audit_file(path: Path) -> list[tuple[int, str]]:
    src = path.read_text(encoding="utf-8")
    comments = _comment_lines(path)
    tree = ast.parse(src, filename=str(path))
    skip = _skip_ranges(tree)
    bad: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and any(a <= getattr(node, "lineno", -1) <= b for a, b in skip):
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            val = node.value
            if val in WHITELIST or (isinstance(val, float) and float(val).is_integer()
                                    and int(val) in WHITELIST):
                continue
            if _has_source_tag(comments.get(node.lineno)):
                continue
            bad.append((node.lineno, repr(val)))
    return bad


def grep_gate(needle: str, label: str) -> list[str]:
    hits = []
    for p in SRC.rglob("*.py"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if needle in line:
                hits.append(f"{p.relative_to(SRC.parent)}:{i}: {line.strip()}")
    return hits


def main() -> int:
    violations = 0
    print("=== CI gate: _ground_truth cấm runtime ===")
    gt = grep_gate("_ground_truth", "_ground_truth")
    if gt:
        violations += len(gt)
        print("\n".join(gt))
    else:
        print("OK (rỗng)")

    print("\n=== CI gate: import pandas cấm trong backend/src ===")
    pd = grep_gate("import pandas", "pandas")
    if pd:
        violations += len(pd)
        print("\n".join(pd))
    else:
        print("OK (rỗng)")

    print("\n=== Sweep literal số không nguồn ===")
    total = 0
    for p in sorted(SRC.rglob("*.py")):
        bad = audit_file(p)
        if bad:
            total += len(bad)
            for ln, val in bad:
                print(f"{p.relative_to(SRC.parent)}:{ln}: literal {val} thiếu `# nguồn:`")
    if total == 0:
        print("OK (mọi literal có nguồn hoặc thuộc whitelist)")
    violations += total

    print(f"\nTỔNG vi phạm: {violations}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
