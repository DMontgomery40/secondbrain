from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import monotonic
from typing import Deque, Tuple


@dataclass
class BufferedScreenshot:
    path: str
    timestamp: float


class ScreenshotBuffer:
    """Buffer screenshots for batch processing."""

    def __init__(self, buffer_duration: int = 30, maxlen: int = 60):
        self.buffer: Deque[BufferedScreenshot] = deque(maxlen=maxlen)
        self.buffer_duration = buffer_duration
        self._start = monotonic()

    def add(self, path: str) -> None:
        self.buffer.append(BufferedScreenshot(path=path, timestamp=monotonic()))

    def should_flush(self) -> bool:
        if len(self.buffer) == self.buffer.maxlen:
            return True
        return (monotonic() - self._start) >= self.buffer_duration

    def flush(self) -> list[str]:
        items = [item.path for item in list(self.buffer)]
        self.buffer.clear()
        self._start = monotonic()
        return items

