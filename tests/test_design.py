from __future__ import annotations

from collections import Counter
from typing import Any

from declab import design
from declab.config import study


def test_allocation_is_blocked_balanced_and_reproducible() -> None:
    a = design.allocation("human", 60)
    size = study()["block_size"]
    for k in range(0, 60, size):
        assert Counter(a[k : k + size]) == {"A": size // 3, "B": size // 3, "C": size // 3}
    assert a == design.allocation("human", 60)
    assert design.allocation_hash("human") == design.allocation_hash("human")


def test_strata_have_independent_allocations() -> None:
    assert design.allocation("model:qwen3-4b", 30) != design.allocation("model:phi-4-mini", 30)
    assert design.stratum_name("model", "qwen3-4b") == "model:qwen3-4b"
    assert design.stratum_name("human", None) == "human"


def test_plan_has_balanced_cases_per_domain_and_outcome(bank: dict[str, Any]) -> None:
    cases = {c["id"]: c for c in bank["cases"]}
    items = design.plan(bank, "human", 0, attention=True)
    tasks = [i for i in items if i["phase"] == "task"]
    assert [i["phase"] for i in items[:2]] == ["practice", "practice"]
    assert len(tasks) == 24 and len({t["case"] for t in tasks}) == 24
    per = Counter((cases[t["case"]]["domain"], cases[t["case"]]["outcome"]) for t in tasks)
    assert set(per.values()) == {4} and len(per) == 6


def test_attention_checks_for_people_only(bank: dict[str, Any]) -> None:
    human = design.plan(bank, "human", 3, attention=True)
    model = design.plan(bank, "model:qwen3-4b", 3, attention=False)
    att = [i for i in human if i["phase"] == "attention"]
    assert [a["case"] for a in att] == ["attention-1", "attention-2"]
    assert len(human) == 28 and len(model) == 26
    assert not any(i["phase"] == "attention" for i in model)
    first = human.index(att[0])
    assert first >= 2 + 4  # never among the first cases


def test_plans_differ_between_participants(bank: dict[str, Any]) -> None:
    assert design.plan(bank, "human", 0, True) != design.plan(bank, "human", 1, True)
    assert design.plan(bank, "human", 5, True) == design.plan(bank, "human", 5, True)
