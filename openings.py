"""
Opening Book - ECO opening positions for game diversity
"""

import random
from dataclasses import dataclass
from typing import List

import chess


@dataclass
class Opening:
    """An opening position with metadata."""
    name: str
    eco: str
    moves: List[str]  # List of UCI move strings
    
    def get_board(self) -> chess.Board:
        """Return the board position after the opening moves."""
        board = chess.Board()
        for uci_move in self.moves:
            board.push_uci(uci_move)
        return board


# Common ECO openings (first 4-8 moves each side)
OPENINGS = [
    # Open Games (1.e4 e5)
    Opening("Italian Game", "C50", ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"]),
    Opening("Ruy Lopez", "C60", ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]),
    Opening("Scotch Game", "C45", ["e2e4", "e7e5", "g1f3", "b8c6", "d2d4", "e5d4"]),
    Opening("Four Knights", "C47", ["e2e4", "e7e5", "g1f3", "b8c6", "b1c3", "g8f6"]),
    Opening("Petroff Defense", "C42", ["e2e4", "e7e5", "g1f3", "g8f6"]),
    Opening("King's Gambit", "C30", ["e2e4", "e7e5", "f2f4"]),
    
    # Semi-Open Games (1.e4 other)
    Opening("Sicilian Najdorf", "B90", ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6", "b1c3", "a7a6"]),
    Opening("Sicilian Dragon", "B70", ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6", "b1c3", "g7g6"]),
    Opening("French Defense", "C00", ["e2e4", "e7e6", "d2d4", "d7d5"]),
    Opening("Caro-Kann", "B10", ["e2e4", "c7c6", "d2d4", "d7d5"]),
    Opening("Pirc Defense", "B07", ["e2e4", "d7d6", "d2d4", "g8f6", "b1c3", "g7g6"]),
    Opening("Scandinavian", "B01", ["e2e4", "d7d5", "e4d5", "d8d5"]),
    
    # Closed Games (1.d4 d5)
    Opening("Queen's Gambit Declined", "D30", ["d2d4", "d7d5", "c2c4", "e7e6"]),
    Opening("Queen's Gambit Accepted", "D20", ["d2d4", "d7d5", "c2c4", "d5c4"]),
    Opening("Slav Defense", "D10", ["d2d4", "d7d5", "c2c4", "c7c6"]),
    Opening("London System", "D00", ["d2d4", "d7d5", "c1f4"]),
    
    # Indian Defenses (1.d4 Nf6)
    Opening("King's Indian", "E60", ["d2d4", "g8f6", "c2c4", "g7g6", "b1c3", "f8g7"]),
    Opening("Nimzo-Indian", "E20", ["d2d4", "g8f6", "c2c4", "e7e6", "b1c3", "f8b4"]),
    Opening("Queen's Indian", "E12", ["d2d4", "g8f6", "c2c4", "e7e6", "g1f3", "b7b6"]),
    Opening("Grünfeld Defense", "D80", ["d2d4", "g8f6", "c2c4", "g7g6", "b1c3", "d7d5"]),
    
    # Flank Openings
    Opening("English Opening", "A10", ["c2c4"]),
    Opening("Réti Opening", "A04", ["g1f3", "d7d5", "c2c4"]),
    Opening("King's Indian Attack", "A07", ["g1f3", "d7d5", "g2g3"]),
    Opening("Bird's Opening", "A02", ["f2f4"]),
]


def get_random_opening() -> Opening:
    """Get a random opening from the book."""
    return random.choice(OPENINGS)


def get_opening_by_eco(eco: str) -> Opening:
    """Get an opening by ECO code."""
    for opening in OPENINGS:
        if opening.eco == eco:
            return opening
    raise ValueError(f"Opening {eco} not found")


def get_all_openings() -> List[Opening]:
    """Get all openings in the book."""
    return OPENINGS.copy()


def create_opening_pairs(num_games: int) -> List[Opening]:
    """
    Create a list of openings for a tournament.
    Each opening is used twice (once as white, once as black swap).
    """
    openings = []
    all_openings = get_all_openings()
    
    games_per_opening = max(1, num_games // (len(all_openings) * 2))
    
    for opening in all_openings:
        for _ in range(games_per_opening):
            openings.append(opening)
            openings.append(opening)  # Pair for color swap
    
    # Fill remaining slots randomly
    while len(openings) < num_games:
        openings.append(get_random_opening())
    
    # Shuffle to avoid predictable patterns
    random.shuffle(openings)
    
    return openings[:num_games]
