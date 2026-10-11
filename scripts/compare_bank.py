"""Compare a rebuilt case bank with the committed one.

``bank.json`` (the cases, outcomes and the AI's shown recommendations) must match byte for byte.
``ai_report.json`` holds fitted coefficients and metrics, whose last digits depend on the machine's
floating-point libraries, so its numbers are compared with a relative tolerance of 1e-9.

Usage: ``python scripts/compare_bank.py <committed_dir> <rebuilt_dir>``
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any


def close(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return [f"{path}: keys differ"]
        return [m for k in a for m in close(a[k], b[k], f"{path}.{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: lengths differ"]
        return [m for i, (x, y) in enumerate(zip(a, b, strict=True)) for m in close(x, y, f"{path}[{i}]")]
    if isinstance(a, float) or isinstance(b, float):
        ok = (
            isinstance(a, int | float)
            and isinstance(b, int | float)
            and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
        )
        return [] if ok else [f"{path}: {a} != {b}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def main(committed: Path, rebuilt: Path) -> int:
    problems = []
    if (committed / "bank.json").read_bytes() != (rebuilt / "bank.json").read_bytes():
        problems.append("bank.json differs")
    a = json.loads((committed / "ai_report.json").read_text())
    b = json.loads((rebuilt / "ai_report.json").read_text())
    problems += close(a, b, "ai_report")
    for p in problems[:20]:
        print(p)
    print("bank matches" if not problems else f"{len(problems)} differences")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
