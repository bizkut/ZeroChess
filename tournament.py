"""
Tournament - Run multiple games in parallel
"""

import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from engine_wrapper import EngineConfig
from match_runner import GameResult, TimeControl, play_game
from openings import Opening, create_opening_pairs


class Tournament:
    """Manages a tournament between two engines."""
    
    def __init__(
        self,
        engine1_config: EngineConfig,
        engine2_config: EngineConfig,
        num_games: int = 100,
        concurrent_games: int = 4,
        time_control: TimeControl = None,
        use_opening_book: bool = True,
        output_dir: str = "output",
        results_file: str = "output/results.json"
    ):
        self.engine1_config = engine1_config
        self.engine2_config = engine2_config
        self.num_games = num_games
        self.concurrent_games = concurrent_games
        self.time_control = time_control or TimeControl()
        self.use_opening_book = use_opening_book
        self.output_dir = Path(output_dir)
        self.results_file = Path(results_file)
        
        self.results: List[GameResult] = []
        self.completed_game_ids: set = set()
        
        # Callbacks
        self.on_game_start: Optional[Callable] = None
        self.on_game_end: Optional[Callable] = None
        self.on_move: Optional[Callable] = None
        
        # State
        self.running = False
        self.paused = False
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    def _load_previous_results(self) -> None:
        """Load results from a previous run for resumption."""
        if self.results_file.exists():
            try:
                with open(self.results_file) as f:
                    data = json.load(f)
                    for r in data.get("results", []):
                        self.completed_game_ids.add(r["game_id"])
                        self.results.append(GameResult(**r))
                print(f"Loaded {len(self.results)} previous results")
            except Exception as e:
                print(f"Could not load previous results: {e}")
    
    def _save_result(self, result: GameResult) -> None:
        """Save a result incrementally."""
        self.results_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "tournament_start": self.results[0].game_id if self.results else 0,
            "last_updated": datetime.now().isoformat(),
            "results": [asdict(r) for r in self.results]
        }
        
        with open(self.results_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_pgn(self, result: GameResult) -> None:
        """Save a game's PGN to file."""
        pgn_dir = self.output_dir / "pgn"
        pgn_dir.mkdir(parents=True, exist_ok=True)
        
        pgn_file = pgn_dir / f"game_{result.game_id:04d}.pgn"
        with open(pgn_file, 'w') as f:
            f.write(result.pgn)
    
    async def _play_single_game(self, game_id: int, opening: Opening) -> Optional[GameResult]:
        """Play a single game with semaphore control."""
        if game_id in self.completed_game_ids:
            return None
        
        async with self._semaphore:
            if not self.running:
                return None
            
            while self.paused:
                await asyncio.sleep(0.5)
            
            # Alternate colors: even games = engine1 white, odd = engine2 white
            if game_id % 2 == 0:
                white_config = self.engine1_config
                black_config = self.engine2_config
            else:
                white_config = self.engine2_config
                black_config = self.engine1_config
            
            # Notify start
            if self.on_game_start:
                await self.on_game_start(game_id, white_config.name, black_config.name, opening)
            
            # Play
            result = await play_game(
                game_id=game_id,
                white_config=white_config,
                black_config=black_config,
                opening=opening,
                time_control=self.time_control,
                on_move=self.on_move
            )
            
            # Save
            self.results.append(result)
            self.completed_game_ids.add(game_id)
            self._save_result(result)
            self._save_pgn(result)
            
            # Notify end
            if self.on_game_end:
                await self.on_game_end(result)
            
            return result
    
    async def run(self) -> List[GameResult]:
        """Run the full tournament."""
        self._load_previous_results()
        
        # Create openings
        if self.use_opening_book:
            openings = create_opening_pairs(self.num_games)
        else:
            # Use starting position for all games
            from openings import Opening
            start = Opening("Starting Position", "A00", [])
            openings = [start] * self.num_games
        
        self._semaphore = asyncio.Semaphore(self.concurrent_games)
        self.running = True
        
        # Create tasks for all games
        tasks = [
            self._play_single_game(i, openings[i])
            for i in range(self.num_games)
        ]
        
        # Run with concurrency control
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.running = False
        return self.results
    
    def pause(self) -> None:
        """Pause the tournament."""
        self.paused = True
    
    def resume(self) -> None:
        """Resume the tournament."""
        self.paused = False
    
    def stop(self) -> None:
        """Stop the tournament."""
        self.running = False
    
    def get_stats(self) -> dict:
        """Get current tournament statistics."""
        if not self.results:
            return {
                "total_games": 0,
                "completed": 0,
                "engine1_wins": 0,
                "engine2_wins": 0,
                "draws": 0,
            }
        
        engine1_wins = 0
        engine2_wins = 0
        draws = 0
        
        for r in self.results:
            if r.result == "1/2-1/2":
                draws += 1
            elif r.winner == "white":
                if r.white_engine == self.engine1_config.name:
                    engine1_wins += 1
                else:
                    engine2_wins += 1
            elif r.winner == "black":
                if r.black_engine == self.engine1_config.name:
                    engine1_wins += 1
                else:
                    engine2_wins += 1
        
        return {
            "total_games": self.num_games,
            "completed": len(self.results),
            "engine1_name": self.engine1_config.name,
            "engine2_name": self.engine2_config.name,
            "engine1_wins": engine1_wins,
            "engine2_wins": engine2_wins,
            "draws": draws,
            "engine1_score": engine1_wins + draws * 0.5,
            "engine2_score": engine2_wins + draws * 0.5,
        }
