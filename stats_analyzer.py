"""
Stats Analyzer - Calculate and report tournament statistics
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from match_runner import GameResult


@dataclass
class TournamentStats:
    """Complete tournament statistics."""
    total_games: int
    completed_games: int
    engine1_name: str
    engine2_name: str
    engine1_wins: int
    engine2_wins: int
    draws: int
    engine1_score: float
    engine2_score: float
    elo_difference: float
    elo_error_margin: float
    win_rate_engine1: float
    opening_stats: Dict[str, Dict]
    avg_game_length: float
    termination_stats: Dict[str, int]


def calculate_elo_difference(wins: int, losses: int, draws: int) -> tuple[float, float]:
    """
    Calculate Elo difference from match results.
    
    Returns:
        (elo_diff, error_margin): Estimated Elo difference and 95% confidence margin
    """
    total = wins + losses + draws
    if total == 0:
        return 0.0, 0.0
    
    # Score percentage
    score = (wins + draws * 0.5) / total
    
    # Clamp to avoid math errors
    score = max(0.001, min(0.999, score))
    
    # Elo formula: Elo = -400 * log10(1/score - 1)
    elo_diff = -400 * math.log10(1 / score - 1)
    
    # Error margin using standard deviation
    # Variance for win/loss/draw outcomes
    variance = (wins * (1 - score) ** 2 + losses * score ** 2 + draws * (0.5 - score) ** 2) / total
    std_dev = math.sqrt(variance)
    
    # Convert to Elo (simplified approximation)
    elo_per_pct = 8  # Rough conversion factor
    error_margin = 1.96 * std_dev * elo_per_pct * 100 / math.sqrt(total)
    
    return elo_diff, error_margin


def analyze_tournament(results: List[GameResult], engine1_name: str, engine2_name: str) -> TournamentStats:
    """Analyze tournament results and generate statistics."""
    
    if not results:
        return TournamentStats(
            total_games=0,
            completed_games=0,
            engine1_name=engine1_name,
            engine2_name=engine2_name,
            engine1_wins=0,
            engine2_wins=0,
            draws=0,
            engine1_score=0,
            engine2_score=0,
            elo_difference=0,
            elo_error_margin=0,
            win_rate_engine1=0,
            opening_stats={},
            avg_game_length=0,
            termination_stats={}
        )
    
    # Count results
    engine1_wins = 0
    engine2_wins = 0
    draws = 0
    total_moves = 0
    termination_stats: Dict[str, int] = {}
    opening_stats: Dict[str, Dict] = {}
    
    for r in results:
        # Count terminations
        termination_stats[r.termination] = termination_stats.get(r.termination, 0) + 1
        
        # Count moves
        total_moves += r.move_count
        
        # Determine outcome
        if r.result == "1/2-1/2":
            draws += 1
            outcome = "draw"
        elif r.winner == "white":
            if r.white_engine == engine1_name:
                engine1_wins += 1
                outcome = "engine1_win"
            else:
                engine2_wins += 1
                outcome = "engine2_win"
        elif r.winner == "black":
            if r.black_engine == engine1_name:
                engine1_wins += 1
                outcome = "engine1_win"
            else:
                engine2_wins += 1
                outcome = "engine2_win"
        else:
            draws += 1
            outcome = "draw"
        
        # Track opening performance
        eco = r.opening_eco
        if eco not in opening_stats:
            opening_stats[eco] = {
                "name": r.opening_name,
                "games": 0,
                "engine1_wins": 0,
                "engine2_wins": 0,
                "draws": 0
            }
        
        opening_stats[eco]["games"] += 1
        if outcome == "engine1_win":
            opening_stats[eco]["engine1_wins"] += 1
        elif outcome == "engine2_win":
            opening_stats[eco]["engine2_wins"] += 1
        else:
            opening_stats[eco]["draws"] += 1
    
    # Calculate derived stats
    engine1_score = engine1_wins + draws * 0.5
    engine2_score = engine2_wins + draws * 0.5
    total = engine1_wins + engine2_wins + draws
    
    elo_diff, elo_error = calculate_elo_difference(engine1_wins, engine2_wins, draws)
    
    win_rate = engine1_score / total if total > 0 else 0.5
    avg_length = total_moves / len(results) if results else 0
    
    return TournamentStats(
        total_games=len(results),
        completed_games=len(results),
        engine1_name=engine1_name,
        engine2_name=engine2_name,
        engine1_wins=engine1_wins,
        engine2_wins=engine2_wins,
        draws=draws,
        engine1_score=engine1_score,
        engine2_score=engine2_score,
        elo_difference=elo_diff,
        elo_error_margin=elo_error,
        win_rate_engine1=win_rate,
        opening_stats=opening_stats,
        avg_game_length=avg_length,
        termination_stats=termination_stats
    )


def generate_report(stats: TournamentStats) -> str:
    """Generate a human-readable report."""
    lines = [
        "=" * 60,
        "ZEROCHESS TOURNAMENT REPORT",
        "=" * 60,
        "",
        f"Match: {stats.engine1_name} vs {stats.engine2_name}",
        f"Games: {stats.completed_games}",
        "",
        "--- RESULTS ---",
        f"{stats.engine1_name}: {stats.engine1_wins} wins ({stats.engine1_score:.1f} points)",
        f"{stats.engine2_name}: {stats.engine2_wins} wins ({stats.engine2_score:.1f} points)",
        f"Draws: {stats.draws}",
        "",
        "--- ELO ANALYSIS ---",
        f"Elo difference: {stats.elo_difference:+.1f} ± {stats.elo_error_margin:.1f}",
        f"Win rate ({stats.engine1_name}): {stats.win_rate_engine1 * 100:.1f}%",
        "",
        "--- GAME STATISTICS ---",
        f"Average game length: {stats.avg_game_length:.1f} moves",
        "",
        "Terminations:"
    ]
    
    for term, count in sorted(stats.termination_stats.items(), key=lambda x: -x[1]):
        pct = count / stats.completed_games * 100 if stats.completed_games else 0
        lines.append(f"  {term}: {count} ({pct:.1f}%)")
    
    if stats.opening_stats:
        lines.extend([
            "",
            "--- OPENINGS (Top 5 by games) ---"
        ])
        
        sorted_openings = sorted(
            stats.opening_stats.items(),
            key=lambda x: -x[1]["games"]
        )[:5]
        
        for eco, data in sorted_openings:
            lines.append(
                f"  {eco} {data['name']}: "
                f"+{data['engine1_wins']} ={data['draws']} -{data['engine2_wins']}"
            )
    
    lines.extend(["", "=" * 60])
    
    return "\n".join(lines)


def export_json(stats: TournamentStats, filepath: str) -> None:
    """Export statistics to JSON."""
    data = {
        "total_games": stats.total_games,
        "completed_games": stats.completed_games,
        "engine1": {
            "name": stats.engine1_name,
            "wins": stats.engine1_wins,
            "score": stats.engine1_score,
        },
        "engine2": {
            "name": stats.engine2_name,
            "wins": stats.engine2_wins,
            "score": stats.engine2_score,
        },
        "draws": stats.draws,
        "elo_difference": stats.elo_difference,
        "elo_error_margin": stats.elo_error_margin,
        "win_rate_engine1": stats.win_rate_engine1,
        "avg_game_length": stats.avg_game_length,
        "termination_stats": stats.termination_stats,
        "opening_stats": stats.opening_stats,
    }
    
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def export_csv(results: List[GameResult], filepath: str) -> None:
    """Export game-by-game results to CSV."""
    import csv
    
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "game_id", "white", "black", "result", "winner",
            "termination", "moves", "opening_eco", "opening_name", "duration_s"
        ])
        
        for r in results:
            writer.writerow([
                r.game_id, r.white_engine, r.black_engine, r.result, r.winner or "",
                r.termination, r.move_count, r.opening_eco, r.opening_name, f"{r.duration_seconds:.1f}"
            ])
