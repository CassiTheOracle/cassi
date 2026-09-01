"""Command-line entrypoint for the bounded local Cassi Qi terminal conversation."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_conscious_chat import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_STATE_DIR,
    CassiChatTurn,
    CassiConsciousChatError,
    CassiConsciousChatRuntime,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local terminal conversation generated and persisted by the Cassi Qi field engine."
    )
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--max-output-symbols", type=int, default=None)
    parser.add_argument("--prompt", help="Run one bounded turn without entering the interactive loop.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the complete Qi-native ownership receipt as JSON.",
    )
    return parser


def _print_turn(turn: CassiChatTurn, *, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(
                turn.as_dict(),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        print(turn.reply)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        with CassiConsciousChatRuntime.open(
            config_path=args.runtime_config,
            state_dir=args.state_dir,
            device=args.device,
            session_id=args.session_id,
            max_output_symbols=args.max_output_symbols,
        ) as runtime:
            if args.prompt is not None:
                _print_turn(runtime.chat(args.prompt), as_json=args.json)
                return 0
            print("Local Qi-field conversation; no model server, tools, or actions.")
            while True:
                try:
                    text = input("you> ")
                except EOFError:
                    print()
                    return 0
                if text == "/quit":
                    return 0
                try:
                    turn = runtime.chat(text)
                except CassiConsciousChatError as error:
                    print(f"cassi chat error: {error}", file=sys.stderr)
                    continue
                if args.json:
                    _print_turn(turn, as_json=True)
                else:
                    print(f"cassi> {turn.reply}")
                    print(
                        f"[continuity sequence {turn.next_sequence}; "
                        f"field receipt {turn.field_text_receipt_sha256[:12]}; "
                        f"learned_parameters {turn.architecture['learned_parameter_count']}]"
                    )
    except (CassiConsciousChatError, OSError, ValueError) as error:
        print(f"cassi chat error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
