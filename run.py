#!/usr/bin/env python3
"""
BlockyMarketMaker - Entry Point

Run the Market Maker bot from the project root:
    python run.py

Or with module syntax:
    python -m src.main
"""
import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
