"""Command line entry points for Codex-only, real-data Reddit strategy research."""

import argparse
import json
from pathlib import Path

from .collection import Reddit, read_posts
from .config import configure
from .security import error_reason


def add_translation_arguments(parser, *, needs_posts=False, needs_prices=False):
    if needs_posts:
        parser.add_argument("posts", help="real local post JSON/JSONL with source provenance")
    parser.add_argument(
        "--code-config", help="fixed eligible universe, data frequency, costs and assumptions"
    )
    parser.add_argument(
        "--prices", required=needs_prices, help="real CSV or exact-universe directory with metadata"
    )
    parser.add_argument("--max-model-calls", type=int, default=6)
    parser.add_argument("--model", help="optional installed-Codex model override")
    parser.add_argument(
        "--hypotheses", action="store_true", help="allow only declared source-inspired assumptions"
    )


def make_parser():
    parser = argparse.ArgumentParser(description="Codex-powered, real-data Reddit strategy research")
    sub = parser.add_subparsers(dest="command", required=True)

    link = sub.add_parser("link", help="fetch one approved Reddit post, translate it and backtest it")
    link.add_argument("url")
    add_translation_arguments(link, needs_prices=True)
    link.add_argument("--out", default="runs/custom-code")

    discover = sub.add_parser(
        "discover", help="autonomously collect, translate and test eligible Reddit posts"
    )
    discover.add_argument("--subreddit", default="algotrading")
    discover.add_argument("--limit", type=int, default=20)
    discover.add_argument("--feeds", default="new,top", help="comma-separated: new,top,hot")
    discover.add_argument("--search", action="append", help="repeatable topic search")
    discover.add_argument("--max-reddit-requests", type=int, default=8)
    discover.add_argument("--time-filter", default="year")
    discover.add_argument(
        "--collect-only", action="store_true", help="save a bounded candidate batch; no model calls"
    )
    discover.add_argument("--output-posts", default="data/discovered-posts.json")
    add_translation_arguments(discover)
    discover.add_argument("--out", default="runs/custom-code")

    imported = sub.add_parser("import", help="translate and test a real locally imported post batch")
    add_translation_arguments(imported, needs_posts=True, needs_prices=True)
    imported.add_argument("--out", default="runs/custom-code")

    extract = sub.add_parser("extract", help="translate and independently review code without market data")
    add_translation_arguments(extract, needs_posts=True)
    extract.add_argument("--out", default="data/generated-code")

    inspect = sub.add_parser("inspect", help="Codex source-faithfulness audit without execution")
    inspect.add_argument("posts")
    inspect.add_argument("--out", default="runs/source-audits")
    inspect.add_argument("--max-model-calls", type=int, default=2)
    inspect.add_argument("--model", help="optional installed-Codex model override")

    codegen = sub.add_parser(
        "generate-code", help="generate and review custom Python from local source imports"
    )
    codegen.add_argument("posts")
    codegen.add_argument("--config", required=True)
    codegen.add_argument("--prices", help="optionally run reviewed candidates immediately on real data")
    codegen.add_argument("--hypotheses", action="store_true")
    codegen.add_argument("--max-model-calls", type=int, default=6)
    codegen.add_argument("--model", help="optional installed-Codex model override")
    codegen.add_argument("--out", default="data/generated-code")

    custom = sub.add_parser("run-code", help="run custom Python in the verified OS sandbox on real data")
    custom.add_argument("source")
    custom.add_argument("--config", required=True)
    custom.add_argument("--prices", required=True)
    custom.add_argument("--out", default="runs/custom-code")
    sub.add_parser("check-code-sandbox", help="exercise file/network/process isolation with harmless probes")
    sub.add_parser("check-access", help="show Codex and autonomous-discovery readiness without values")
    prices = sub.add_parser("fetch-prices", help="download real daily US stock/ETF bars; no invented data")
    prices.add_argument("--symbol", default="SPY")
    prices.add_argument("--symbols", nargs="+", help="explicit real stock/ETF basket, at most 50")
    prices.add_argument("--start", required=True, help="inclusive YYYY-MM-DD")
    prices.add_argument("--end", required=True, help="exclusive YYYY-MM-DD")
    prices.add_argument("--out", default="data/market")
    return parser


def generate_batch(posts, config_path, out, max_calls, model, hypotheses, prices=None, run_out=None):
    from .code_engine import CodeConfig
    from .code_experiment import run_code_file
    from .code_generation import CodeGenerator

    config = CodeConfig.model_validate_json(Path(config_path).read_text())
    generator = CodeGenerator(out, max_calls, model=model)
    summary = []
    for post in posts:
        try:
            artifact = generator.generate(post, config, hypotheses=hypotheses)
            item = dict(source_id=post.id, status="generated_and_reviewed", artifact=str(artifact))
            if prices:
                run_folder, metrics = run_code_file(
                    artifact / "strategy.py", artifact / "config.json", prices, run_out or "runs/custom-code"
                )
                item.update(status="completed", run=str(run_folder), metrics=metrics)
            summary.append(item)
        except (ValueError, OSError, SyntaxError) as exc:
            # Discovery exclusions are a valid result: preserve source provenance and continue.
            summary.append(dict(source_id=post.id, status="excluded", reason=error_reason(exc)))
    return summary


