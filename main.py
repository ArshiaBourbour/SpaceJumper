"""Entry point for Space Jumper.

Run this file to start the game::

    python main.py
"""

from __future__ import annotations

from core.game import Game


def main() -> None:
    """Create the game and run it until the player quits."""
    Game().run()


if __name__ == "__main__":
    main()
