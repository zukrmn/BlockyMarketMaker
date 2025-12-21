import json
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class DataRecorder:
    """
    Recorder for logging high-volume market data to JSONL files for future AI analysis.
    Uses run_in_executor to avoid blocking the main asyncio loop during file I/O.
    """
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        if not os.path.isabs(data_dir):
            self.data_dir = os.path.abspath(data_dir)
        
        self.loop = asyncio.get_running_loop()
        self._ensure_dir()
        logger.info(f"DataRecorder initialized. Saving to: {self.data_dir}")

    def _ensure_dir(self):
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except OSError as e:
                logger.error(f"Failed to create data directory {self.data_dir}: {e}")

    def _append(self, filename: str, data: Dict[str, Any]):
        """Synchronous append to file."""
        try:
            filepath = os.path.join(self.data_dir, filename)
            # Add timestamp if not strictly present in desired format, or wrap it
            record = {
                "ts": datetime.utcnow().isoformat(),
                "data": data
            }
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            # Don't let logging crash the bot
            logger.error(f"DataRecorder Failed to write to {filename}: {e}")

    async def log_trade(self, market: str, trade_data: Dict[str, Any]):
        """Log a public trade execution."""
        await self.loop.run_in_executor(None, self._append, f"trades_{market}.jsonl", trade_data)

    async def log_orderbook(self, market: str, orderbook: Dict[str, Any]):
        """Log a snapshot of the orderbook."""
        await self.loop.run_in_executor(None, self._append, f"orderbook_{market}.jsonl", orderbook)
    
    async def log_ticker(self, market: str, ticker: Dict[str, Any]):
        """Log a ticker update."""
        await self.loop.run_in_executor(None, self._append, f"ticker_{market}.jsonl", ticker)
    
    async def log_snapshot(self, market: str, snapshot_data: Dict[str, Any]):
        """Log a general snapshot (metrics, strategies, etc.)."""
        await self.loop.run_in_executor(None, self._append, f"snapshot_{market}.jsonl", snapshot_data)
