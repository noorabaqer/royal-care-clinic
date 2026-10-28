"""
formatting.py
=============
Helpers that turn objects into neat console output (headings, key/value
blocks and aligned tables). Keeping presentation here keeps the domain
classes free of printing code.
"""

from typing import Iterable, List, Sequence, Tuple

WIDTH = 78


def heading(title: str, char: str = "=") -> str:
    """A centred title between two rules."""
    rule = char * WIDTH
    return f"\n{rule}\n{title.upper().center(WIDTH)}\n{rule}"


def subheading(title: str) -> str:
    return f"\n--- {title} " + "-" * max(0, WIDTH - len(title) - 5)


def key_values(pairs: Iterable[Tuple[str, object]], indent: int = 2) -> str:
    """Align ``label : value`` pairs."""
    pairs = list(pairs)
    width = max((len(k) for k, _ in pairs), default=0)
    pad = " " * indent
    return "\n".join(f"{pad}{k.ljust(width)} : {v}" for k, v in pairs)


def table(headers: Sequence[str], rows: Sequence[Sequence[object]],
          align_right: Sequence[int] = ()) -> str:
    """Render rows as a simple text table with a header rule.

    ``align_right`` lists column indexes to right-align (useful for money).
    """
    text_rows: List[List[str]] = [[str(c) for c in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in text_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(cells: Sequence[str]) -> str:
        out = []
        for i, cell in enumerate(cells):
            out.append(cell.rjust(widths[i]) if i in align_right else cell.ljust(widths[i]))
        return "  " + " | ".join(out)

    rule = "  " + "-+-".join("-" * w for w in widths)
    lines = [fmt(list(headers)), rule] + [fmt(r) for r in text_rows]
    return "\n".join(lines)
