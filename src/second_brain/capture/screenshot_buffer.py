"""
Screenshot buffering for batch processing.
Works alongside existing capture_service.py to enable efficient batch OCR.
"""

import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger()


@dataclass
class BufferedFrame:
    """Represents a buffered screenshot frame."""
    path: Path
    frame_id: str
    timestamp: datetime
    app_bundle_id: Optional[str]
    window_title: Optional[str]


class ScreenshotBuffer:
    """Buffer screenshots for batch OCR processing."""

    def __init__(
        self,
        duration_seconds: int = 30,
        max_size: int = 30,
        min_flush_size: int = 10
    ):
        """Initialize screenshot buffer.

        Args:
            duration_seconds: Maximum time to buffer before flushing
            max_size: Maximum number of frames to buffer
            min_flush_size: Minimum frames before time-based flush
        """
        self.buffer: deque[BufferedFrame] = deque(maxlen=max_size)
        self.duration = duration_seconds
        self.max_size = max_size
        self.min_flush_size = min_flush_size
        self.last_flush = time.time()

        logger.info(
            "screenshot_buffer_initialized",
            duration_seconds=duration_seconds,
            max_size=max_size,
            min_flush_size=min_flush_size
        )

    def add(
        self,
        frame_path: Path,
        frame_id: str,
        metadata: Dict
    ) -> bool:
        """Add frame to buffer.

        Args:
            frame_path: Path to screenshot file
            frame_id: Frame identifier
            metadata: Frame metadata dict

        Returns:
            True if buffer should be flushed, False otherwise
        """
        frame = BufferedFrame(
            path=frame_path,
            frame_id=frame_id,
            timestamp=datetime.now(),
            app_bundle_id=metadata.get('app_bundle_id'),
            window_title=metadata.get('window_title')
        )

        self.buffer.append(frame)

        should_flush = self.should_flush()

        if should_flush:
            logger.debug(
                "buffer_ready_to_flush",
                buffer_size=len(self.buffer),
                time_since_flush=time.time() - self.last_flush
            )

        return should_flush

    def should_flush(self) -> bool:
        """Determine if buffer should be processed.

        Returns:
            True if buffer should be flushed
        """
        if not self.buffer:
            return False

        buffer_size = len(self.buffer)
        time_elapsed = time.time() - self.last_flush

        # Flush if buffer is full
        if buffer_size >= self.max_size:
            logger.debug("flush_triggered_by_size", buffer_size=buffer_size)
            return True

        # Flush if time elapsed and we have minimum frames
        if time_elapsed >= self.duration and buffer_size >= self.min_flush_size:
            logger.debug(
                "flush_triggered_by_time",
                time_elapsed=time_elapsed,
                buffer_size=buffer_size
            )
            return True

        return False

    def get_batch(self) -> List[Tuple[Path, str]]:
        """Get all buffered frames and clear buffer.

        Returns:
            List of (frame_path, frame_id) tuples
        """
        batch = [(frame.path, frame.frame_id) for frame in self.buffer]

        logger.info(
            "buffer_flushed",
            batch_size=len(batch),
            time_since_last_flush=time.time() - self.last_flush
        )

        self.buffer.clear()
        self.last_flush = time.time()

        return batch

    def get_buffered_frames(self) -> List[BufferedFrame]:
        """Get all buffered frames without clearing.

        Returns:
            List of BufferedFrame objects
        """
        return list(self.buffer)

    def size(self) -> int:
        """Get current buffer size.

        Returns:
            Number of frames in buffer
        """
        return len(self.buffer)

    def is_empty(self) -> bool:
        """Check if buffer is empty.

        Returns:
            True if buffer is empty
        """
        return len(self.buffer) == 0

    def clear(self) -> None:
        """Clear the buffer without processing."""
        count = len(self.buffer)
        self.buffer.clear()
        self.last_flush = time.time()

        if count > 0:
            logger.info("buffer_cleared", frames_discarded=count)

    def time_since_flush(self) -> float:
        """Get seconds since last flush.

        Returns:
            Seconds since last flush
        """
        return time.time() - self.last_flush

    def force_flush(self) -> List[Tuple[Path, str]]:
        """Force flush buffer regardless of size or time.

        Returns:
            List of (frame_path, frame_id) tuples
        """
        if self.is_empty():
            return []

        logger.info("buffer_force_flushed", batch_size=len(self.buffer))
        return self.get_batch()
