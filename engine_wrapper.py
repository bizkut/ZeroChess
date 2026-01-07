"""
Engine Wrapper - Unified interface for chess engines (Stockfish, LC0)
"""

import asyncio
import gzip
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chess
import chess.engine
import httpx


@dataclass
class EngineConfig:
    """Configuration for a chess engine."""
    name: str
    path: str
    options: dict = None
    
    def __post_init__(self):
        if self.options is None:
            self.options = {}


async def download_weights(url: str, local_path: str) -> str:
    """Download LC0 weights if not present."""
    path = Path(local_path)
    
    if path.exists():
        return str(path)
    
    path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading weights from {url}...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        
        with open(path, 'wb') as f:
            f.write(response.content)
    
    print(f"Weights saved to {path}")
    return str(path)


def decompress_weights_if_needed(path: str) -> str:
    """Decompress .gz weights file if needed, return path to usable file."""
    if not path.endswith('.gz'):
        return path
    
    decompressed_path = path[:-3]  # Remove .gz
    if os.path.exists(decompressed_path):
        return decompressed_path
    
    print(f"Decompressing {path}...")
    with gzip.open(path, 'rb') as f_in:
        with open(decompressed_path, 'wb') as f_out:
            f_out.write(f_in.read())
    
    return decompressed_path


class EngineWrapper:
    """Wrapper around python-chess engine for unified interface."""
    
    def __init__(self, config: EngineConfig):
        self.config = config
        self.engine: Optional[chess.engine.UciProtocol] = None
        self._transport = None
    
    async def start(self) -> None:
        """Start the engine process."""
        self._transport, self.engine = await chess.engine.popen_uci(self.config.path)
        
        # Apply engine options
        for name, value in self.config.options.items():
            await self.engine.configure({name: value})
    
    async def play(
        self,
        board: chess.Board,
        limit: chess.engine.Limit
    ) -> chess.engine.PlayResult:
        """Get the engine's best move for the position."""
        if self.engine is None:
            raise RuntimeError("Engine not started")
        
        return await self.engine.play(board, limit)
    
    async def quit(self) -> None:
        """Quit the engine."""
        if self.engine:
            await self.engine.quit()
            self.engine = None


def create_stockfish_config(
    path: str = "stockfish",
    threads: int = 4,
    hash_mb: int = 256
) -> EngineConfig:
    """Create Stockfish engine configuration."""
    return EngineConfig(
        name="Stockfish",
        path=path,
        options={
            "Threads": threads,
            "Hash": hash_mb,
        }
    )


def create_lc0_config(
    path: str = "lc0",
    weights_path: str = None,
    backend: str = "metal",
    threads: int = 2
) -> EngineConfig:
    """Create LC0 engine configuration."""
    options = {
        "Backend": backend,
        "Threads": threads,
    }
    
    if weights_path:
        # Decompress if needed
        usable_path = decompress_weights_if_needed(weights_path)
        options["WeightsFile"] = usable_path
    
    return EngineConfig(
        name="LC0",
        path=path,
        options=options
    )


async def test_engine(config: EngineConfig) -> bool:
    """Test if an engine can be started and responds correctly."""
    try:
        wrapper = EngineWrapper(config)
        await wrapper.start()
        
        # Try to get a move from starting position
        board = chess.Board()
        result = await wrapper.play(board, chess.engine.Limit(nodes=1))
        
        await wrapper.quit()
        
        print(f"✓ {config.name} is working (sample move: {result.move})")
        return True
    except Exception as e:
        print(f"✗ {config.name} failed: {e}")
        return False
