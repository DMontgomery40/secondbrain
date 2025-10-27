"""DeepSeek OCR client that talks to a local Dockerized API.

This mirrors the async interface of OpenAIOCR: `extract_text` and `process_batch`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import structlog

from ..config import Config


logger = structlog.get_logger()


class DeepSeekOCR:
    """OCR service using a local DeepSeek-OCR HTTP API.

    Expects an API compatible with endpoints:
      - POST /ocr/image (multipart file)
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.base_url = self.config.get("ocr.deepseek_docker_url", "http://localhost:8001")
        self.timeout = self.config.get("ocr.timeout_seconds", 30)

    async def extract_text(self, image_path: Path, frame_id: str) -> List[Dict[str, Any]]:
        """Extract text for a single image via DeepSeek OCR API.

        Returns a list with a single text block dictionary to match the OpenAI path.
        """
        if not image_path.exists():
            logger.error("deepseek_image_not_found", path=str(image_path))
            return []

        url = f"{self.base_url}/ocr/image"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with open(image_path, "rb") as f:
                    files = {"file": (image_path.name, f, "image/png")}
                    resp = await client.post(url, files=files)

            if resp.status_code != 200:
                logger.error("deepseek_http_error", status=resp.status_code, text=resp.text)
                return []

            data = resp.json()
            text = data.get("result") or data.get("text") or ""
            if not isinstance(text, str):
                text = str(text)

            block: Dict[str, Any] = {
                "block_id": f"deepseek-{frame_id}",
                "frame_id": frame_id,
                "text": text,
                "normalized_text": self._normalize_text(text),
                "confidence": 0.95,
                "block_type": "mixed",
                "ocr_engine": "deepseek",
            }
            logger.info("deepseek_ocr_completed", frame_id=frame_id, text_len=len(text))
            return [block]
        except Exception as e:
            logger.error("deepseek_ocr_failed", error=str(e))
            return []

    async def process_batch(self, image_paths: List[tuple[Path, str]]) -> List[List[Dict[str, Any]]]:
        """Process a batch sequentially via the HTTP API."""
        results: List[List[Dict[str, Any]]] = []
        for path, frame_id in image_paths:
            try:
                results.append(await self.extract_text(path, frame_id))
            except Exception as exc:
                logger.error("deepseek_batch_error", frame_id=frame_id, error=str(exc))
                results.append([])
            # Be polite to the local server if needed
            await asyncio.sleep(0)
        return results

    def _normalize_text(self, text: str) -> str:
        import re

        text = re.sub(r" +", " ", text)
        text = re.sub(r"\n\n+", "\n\n", text)
        return text.strip()

