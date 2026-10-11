from __future__ import annotations

from functools import cache
from typing import Any

import yaml

from declab.paths import CONFIGS


@cache
def study() -> dict[str, Any]:
    return dict(yaml.safe_load((CONFIGS / "study.yaml").read_text(encoding="utf-8")))


def domains() -> dict[str, dict[str, Any]]:
    return dict(study()["domains"])
