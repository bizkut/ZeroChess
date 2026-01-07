"""
WebSocket Server - Real-time dashboard and tournament control
"""

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Set

import chess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from engine_wrapper import (
    EngineConfig,
    create_lc0_config,
    create_stockfish_config,
    download_weights,
)
from match_runner import GameResult, TimeControl
from openings import Opening
from stats_analyzer import TournamentStats, analyze_tournament, generate_report
from tournament import Tournament

app = FastAPI(title="ZeroChess")

# Global state
tournament: Optional[Tournament] = None
active_games: Dict[int, dict] = {}
connected_clients: Set[WebSocket] = set()


# --- WebSocket Broadcasting ---

async def broadcast(event: str, data: dict) -> None:
    """Send event to all connected clients."""
    message = json.dumps({"event": event, "data": data})
    disconnected = set()
    
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)
    
    connected_clients.difference_update(disconnected)


# --- Tournament Callbacks ---

async def on_game_start(game_id: int, white: str, black: str, opening: Opening) -> None:
    """Called when a game starts."""
    active_games[game_id] = {
        "game_id": game_id,
        "white": white,
        "black": black,
        "opening": opening.name,
        "eco": opening.eco,
        "fen": opening.get_board().fen(),
        "moves": [],
    }
    
    await broadcast("game_start", active_games[game_id])


async def on_move(game_id: int, board: chess.Board, move: chess.Move) -> None:
    """Called after each move."""
    if game_id in active_games:
        active_games[game_id]["fen"] = board.fen()
        active_games[game_id]["moves"].append(move.uci())
        
        await broadcast("move", {
            "game_id": game_id,
            "fen": board.fen(),
            "move": move.uci(),
            "move_count": len(active_games[game_id]["moves"])
        })


async def on_game_end(result: GameResult) -> None:
    """Called when a game ends."""
    if result.game_id in active_games:
        del active_games[result.game_id]
    
    # Get updated stats
    if tournament:
        stats = tournament.get_stats()
    else:
        stats = {}
    
    await broadcast("game_end", {
        "game_id": result.game_id,
        "result": result.result,
        "winner": result.winner,
        "termination": result.termination,
        "moves": result.move_count,
        "stats": stats
    })


# --- API Endpoints ---

@app.get("/")
async def index():
    """Serve the dashboard."""
    return FileResponse(Path(__file__).parent / "web" / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection handler."""
    await websocket.accept()
    connected_clients.add(websocket)
    
    # Send current state
    if tournament:
        stats = tournament.get_stats()
        await websocket.send_text(json.dumps({
            "event": "state",
            "data": {
                "running": tournament.running,
                "paused": tournament.paused,
                "stats": stats,
                "active_games": list(active_games.values())
            }
        }))
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            await handle_command(message, websocket)
    
    except WebSocketDisconnect:
        connected_clients.discard(websocket)


async def handle_command(message: dict, websocket: WebSocket) -> None:
    """Handle incoming WebSocket commands."""
    global tournament
    
    command = message.get("command")
    
    if command == "start":
        await start_tournament(message.get("config", {}))
    
    elif command == "pause":
        if tournament:
            tournament.pause()
            await broadcast("paused", {})
    
    elif command == "resume":
        if tournament:
            tournament.resume()
            await broadcast("resumed", {})
    
    elif command == "stop":
        if tournament:
            tournament.stop()
            await broadcast("stopped", {})
    
    elif command == "get_stats":
        if tournament:
            stats = tournament.get_stats()
            await websocket.send_text(json.dumps({
                "event": "stats",
                "data": stats
            }))


async def start_tournament(config: dict) -> None:
    """Start a new tournament with the given configuration."""
    global tournament
    
    # Load defaults from config.toml
    import toml
    config_path = Path(__file__).parent / "config.toml"
    
    if config_path.exists():
        defaults = toml.load(config_path)
    else:
        defaults = {}
    
    # Merge with provided config
    engines = defaults.get("engines", {})
    tourney = defaults.get("tournament", {})
    
    # Download weights if needed
    weights_cfg = engines.get("lc0_weights", {})
    if weights_cfg.get("url"):
        await download_weights(weights_cfg["url"], weights_cfg.get("local_path", "weights/network.pb.gz"))
    
    # Create engine configs
    stockfish = create_stockfish_config(
        path=config.get("stockfish_path", engines.get("stockfish_path", "stockfish")),
        threads=config.get("stockfish_threads", engines.get("stockfish_threads", 4)),
        hash_mb=config.get("stockfish_hash", engines.get("stockfish_hash_mb", 256))
    )
    
    lc0 = create_lc0_config(
        path=config.get("lc0_path", engines.get("lc0_path", "lc0")),
        weights_path=weights_cfg.get("local_path"),
        backend=config.get("lc0_backend", engines.get("lc0_backend", "metal")),
        threads=config.get("lc0_threads", engines.get("lc0_threads", 2))
    )
    
    # Create tournament
    tournament = Tournament(
        engine1_config=lc0,
        engine2_config=stockfish,
        num_games=config.get("num_games", tourney.get("num_games", 100)),
        concurrent_games=config.get("concurrent_games", tourney.get("concurrent_games", 4)),
        time_control=TimeControl(
            base_seconds=config.get("time_control", tourney.get("time_control_seconds", 60)),
            increment_seconds=config.get("increment", tourney.get("increment_seconds", 0.5))
        ),
        use_opening_book=config.get("use_openings", tourney.get("use_opening_book", True))
    )
    
    # Set callbacks
    tournament.on_game_start = on_game_start
    tournament.on_game_end = on_game_end
    tournament.on_move = on_move
    
    await broadcast("started", {"config": config})
    
    # Run in background
    asyncio.create_task(run_tournament_task())


async def run_tournament_task() -> None:
    """Background task to run the tournament."""
    global tournament
    
    if tournament:
        try:
            results = await tournament.run()
            
            # Generate final report
            stats = analyze_tournament(
                results,
                tournament.engine1_config.name,
                tournament.engine2_config.name
            )
            
            report = generate_report(stats)
            print(report)
            
            await broadcast("completed", {
                "stats": tournament.get_stats(),
                "report": report
            })
        
        except Exception as e:
            await broadcast("error", {"message": str(e)})


# Mount static files
web_dir = Path(__file__).parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
