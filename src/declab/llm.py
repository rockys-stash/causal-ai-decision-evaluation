"""Model participants: local open-weights language models deciding through the same API as people.

They read the same item a person's screen shows, rendered as text (``render``), and answer with a
schema-constrained JSON reply. Models are GGUF files pinned by SHA-256 (``configs/models.yaml``),
shared with the portfolio's other projects when ``DECLAB_MODEL_DIR`` points at a copy.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any, cast

import yaml

from declab.data import sha256
from declab.paths import CONFIGS, MODELS

SYSTEM = (
    "You are a participant in a decision-making study. Each task is a real past case from a business. "
    "Read the case and make the decision you think is right; the correct answer is what actually happened. "
    "Half of all cases in this study had each outcome. Then say how confident you are that your decision "
    "is right, from 50 (a guess) to 100 (certain). Reply with JSON only."
)


def config() -> dict[str, Any]:
    return dict(yaml.safe_load((CONFIGS / "models.yaml").read_text(encoding="utf-8")))


def fetch_models() -> list[Path]:
    cfg = config()
    MODELS.mkdir(exist_ok=True)
    out = []
    for m in cfg["models"].values():
        path = MODELS / m["file"]
        shared = Path(os.environ.get("DECLAB_MODEL_DIR", "/nonexistent")) / m["file"]
        if not path.exists() and shared.exists():
            path.symlink_to(shared)
        if not path.exists():
            tmp = path.with_suffix(".part")
            with urllib.request.urlopen(m["url"], timeout=120) as r, tmp.open("wb") as f:
                shutil.copyfileobj(r, f)
            tmp.replace(path)
        if sha256(path) != m["sha256"]:
            raise ValueError(f"{path.name}: checksum does not match configs/models.yaml; delete it and retry")
        out.append(path)
    return out


def render(item: dict[str, Any]) -> str:
    """The item as text: what a person in this arm sees on screen."""
    lines = [f"Task {item['index'] + 1} of {item['total']}: {item['domain_label']}", ""]
    lines += [f"- {f['label']}: {f['value']}" for f in item["card"]]
    ai = item.get("ai")
    if ai:
        lines += ["", f"AI recommendation: {ai['label']}"]
        if "confidence" in ai:
            lines.append(f"AI confidence (calibrated: of cases where it says {round(100 * ai['confidence'])}%, about that many are right): "
                         f"{round(100 * ai['confidence'])}%")  # fmt: skip
            ex = ai["explanation"]
            for key, lab in (("towards_positive", ex["positive_label"]), ("towards_negative", ex["negative_label"])):
                if ex[key]:
                    lines.append(
                        f"Factors pointing to {lab}: "
                        + "; ".join(f"{x['label']} = {x['value']} ({x['strength']})" for x in ex[key])
                    )
    opts = " or ".join(f'"{o["decision"]}"' for o in item["options"])
    lines += ["", f"Question: {item['question']}", f'Answer as JSON: {{"decision": {opts}, "confidence": 50 to 100}}']
    return "\n".join(lines)


def schema(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": {"decision": {"type": "string", "enum": [o["decision"] for o in item["options"]]},
                                             "confidence": {"type": "integer"}},
            "required": ["decision", "confidence"]}  # fmt: skip


class ModelParticipant:
    """One model participant: a loaded model plus a participant seed; logs every call."""

    def __init__(self, name: str, threads: int | None = None) -> None:
        from llama_cpp import Llama

        cfg = config()
        m = cfg["models"][name]
        path = MODELS / m["file"]
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing: run `make models`")
        self.name, self.label, self.sha256 = name, m["label"], m["sha256"]
        n = threads or int(os.environ.get("DECLAB_LLM_THREADS", cfg["threads"]))
        self.llm = Llama(
            model_path=str(path), n_ctx=cfg["n_ctx"], n_threads=n, n_threads_batch=n, verbose=False, seed=0
        )
        self.temperature = float(cfg["temperature"])
        self.calls: list[dict[str, Any]] = []
        self.seed = 0

    def _seed(self, *parts: object) -> int:
        return int.from_bytes(hashlib.sha256(json.dumps([self.seed, *parts]).encode()).digest()[:4], "big")

    def choose(self, item: dict[str, Any], arm: str) -> tuple[str | None, int | None, int | None]:
        """A decision, or (None, None, ms) when four replies in a row are invalid (recorded as missing)."""
        prompt = render(item)
        options = {o["decision"] for o in item["options"]}
        for attempt in range(4):
            seed = self._seed(item["case_id"], item["index"], attempt)
            t0 = time.perf_counter()
            self.llm.set_seed(seed)
            out = cast(dict[str, Any], self.llm.create_chat_completion(
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                response_format={"type": "json_object", "schema": schema(item)},
                temperature=self.temperature, top_p=0.95, seed=seed, max_tokens=40))  # fmt: skip
            text = str(out["choices"][0]["message"]["content"] or "")
            ms = int((time.perf_counter() - t0) * 1000)
            try:
                reply = json.loads(text)
                decision, conf = str(reply["decision"]), int(reply["confidence"])
                valid = decision in options and 50 <= conf <= 100
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                decision, conf, valid = "", 0, False
            self.calls.append({"case": item["case_id"], "index": item["index"], "attempt": attempt, "seed": seed,
                               "reply": text, "valid": valid, "ms": ms})  # fmt: skip
            if valid:
                return decision, conf, ms
        return None, None, sum(c["ms"] for c in self.calls[-4:])
