"""Command line entrypoint."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="proofsmith")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="compile and run the sanitizer probes")
    demo = sub.add_parser("demo")
    demo_sub = demo.add_subparsers(dest="demo_command", required=True)
    demo_sub.add_parser("orderd", help="run the orderd deadlock demo")
    report = sub.add_parser("report")
    report_sub = report.add_subparsers(dest="report_command", required=True)
    report_sub.add_parser("build", help="render the static site")
    ledger = sub.add_parser("ledger")
    ledger_sub = ledger.add_subparsers(dest="ledger_command", required=True)
    ledger_sub.add_parser("status", help="print spend, cap, remaining, and live balance")
    agent = sub.add_parser("agent")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    agent_sub.add_parser("smoke", help="live deepseek-flash tool-calling smoke")
    make = sub.add_parser("make-verifier", help="build a verifier bundle for one instance")
    make.add_argument("--instance", required=True, help="path to instance.json")
    make.add_argument("--out", required=True, help="directory for the verifier bundle")
    protocol = sub.add_parser("protocol", help="freeze the experiment before any paid run")
    protocol.add_argument("action", choices=["freeze", "validate"])
    evaluate = sub.add_parser("evaluate", help="run the protocol-bound experiment")
    evaluate.add_argument("--pilot", action="store_true")
    evaluate.add_argument("--track", choices=["all", "A", "B"], default="all")
    evaluate.add_argument("--systems", nargs="+", choices=["b0", "b1", "proofsmith"])
    evaluate.add_argument("--instance-ids", nargs="+")
    evaluate.add_argument("--bundle", help="offline evaluation of one frozen bundle")
    evaluate.add_argument("--instance", help="visible instance JSON for offline evaluation")
    evaluate.add_argument("--hidden", help="hidden fixed-tree JSON for offline evaluation")
    evaluate.add_argument("--out", help="output verdict JSON for offline evaluation")
    sub.add_parser("metrics", help="recompute metrics from frozen-protocol verdicts")
    sub.add_parser("mcp", help="serve make_verifier and verify over stdio (install proofsmith[mcp])")
    benchmark = sub.add_parser("benchmark", help="export a self-contained Track B source package")
    benchmark.add_argument("--out", default="benchmark")
    replay = sub.add_parser("replay", help="evaluate existing frozen bundles without model calls")
    replay.add_argument("--check", action="store_true", help="fail if outcomes differ from the stored verdicts")
    replay.add_argument("--bundle", help="restrict replay to one bundle directory")
    verify = sub.add_parser("verify", help="check a frozen verifier against a local source tree")
    verify.add_argument("--bundle", required=True)
    verify.add_argument("--repo", required=True)
    verify.add_argument("--instance", required=True, help="instance JSON supplying the build recipe")
    verify.add_argument("--n", type=int, default=20)
    report_sub.add_parser("readme", help="generate traceable README and draft outreach")
    args = parser.parse_args(argv)

    if args.command == "mcp":
        from proofsmith.mcp_server import main as serve_mcp
        serve_mcp()
        return

    if args.command == "benchmark":
        from pathlib import Path
        from proofsmith.benchmark import export_benchmark
        print(export_benchmark(Path(args.out)))
        return

    if args.command in {"protocol", "evaluate", "metrics", "replay", "verify"}:
        import json
        from pathlib import Path
        from proofsmith import config
        from proofsmith.eval.protocol import PROTOCOL_PATH, freeze_protocol, validate_protocol
        if args.command == "protocol":
            payload = freeze_protocol() if args.action == "freeze" else json.loads(PROTOCOL_PATH.read_text())
            validate_protocol(payload)
            print(PROTOCOL_PATH)
        elif args.command == "evaluate":
            from proofsmith.eval.runner import atomic_json, run_eval
            if args.bundle:
                if not args.instance or not args.hidden or not args.out:
                    parser.error("offline evaluation needs --bundle, --instance, --hidden and --out")
                from proofsmith.datasets.schema import Instance, HiddenInstance
                from proofsmith.eval.evaluator import evaluate as score
                instance = Instance.model_validate_json(Path(args.instance).read_text())
                hidden = HiddenInstance.model_validate_json(Path(args.hidden).read_text())
                value = score(Path(args.bundle), instance, hidden, config.WORK / "offline-eval").as_dict()
                atomic_json(Path(args.out), value)
            else:
                value = run_eval(args.track, args.systems, args.instance_ids, pilot=args.pilot)
            print(json.dumps(value, indent=2))
        elif args.command == "metrics":
            from proofsmith.eval.runner import write_summary
            print(json.dumps(write_summary(json.loads(PROTOCOL_PATH.read_text())), indent=2))
        elif args.command == "replay":
            from proofsmith.eval.replay import replay_all
            payload = replay_all(check=args.check, only=Path(args.bundle) if args.bundle else None)
            print(json.dumps(payload, indent=2))
            if args.check and not payload["matches"]:
                raise SystemExit(1)
        else:
            from proofsmith.datasets.schema import Instance
            from proofsmith.freeze import verify_bundle
            if args.n < 1:
                raise ValueError("n must be positive")
            instance = Instance.model_validate_json(Path(args.instance).read_text())
            result = verify_bundle(Path(args.bundle), Path(args.repo), instance.build, args.n, config.WORK / "verify")
            print(json.dumps({"build_ok": result.build_ok, "fails": result.fails, "n": result.n,
                              "evidence_kinds": [r.evidence.kind for r in result.runs]}))
            if not result.build_ok or result.fails:
                raise SystemExit(1)
        return

    if args.command == "report" and args.report_command == "readme":
        from proofsmith.report.readme import generate_readme
        generate_readme()
        return

    if args.command == "doctor":
        from proofsmith.toolchain import doctor, write_toolchain_json

        results = doctor()
        path = write_toolchain_json(results)
        for item in results:
            status = "ok" if item.ok else "FAIL"
            print(
                f"{item.name} {item.variant} expected={item.expected_kind} "
                f"observed={item.observed_kind} {status}"
            )
        print(path)
        if not all(item.ok for item in results):
            raise SystemExit(1)
        return

    if args.command == "demo" and args.demo_command == "orderd":
        from proofsmith.demo import run_orderd

        run_orderd()
        return

    if args.command == "report" and args.report_command == "build":
        from proofsmith.config import SITE
        from proofsmith.report.site import build_site

        build_site()
        print(SITE / "index.html")
        return

    if args.command == "ledger" and args.ledger_command == "status":
        from proofsmith.ledger import print_status

        print_status()
        return

    if args.command == "make-verifier":
        from pathlib import Path

        from proofsmith.agent.loop import Budget
        from proofsmith.config import EVAL_MODEL, MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S
        from proofsmith.datasets.schema import Instance
        from proofsmith.ledger import LEDGER_PATH, Ledger
        from proofsmith.llm import LLMClient
        from proofsmith.pipeline import make_verifier

        instance = Instance.model_validate_json(Path(args.instance).read_text(encoding="utf-8"))
        ledger = Ledger(LEDGER_PATH)
        client = LLMClient(EVAL_MODEL, ledger, f"make-{instance.id}")
        client.system_name = "proofsmith"
        result = make_verifier(
            instance,
            client,
            Budget(MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S),
            Path(args.out),
        )
        print(f"status: {result.status}")
        print(f"oracle: {result.oracle}")
        print(f"signature: {result.signature}")
        print(f"reason: {result.reason}")
        print(f"cost_usd: {result.cost_usd:.6f}")
        print(result.bundle_dir or "")
        return

    if args.command == "agent" and args.agent_command == "smoke":
        from proofsmith.agent.smoke import run_smoke

        result = run_smoke()
        summary = result.final.get("summary", "")
        print(f"status: {result.status}")
        print(f"steps: {result.steps}")
        print(f"cost_usd: {result.cost_usd:.6f}")
        print(f"summary: {summary}")
        if result.status != "finished":
            raise SystemExit(1)
        return

    raise SystemExit(2)


if __name__ == "__main__":
    main()
