"""
AgentSystem — Headless service entry point.

Run this script for unattended autonomous operation.
Usage: pythonw run_headless.py  (or python run_headless.py for console)
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.service import ServiceRunner, setup_signal_handlers


def setup_logging():
    """Configure logging for headless operation."""
    log_dir = Path(__file__).resolve().parent.parent / "memory"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)-20s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_dir / "service.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


async def main():
    setup_logging()
    logger = logging.getLogger("headless")

    runner = ServiceRunner(mode="headless")
    setup_signal_handlers(runner)

    logger.info("Starting AgentSystem in headless mode...")
    try:
        await runner.run_headless()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please update .env with valid LLM credentials.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
