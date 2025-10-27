"""Hybrid OCR engine that routes work between DeepSeek and OpenAI."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List

import structlog

from .openai_ocr import OpenAIOCR
from .deepseek_ocr import DeepSeekOCR

logger = structlog.get_logger()


class HybridOCR:
    """Routes a portion of work to DeepSeek and the rest to OpenAI.

    The `ratio` determines the fraction processed by DeepSeek (0.0..1.0).
    """

    def __init__(self, primary: DeepSeekOCR, fallback: OpenAIOCR, ratio: float = 0.5):
        self.primary = primary
        self.fallback = fallback
        self.ratio = max(0.0, min(1.0, ratio))

    async def process_batch(self, image_paths: List[tuple[Path, str]]) -> List[List[Dict[str, Any]]]:
        n = len(image_paths)
        k = int(math.ceil(n * self.ratio))
        # Split deterministically to keep ordering predictable
        primary_items = list(enumerate(image_paths[:k]))
        fallback_items = list(enumerate(image_paths[k:], start=k))

        # Process each subset
        primary_results = await self.primary.process_batch([item for _, item in primary_items]) if primary_items else []
        fallback_results = await self.fallback.process_batch([item for _, item in fallback_items]) if fallback_items else []

        # Merge back preserving original order
        results: List[List[Dict[str, Any]]] = [None] * n  # type: ignore
        for (idx, _), res in zip(primary_items, primary_results):
            # Inject engine label explicitly for observability
            for block in res:
                block.setdefault("ocr_engine", "deepseek")
            results[idx] = res
        for (idx, _), res in zip(fallback_items, fallback_results):
            for block in res:
                block.setdefault("ocr_engine", "openai")
            results[idx] = res

        # mypy hinting: results should be fully filled
        return results

