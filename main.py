"""Entry point for Space Jumper.

Run this file to start the game::

    python main.py
"""
import pygame

from core.game import Game


def main() -> None:
    """Initialize Pygame and start the game loop."""
    pygame.init()
    game = Game()
    while True:
        game.show_menu()


if __name__ == "__main__":
    main()
