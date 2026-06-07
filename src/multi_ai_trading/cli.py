from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path

from .config import load_config
from .orchestrator import MultiAgentTradingSystem


async def run_demo(args: argparse.Namespace) -> None:
    config = replace(
        load_config(),
        feed_mode="simulated",
        execution_mode="paper",
        state_db_path=Path(args.db),
    )
    system = MultiAgentTradingSystem(config)
    await system.run(max_ticks=args.ticks)
    print(json.dumps(system.snapshot(), indent=2, ensure_ascii=False))


def serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("Install runtime dependencies first: pip install -r requirements.txt") from exc
    uvicorn.run(
        "multi_ai_trading.api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Multi-AI Agent Trading System")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="Run a paper-trading simulated feed demo")
    demo.add_argument("--ticks", type=int, default=180)
    demo.add_argument("--db", default="runtime/demo.sqlite")
    demo.set_defaults(func=lambda args: asyncio.run(run_demo(args)))

    server = subparsers.add_parser("serve", help="Start FastAPI server")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8000)
    server.add_argument("--reload", action="store_true")
    server.set_defaults(func=serve)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

