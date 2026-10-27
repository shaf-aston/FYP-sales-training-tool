"""Talk to the scripted seller from the terminal, with the real recogniser and no AI (the plain script lines).

    python scripts/chat_cli.py                       # type replies, blank line quits
    python scripts/chat_cli.py "yeah" "more money"   # one call from the replies given
    python scripts/chat_cli.py --file replies.txt    # one reply per line

Each turn shows what the reply was heard as and the step the script moved to.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.buy_mode.script_engine.seller import build_seller, resolve_product  # noqa: E402


class NoAi:
    """Stands in for the provider router: every AI call fails, so the seller says its plain script lines."""

    def chat_with_fallback(self, *_, **__):
        raise RuntimeError("AI off in the CLI")


def replies(args):
    if args.file:
        return iter(Path(args.file).read_text(encoding="utf-8").splitlines())
    if args.replies:
        return iter(args.replies)
    return iter(lambda: input("you : ").strip(), "")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("replies", nargs="*")
    parser.add_argument("--file")
    parser.add_argument("--product", default=None)
    args = parser.parse_args()
    seller = build_seller(NoAi(), resolve_product(args.product))
    print(f"bot : {seller.opening()[0]}")
    for text in replies(args):
        said, _ = seller.reply(text)
        turn = seller.last_turn
        if args.replies or args.file:
            print(f"\nyou : {text}")
        print(f"      [{turn['heard_as']}  {turn['step_from']} -> {turn['step_to']}]")
        print(f"bot : {said}")


if __name__ == "__main__":
    main()
