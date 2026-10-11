from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from declab import bank as bankmod
from declab.api import create_app
from declab.store import Store


@pytest.fixture(scope="session")
def bank() -> dict[str, Any]:
    """The committed case bank (data/bank/bank.json): no download needed."""
    return bankmod.read()


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "lab.db")


@pytest.fixture
def client(store: Store, bank: dict[str, Any], tmp_path: Path) -> TestClient:
    return TestClient(create_app(store=store, bank=bank, results=tmp_path / "results", static_dir=tmp_path / "dist",
                                 rate_limit=False, sessions=tmp_path / "sessions"))  # fmt: skip
