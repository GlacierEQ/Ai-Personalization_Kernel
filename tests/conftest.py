from __future__ import annotations

import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_DATA_DIR = REPO_ROOT / "data"


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """A private copy of the seed data/ directory for a single test."""
    dest = tmp_path / "data"
    shutil.copytree(SEED_DATA_DIR, dest)
    return dest


@pytest.fixture()
def user_model(tmp_data_dir: Path):
    from apk.user_model import UserModel

    return UserModel.load(
        tmp_data_dir / "user_model.json",
        corrections_path=tmp_data_dir / "corrections.jsonl",
    )


@pytest.fixture()
def policy_engine(tmp_data_dir: Path):
    from apk.policy import PolicyEngine

    return PolicyEngine.from_file(tmp_data_dir / "policy_weights.json")


@pytest.fixture()
def correction_ledger(tmp_data_dir: Path):
    from apk.corrections import CorrectionLedger

    return CorrectionLedger(tmp_data_dir / "corrections.jsonl")


@pytest.fixture()
def empty_store(tmp_path: Path):
    from apk.store import JsonlStore

    return JsonlStore(tmp_path / "ledger.jsonl")
