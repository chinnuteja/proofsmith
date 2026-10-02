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
    args = parser.parse_args(argv)

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
