#!/usr/bin/env python3
"""
ZeroChess - Main Entry Point

Run this to start the web server and dashboard.
"""

import argparse
import asyncio
from pathlib import Path

import toml


def load_config(config_path: str = "config.toml") -> dict:
    """Load configuration from TOML file."""
    path = Path(config_path)
    if path.exists():
        return toml.load(path)
    return {}


def main():
    parser = argparse.ArgumentParser(description="ZeroChess - LC0 vs Stockfish Match Simulator")
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    parser.add_argument("--config", default="config.toml", help="Config file path")
    
    args = parser.parse_args()
    
    # Load config
    config = load_config(args.config)
    server_config = config.get("server", {})
    
    host = server_config.get("host", args.host)
    port = server_config.get("port", args.port)
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ♔  Z E R O C H E S S                                   ║
║                                                           ║
║   LC0 vs Stockfish Match Simulator                        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Starting server at http://{host if host != '0.0.0.0' else 'localhost'}:{port}
Press Ctrl+C to stop.
""")
    
    # Import and run server
    from server import run_server
    run_server(host=host, port=port)


if __name__ == "__main__":
    main()
