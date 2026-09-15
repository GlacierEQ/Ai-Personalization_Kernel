"""``apk`` command-line interface.

Subcommands:
- ``apk validate <path>``          validate JSON/JSONL data against schemas
- ``apk replay --cases <path>``    run regression replay (CI hard gate)
- ``apk boot --demo``              run the 12-step boot contract on bundled demo data
- ``apk metrics <eval_run.json>``  pretty-print an eval run's metrics
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

FILE_SCHEMA_MAP: dict[str, str] = {
    "user_model.json": "user-model.schema.json",
    "policy_weights.json": "policy-weights.schema.json",
    "corrections.jsonl": "correction.schema.json",
    "regression_cases.jsonl": "regression-case.schema.json",
    "preferences.jsonl": "memory-object.schema.json",
    "successful_strategies.jsonl": "memory-object.schema.json",
    "failed_strategies.jsonl": "memory-object.schema.json",
    "authority_rules.jsonl": "memory-object.schema.json",
}


def _repo_root() -> Path:
    # src/apk/cli.py -> src/apk -> src -> repo root
    return Path(__file__).resolve().parents[2]


def _schemas_dir() -> Path:
    candidates = [_repo_root() / "schemas", Path.cwd() / "schemas"]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("could not locate schemas/ directory")


def _data_dir() -> Path:
    candidates = [_repo_root() / "data", Path.cwd() / "data"]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("could not locate data/ directory")


def _load_jsonschema():
    try:
        import jsonschema  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised via CLI error path
        raise SystemExit(
            "jsonschema is required for `apk validate`; install the dev extra: "
            "pip install -e .[dev]"
        ) from exc
    return jsonschema


def _validate_file(path: Path, schemas_dir: Path) -> list[str]:
    schema_name = FILE_SCHEMA_MAP.get(path.name)
    if schema_name is None:
        return [f"{path}: no schema mapping known for filename {path.name!r}"]
    jsonschema = _load_jsonschema()
    schema = json.loads((schemas_dir / schema_name).read_text(encoding="utf-8"))
    errors: list[str] = []
    if path.suffix == ".jsonl":
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                jsonschema.validate(obj, schema)
            except Exception as exc:  # noqa: BLE001 - surfaced as validation error text
                errors.append(f"{path}:{lineno}: {exc}")
    else:
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            jsonschema.validate(obj, schema)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")
    return errors


def cmd_validate(args: argparse.Namespace) -> int:
    schemas_dir = Path(args.schemas) if args.schemas else _schemas_dir()
    target = Path(args.path)
    files = [target] if target.is_file() else sorted(
        p for p in target.iterdir() if p.name in FILE_SCHEMA_MAP
    )
    if not files:
        print(f"no recognized data files found under {target}")
        return 1
    all_errors: list[str] = []
    for f in files:
        errs = _validate_file(f, schemas_dir)
        if errs:
            all_errors.extend(errs)
        else:
            print(f"OK   {f}")
    for e in all_errors:
        print(f"FAIL {e}", file=sys.stderr)
    if all_errors:
        print(f"\n{len(all_errors)} validation error(s)")
        return 1
    print(f"\nall {len(files)} file(s) valid")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    from apk.policy import PolicyEngine
    from apk.replay import ExperienceReplay

    weights_path = Path(args.weights) if args.weights else _data_dir() / "policy_weights.json"
    policy = PolicyEngine.from_file(weights_path)
    replay = ExperienceReplay(policy)
    run = replay.run(args.cases)
    # stdout carries only the machine-readable report (so `apk replay > eval_run.json`
    # produces valid JSON); human-readable summary goes to stderr.
    print(json.dumps(run.to_dict(), indent=2, default=str))
    if run.regression_reintroduction_count > 0:
        print(
            f"REGRESSION GATE FAILED: {run.regression_reintroduction_count} case(s) reintroduced "
            "a previously corrected failure",
            file=sys.stderr,
        )
        return 1
    print(f"regression gate passed: {run.passed_cases}/{run.total_cases} cases", file=sys.stderr)
    return 0


def cmd_boot(args: argparse.Namespace) -> int:
    from apk.boot import BootContract, BootContractError
    from apk.policy import PolicyEngine

    data_dir = Path(args.data_dir) if args.data_dir else _data_dir()
    user_model_path = data_dir / "user_model.json"
    corrections_path = data_dir / "corrections.jsonl"
    policy = PolicyEngine.from_file(data_dir / "policy_weights.json")
    contract = BootContract(user_model_path, corrections_path, policy)
    try:
        receipt = contract.run(
            message=args.message
            or "Continue the ongoing repository work and keep applying my known preferences.",
            claims=[{"content": "Our kernel uses the always-active user model.", "claim_type": "project_meaning"}],
            triggers={"continuity", "correction_overlap"},
            relevant_context_exists=True,
            context_retrieved=False,
        )
    except BootContractError as exc:
        print(f"BOOT CONTRACT FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt.to_dict(), indent=2, default=str))
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.eval_run).read_text(encoding="utf-8"))
    metrics = data.get("metrics", {})
    print(f"{'metric':40s} {'value':>10s}  status")
    print("-" * 70)
    for name, m in metrics.items():
        if isinstance(m, dict) and m.get("not_computable"):
            print(f"{name:40s} {'--':>10s}  not_computable ({m.get('reason', '')})")
        elif isinstance(m, dict):
            print(f"{name:40s} {str(m.get('value')):>10s}  target={m.get('target')}")
        else:
            print(f"{name:40s} {str(m):>10s}")
    print("-" * 70)
    print(f"total_cases={data.get('total_cases')} passed={data.get('passed_cases')} "
          f"failed={data.get('failed_cases')} passed_gate={data.get('passed')}")
    return 0 if data.get("passed", True) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apk", description="Ai-Personalization_Kernel CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate JSON/JSONL data files against schemas")
    p_validate.add_argument("path", help="file or directory to validate")
    p_validate.add_argument("--schemas", help="override schemas directory")
    p_validate.set_defaults(func=cmd_validate)

    p_replay = sub.add_parser("replay", help="run regression replay against the policy engine")
    p_replay.add_argument("--cases", required=True, help="path to regression_cases.jsonl")
    p_replay.add_argument("--weights", help="override policy_weights.json path")
    p_replay.set_defaults(func=cmd_replay)

    p_boot = sub.add_parser("boot", help="run the 12-step boot contract")
    p_boot.add_argument("--demo", action="store_true", help="run against bundled demo data")
    p_boot.add_argument("--data-dir", dest="data_dir", help="override data directory")
    p_boot.add_argument("--message", help="override the demo user message")
    p_boot.set_defaults(func=cmd_boot)

    p_metrics = sub.add_parser("metrics", help="pretty-print an eval_run.json report")
    p_metrics.add_argument("eval_run", help="path to an eval_run.json produced by `apk replay`")
    p_metrics.set_defaults(func=cmd_metrics)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