def main():
    args = make_parser().parse_args()
    try:
        if args.command in {"link", "discover"}:
            configure()

        if args.command == "check-code-sandbox":
            from .code_runner import verify_sandbox

            print(json.dumps(verify_sandbox(), indent=2))
            return
        if args.command == "check-access":
            import os
            import shutil
            import subprocess

            from .codex_provider import configured_model

            codex = shutil.which("codex")
            logged_in = False
            if codex:
                check = subprocess.run([codex, "login", "status"], capture_output=True, text=True, timeout=10)
                logged_in = check.returncode == 0 and "Logged in" in (check.stdout + check.stderr)
            reddit_ready = all(
                (
                    os.environ.get("REDDIT_API_APPROVED") == "true",
                    bool(os.environ.get("REDDIT_ACCESS_TOKEN")),
                    bool(os.environ.get("REDDIT_USER_AGENT")),
                )
            )
            print(
                json.dumps(
                    dict(
                        codex_cli=bool(codex),
                        codex_logged_in=logged_in,
                        codex_model=configured_model(),
                        reddit_approved=os.environ.get("REDDIT_API_APPROVED") == "true",
                        reddit_token=bool(os.environ.get("REDDIT_ACCESS_TOKEN")),
                        reddit_user_agent=bool(os.environ.get("REDDIT_USER_AGENT")),
                        autonomous_discovery_ready=bool(codex and logged_in and reddit_ready),
                    ),
                    indent=2,
                )
            )
            return
        if args.command == "fetch-prices":
            from .market import fetch_spy

            names = args.symbols or [args.symbol]
            if len(names) > 50 or len(names) != len(set(names)):
                raise ValueError("at most 50 unique requested symbols")
            for symbol in names:
                print(fetch_spy(args.start, args.end, args.out, symbol))
            return
        if args.command == "run-code":
            from .code_experiment import run_code_file

            folder, metrics = run_code_file(args.source, args.config, args.prices, args.out)
            print(json.dumps(dict(run=str(folder), metrics=metrics), indent=2))
            return
        if args.command == "inspect":
            from .source_contract import NativeExtractor, audit_contract, write_native_report

            extractor = NativeExtractor(
                "data/source-contract-cache", max_calls=args.max_model_calls, model=args.model
            )
            summary = []
            for post in read_posts(args.posts):
                contract, provenance = extractor.extract(post)
                audit = audit_contract(contract, post)
                output = Path(args.out) / f"{post.id}-{audit['contract_hash'][:16]}"
                write_native_report(output, post, contract, provenance, audit)
                summary.append(
                    dict(
                        source=post.id,
                        status=audit["status"],
                        output=str(output),
                        unsupported=audit["unsupported_capabilities"],
                    )
                )
            print(json.dumps(summary, indent=2))
            return
        if args.command == "generate-code":
            summary = generate_batch(
                read_posts(args.posts),
                args.config,
                args.out,
                args.max_model_calls,
                args.model,
                args.hypotheses,
                args.prices,
                "runs/custom-code",
            )
            print(json.dumps(summary, indent=2))
            return

        if args.command == "link":
            posts = Reddit("data/posts").link(args.url)
        elif args.command == "discover":
            posts = Reddit("data/posts").discover(
                args.subreddit,
                args.limit,
                tuple(args.feeds.split(",")),
                args.search,
                args.max_reddit_requests,
                args.time_filter,
            )
            output = Path(args.output_posts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps([post.model_dump() for post in posts], indent=2))
            if args.collect_only:
                print(
                    json.dumps(
                        dict(posts=len(posts), output=str(output), audit="data/posts/latest-discovery.json"),
                        indent=2,
                    )
                )
                return
            if not args.prices:
                raise ValueError("--prices is required when testing discovered posts")
        else:
            posts = read_posts(args.posts)

        if not args.code_config:
            raise ValueError(
                "--code-config is required for Codex translation; discovery supports --collect-only without it"
            )
        summary = generate_batch(
            posts,
            args.code_config,
            "data/generated-code",
            args.max_model_calls,
            args.model,
            args.hypotheses,
            None if args.command == "extract" else args.prices,
            args.out,
        )
        print(
            json.dumps(
                dict(
                    candidates=len(summary),
                    completed=sum(item["status"] == "completed" for item in summary),
                    reviewed=sum(item["status"] == "generated_and_reviewed" for item in summary),
                    excluded=sum(item["status"] == "excluded" for item in summary),
                    results=summary,
                ),
                indent=2,
            )
        )
    except (ValueError, OSError, KeyError, SyntaxError) as exc:
        print("Run failed: " + error_reason(exc))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
