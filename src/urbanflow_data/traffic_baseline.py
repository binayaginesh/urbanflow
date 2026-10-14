"""
traffic_baseline – Stub (not yet implemented).
This file is a placeholder so the CLI can import it.
Implement the ``run(cfg, root, **kwargs)`` function.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def run(cfg: dict[str, Any], root: Path = Path("."), **kwargs) -> None:
    logger.warning("traffic_baseline.run() is not yet implemented.")
