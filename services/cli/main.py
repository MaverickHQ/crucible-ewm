from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys

from services.cli.check import run_check
from services.cli.cost import apply_cost, set_cost_profile, show_cost
from services.cli.evaluate import experiment_evaluate_placeholder, run_evaluate_cmd
from services.cli.mode import set_env, set_mode, set_target, show_env, show_mode, show_target
from services.cli.runs import runs_latest, runs_tail


def _version_string() -> str:
    try:
        ver = importlib.metadata.version("beyond-tokens")
    except importlib.metadata.PackageNotFoundError:
        ver = "dev"
    return f"beyond-tokens {ver}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ewm")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version")
    sub.add_parser("check")

    mode_parser = sub.add_parser("mode")
    mode_sub = mode_parser.add_subparsers(dest="mode_cmd", required=True)
    mode_show = mode_sub.add_parser("show")
    mode_show.add_argument("--raw", action="store_true", help="Output raw value without label")
    mode_set = mode_sub.add_parser("set")
    mode_set.add_argument("value", choices=["local", "aws", "both"])

    target_parser = sub.add_parser("target")
    target_sub = target_parser.add_subparsers(dest="target_cmd", required=True)
    target_show = target_sub.add_parser("show")
    target_show.add_argument("--raw", action="store_true", help="Output raw value without label")
    target_set = target_sub.add_parser("set")
    target_set.add_argument("value", choices=["local", "aws", "both"])

    env_parser = sub.add_parser("env")
    env_sub = env_parser.add_subparsers(dest="env_cmd", required=True)
    env_show = env_sub.add_parser("show")
    env_show.add_argument("--raw", action="store_true", help="Output raw value without label")
    env_set = env_sub.add_parser("set")
    env_set.add_argument("value", choices=["paper", "prod"])

    cost_parser = sub.add_parser("cost")
    cost_sub = cost_parser.add_subparsers(dest="cost_cmd", required=True)
    cost_sub.add_parser("show")
    cost_set = cost_sub.add_parser("set")
    cost_set.add_argument("--profile", required=True, choices=["integration", "paper", "prod"])
    cost_set.add_argument("--steps", type=int)
    cost_set.add_argument("--tool-calls", type=int)
    cost_set.add_argument("--model-calls", type=int)
    cost_set.add_argument("--memory-ops", type=int)
    cost_set.add_argument("--memory-bytes", type=int)
    cost_apply = cost_sub.add_parser("apply")
    cost_apply.add_argument("--yes", action="store_true")

    runs_parser = sub.add_parser("runs")
    runs_sub = runs_parser.add_subparsers(dest="runs_cmd", required=True)
    runs_latest_parser = runs_sub.add_parser("latest")
    runs_latest_parser.add_argument("--raw", action="store_true", help="Output raw JSON")
    runs_latest_parser.add_argument(
        "--json", action="store_true", help="Output pretty-printed JSON"
    )
    runs_tail_parser = runs_sub.add_parser("tail")
    runs_tail_parser.add_argument("--n", type=int, default=10)

    # Run subcommand
    run_parser = sub.add_parser("run")
    run_sub = run_parser.add_subparsers(dest="run_cmd", required=True)

    # run evaluate
    run_evaluate_parser = run_sub.add_parser("evaluate")
    run_evaluate_parser.add_argument(
        "--artifacts-dir",
        required=True,
        help=(
            "If --run-id is provided, this is the root artifacts directory containing <run-id>/. "
            "If --run-id is omitted, this is the run artifact directory itself."
        ),
    )
    run_evaluate_parser.add_argument(
        "--run-id",
        help="Evaluate a specific run by ID under the artifacts root directory.",
    )
    run_evaluate_parser.add_argument(
        "--json", action="store_true", help="Print full evaluation JSON to stdout"
    )

    # Experiment subcommand
    experiment_parser = sub.add_parser("experiment")
    experiment_sub = experiment_parser.add_subparsers(dest="experiment_cmd", required=True)

    # experiment run
    experiment_run_parser = experiment_sub.add_parser("run")
    experiment_run_parser.add_argument(
        "config_path", help="Path to experiment config file (JSON or YAML)"
    )
    experiment_run_parser.add_argument(
        "--target", choices=["local", "aws"], help="Execution target (overrides config)"
    )

    # experiment evaluate (R22)
    experiment_evaluate_parser = experiment_sub.add_parser("evaluate")
    experiment_evaluate_parser.add_argument(
        "--experiment-dir",
        required=True,
        help="Path to experiment directory for evaluation.",
    )
    experiment_evaluate_parser.add_argument(
        "--json", action="store_true", help="Print full evaluation JSON to stdout"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "version":
            print(_version_string())
            return 0

        if args.command == "mode":
            if args.mode_cmd == "show":
                print(show_mode(raw=getattr(args, "raw", False)))
                return 0
            print(set_mode(args.value))
            return 0

        if args.command == "target":
            if args.target_cmd == "show":
                print(show_target(raw=getattr(args, "raw", False)))
                return 0
            print(set_target(args.value))
            return 0

        if args.command == "env":
            if args.env_cmd == "show":
                print(show_env(raw=getattr(args, "raw", False)))
                return 0
            print(set_env(args.value))
            return 0

        if args.command == "check":
            return run_check()

        if args.command == "cost":
            if args.cost_cmd == "show":
                print(json.dumps(show_cost(), indent=2, sort_keys=True))
                return 0
            if args.cost_cmd == "set":
                result = set_cost_profile(
                    args.profile,
                    steps=args.steps,
                    tool_calls=args.tool_calls,
                    model_calls=args.model_calls,
                    memory_ops=args.memory_ops,
                    memory_bytes=args.memory_bytes,
                )
                print(json.dumps(result, indent=2, sort_keys=True))
                return 0
            result = apply_cost(yes=args.yes)
            if result["cost_profile"] == "prod":
                print("WARNING: applying PROD cost profile")
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        if args.command == "runs":
            if args.runs_cmd == "latest":
                return runs_latest(raw=args.raw, json_output=args.json)
            return runs_tail(args.n)

        if args.command == "run":
            if args.run_cmd == "evaluate":
                return run_evaluate_cmd(args)

        if args.command == "experiment":
            # Lazy import to avoid requiring certifi for non-experiment commands
            from services.cli.experiment import experiment_run

            if args.experiment_cmd == "run":
                return experiment_run(args.config_path, target=args.target)
            if args.experiment_cmd == "evaluate":
                return experiment_evaluate_placeholder(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
