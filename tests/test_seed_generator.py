"""Tests for the deterministic seed generator (scripts/generate_seed_data.py).

The generator is the source of truth for data/; these tests pin the
invariants CI relies on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate_seed_data.py"

sys.path.insert(0, str(REPO_ROOT))


def _run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_check_passes_on_committed_data() -> None:
    result = _run_generator("--check")
    assert result.returncode == 0, result.stderr


def test_check_fails_on_drift(tmp_path: Path) -> None:
    result = _run_generator("--data-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr
    tampered = tmp_path / "preferences.jsonl"
    lines = tampered.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["description"] = "HAND-EDITED"
    lines[0] = json.dumps(rec, sort_keys=True)
    tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = _run_generator("--check", "--data-dir", str(tmp_path))
    assert result.returncode == 1
    assert "drifted" in result.stderr


def test_check_fails_on_extra_file(tmp_path: Path) -> None:
    result = _run_generator("--data-dir", str(tmp_path))
    assert result.returncode == 0
    (tmp_path / "rogue.jsonl").write_text("{}\n", encoding="utf-8")
    result = _run_generator("--check", "--data-dir", str(tmp_path))
    assert result.returncode == 1
    assert "rogue.jsonl" in result.stderr


def test_regeneration_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    assert _run_generator("--data-dir", str(first)).returncode == 0
    assert _run_generator("--data-dir", str(second)).returncode == 0
    for path_a in sorted(first.iterdir()):
        assert path_a.read_bytes() == (second / path_a.name).read_bytes(), path_a.name


def test_correction_chains_have_coherent_supersession() -> None:
    from scripts.generate_seed_data import build_files

    files = build_files()
    records = [
        json.loads(line)
        for line in files["corrections.jsonl"].decode("utf-8").splitlines()
    ]
    by_id = {r["id"]: r for r in records}
    assert len(by_id) == len(records), "duplicate correction ids"
    for rec in records:
        for target in rec["supersedes"]:
            assert target in by_id, f"{rec['id']} supersedes unknown {target}"
            assert rec["id"] in by_id[target]["superseded_by"]
        for target in rec["superseded_by"]:
            assert target in by_id
            assert rec["id"] in by_id[target]["supersedes"]
        assert rec["source_refs"] == sorted(rec["source_refs"])


def test_chain_ids_match_ledger_formula() -> None:
    """Seed chain ids must equal CorrectionLedger.record's deterministic ids."""
    from apk.corrections import deterministic_id
    from scripts.generate_seed_data import T

    assert deterministic_id(
        "corr", "answer_before_context_recovery", "global", T["a1"]
    ) == "corr_43866d3a61159197"
    assert deterministic_id(
        "corr", "answer_before_context_recovery", "global", T["a2"], "2"
    ) == "corr_aafe8f6f7be14898"


def test_regression_cases_embed_chain_heads() -> None:
    """Embedded corrections in regression cases must be the chain heads,
    not stale hand-copies."""
    from scripts.generate_seed_data import build_files

    files = build_files()
    corrections = {
        r["id"]: r
        for r in (json.loads(l) for l in files["corrections.jsonl"].decode().splitlines())
    }
    cases = [
        json.loads(l) for l in files["regression_cases.jsonl"].decode().splitlines()
    ]
    for case in cases[1:]:  # case 0 has no active corrections by design
        for embedded in case["state"]["active_corrections"]:
            live = corrections[embedded["id"]]
            assert not live["superseded_by"], (
                f"case {case['failure_class']} embeds non-head revision {embedded['id']}"
            )
            assert embedded == live
