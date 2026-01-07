"""
Match Runner - Play a single game between two engines
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import chess
import chess.pgn

from engine_wrapper import EngineConfig, EngineWrapper
from openings import Opening


@dataclass
class GameResult:
    """Result of a single game."""
    game_id: int
    white_engine: str
    black_engine: str
    result: str  # "1-0", "0-1", "1/2-1/2"
    winner: Optional[str]  # "white", "black", None for draw
    termination: str  # "checkmate", "stalemate", "resignation", "timeout", "draw"
    moves: List[str]
    opening_name: str
    opening_eco: str
    pgn: str
    move_count: int
    duration_seconds: float
    error: Optional[str] = None


@dataclass 
class TimeControl:
    """Time control settings."""
    base_seconds: float = 60.0
    increment_seconds: float = 0.5
    
    def get_limit(self, remaining_time: float) -> chess.engine.Limit:
        """Get engine limit based on remaining time."""
        # Use a fraction of remaining time + increment
        think_time = min(remaining_time * 0.05, 5.0) + self.increment_seconds
        return chess.engine.Limit(time=think_time)


async def play_game(
    game_id: int,
    white_config: EngineConfig,
    black_config: EngineConfig,
    opening: Opening,
    time_control: TimeControl,
    on_move: callable = None
) -> GameResult:
    """
    Play a single game between two engines.
    
    Args:
        game_id: Unique identifier for this game
        white_config: Configuration for the white engine
        black_config: Configuration for the black engine
        opening: Opening position to start from
        time_control: Time control settings
        on_move: Optional callback called after each move (board, move)
    
    Returns:
        GameResult with all game information
    """
    start_time = datetime.now()
    
    # Initialize engines
    white_engine = EngineWrapper(white_config)
    black_engine = EngineWrapper(black_config)
    
    try:
        await white_engine.start()
        await black_engine.start()
    except Exception as e:
        return GameResult(
            game_id=game_id,
            white_engine=white_config.name,
            black_engine=black_config.name,
            result="*",
            winner=None,
            termination="error",
            moves=[],
            opening_name=opening.name,
            opening_eco=opening.eco,
            pgn="",
            move_count=0,
            duration_seconds=0,
            error=str(e)
        )
    
    # Set up board from opening
    board = opening.get_board()
    moves: List[str] = opening.moves.copy()
    
    # Time tracking
    white_time = time_control.base_seconds
    black_time = time_control.base_seconds
    
    termination = "unknown"
    error = None
    
    try:
        while not board.is_game_over():
            # Check for 50-move rule, threefold repetition, etc.
            if board.can_claim_draw():
                termination = "draw"
                break
            
            # Select engine and time
            if board.turn == chess.WHITE:
                engine = white_engine
                remaining = white_time
            else:
                engine = black_engine
                remaining = black_time
            
            # Get move
            limit = time_control.get_limit(remaining)
            
            try:
                result = await asyncio.wait_for(
                    engine.play(board, limit),
                    timeout=limit.time + 5.0  # Grace period
                )
            except asyncio.TimeoutError:
                termination = "timeout"
                break
            
            move = result.move
            
            if move is None:
                termination = "resignation"
                break
            
            # Apply move
            board.push(move)
            moves.append(move.uci())
            
            # Deduct time (simplified - actual would track real time)
            if board.turn == chess.BLACK:
                white_time = max(0, white_time - limit.time + time_control.increment_seconds)
            else:
                black_time = max(0, black_time - limit.time + time_control.increment_seconds)
            
            # Callback
            if on_move:
                await on_move(game_id, board, move)
        
        # Determine result
        if board.is_checkmate():
            termination = "checkmate"
        elif board.is_stalemate():
            termination = "stalemate"
        elif board.is_insufficient_material():
            termination = "insufficient_material"
        elif termination == "unknown":
            termination = "draw"
    
    except Exception as e:
        error = str(e)
        termination = "error"
    
    finally:
        await white_engine.quit()
        await black_engine.quit()
    
    # Calculate result string
    if termination == "checkmate":
        if board.turn == chess.WHITE:
            result_str = "0-1"
            winner = "black"
        else:
            result_str = "1-0"
            winner = "white"
    elif termination == "timeout":
        if board.turn == chess.WHITE:
            result_str = "0-1"
            winner = "black"
        else:
            result_str = "1-0"
            winner = "white"
    elif termination == "resignation":
        if board.turn == chess.WHITE:
            result_str = "0-1"
            winner = "black"
        else:
            result_str = "1-0"
            winner = "white"
    else:
        result_str = "1/2-1/2"
        winner = None
    
    # Generate PGN
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = "ZeroChess Match"
    pgn_game.headers["Date"] = start_time.strftime("%Y.%m.%d")
    pgn_game.headers["White"] = white_config.name
    pgn_game.headers["Black"] = black_config.name
    pgn_game.headers["Result"] = result_str
    pgn_game.headers["ECO"] = opening.eco
    pgn_game.headers["Opening"] = opening.name
    
    # Rebuild moves for PGN
    node = pgn_game
    temp_board = chess.Board()
    for uci_move in moves:
        move = temp_board.parse_uci(uci_move)
        node = node.add_variation(move)
        temp_board.push(move)
    
    duration = (datetime.now() - start_time).total_seconds()
    
    return GameResult(
        game_id=game_id,
        white_engine=white_config.name,
        black_engine=black_config.name,
        result=result_str,
        winner=winner,
        termination=termination,
        moves=moves,
        opening_name=opening.name,
        opening_eco=opening.eco,
        pgn=str(pgn_game),
        move_count=len(moves),
        duration_seconds=duration,
        error=error
    )
