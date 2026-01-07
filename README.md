# ZeroChess

High-performance chess match simulator for **LeelaChessZero (LC0)** vs **Stockfish** with real-time web dashboard.

## Features

- ⚡ **Parallel Match Execution** - Run multiple games concurrently to maximize GPU/CPU utilization
- 🌐 **Real-Time Web Dashboard** - Live game boards, statistics, and control panel
- 📊 **Detailed Statistics** - Elo estimation, opening analysis, win/loss/draw tracking
- 📖 **Opening Book** - Diversified game starts using ECO openings
- 💾 **Resumable Tournaments** - Continue from where you left off after interruption

## Requirements

- Python 3.10+
- [Stockfish](https://stockfishchess.org/download/) binary
- [LC0](https://lczero.org/play/download/) binary with Metal/CUDA backend

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Edit config.toml with your engine paths
vim config.toml

# Start the server
python main.py

# Open browser to http://localhost:8080
```

## Configuration

Edit `config.toml` to customize:

- Engine paths and options
- Time controls
- Number of concurrent games
- Output directories

## Architecture

ZeroChess is built with a producer-consumer architecture to handle high-concurrency match simulation:

- **Engine Wrapper**: Unified interface for UCI engines (`stockfish`, `lc0`). Handles weight downloading and configuration.
- **Match Runner**: Executes single games with strict time controls, PGN generation, and termination handling.
- **Tournament Manager**: Uses `multiprocessing` (via `asyncio` and thread pools) to run `N` games in parallel, maximizing hardware usage.
- **Stats Engine**: Calculates Elo differences using SPRT (Sequential Probability Ratio Test) logic.
- **Web Server**: FastAPI + WebSockets deliver real-time state to the frontend.

## Web Dashboard

The interface provides real-time monitoring and control:

- **Live Boards**: Watch multiple games progress simultaneously.
- **Stats Panel**: Track Elo difference, win rates, and opening performance.
- **Control**: Pause/Resume the tournament or adjust parameters on the fly.
- **Charts**: Visualise Elo convergence over time.

## Network Weights

LC0 requires a neural network weights file. The default configuration uses:
- **BT4-1024x15x32h-swa-6147500-policytune-332** (auto-downloaded on first run)

## License

MIT
