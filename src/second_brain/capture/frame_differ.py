"""Frame difference detection for smart capture.

Detects when screen content changes significantly to avoid capturing
duplicate frames.
"""

from pathlib import Path
from typing import Optional

import structlog
from PIL import Image
import imagehash

logger = structlog.get_logger()


class FrameDiffer:
    """Detects significant changes between frames."""
    
    def __init__(self, similarity_threshold: float = 0.95):
        """Initialize frame differ.
        
        Args:
            similarity_threshold: Threshold for considering frames similar (0-1)
                                Higher = more similar required to skip
        """
        self.similarity_threshold = similarity_threshold
        self.last_hash: Optional[imagehash.ImageHash] = None
        self.frames_skipped = 0
        self.frames_captured = 0
        
        logger.info(
            "frame_differ_initialized",
            similarity_threshold=similarity_threshold
        )
    
    def should_capture_frame(self, image_path: Path) -> bool:
        """Determine if a frame should be captured based on content change.
        
        Args:
            image_path: Path to the current frame image
            
        Returns:
            True if frame should be captured, False if it's too similar to previous
        """
        try:
            # Load image and compute perceptual hash
            img = Image.open(image_path)
            current_hash = imagehash.average_hash(img, hash_size=16)
            
            # First frame - always capture
            if self.last_hash is None:
                self.last_hash = current_hash
                self.frames_captured += 1
                return True
            
            # Calculate similarity (0 = identical, higher = more different)
            difference = current_hash - self.last_hash
            max_difference = 256  # Maximum possible difference for 16x16 hash
            similarity = 1.0 - (difference / max_difference)
            
            # If similarity is above threshold, skip this frame
            if similarity >= self.similarity_threshold:
                self.frames_skipped += 1
                logger.debug(
                    "frame_skipped_similar",
                    similarity=similarity,
                    threshold=self.similarity_threshold,
                    total_skipped=self.frames_skipped
                )
                return False
            
            # Frame is different enough - capture it
            self.last_hash = current_hash
            self.frames_captured += 1
            logger.debug(
                "frame_captured_different",
                similarity=similarity,
                threshold=self.similarity_threshold
            )
            return True
            
        except Exception as e:
            logger.error("frame_diff_check_failed", error=str(e))
            # On error, capture the frame to be safe
            return True
    
    def get_stats(self) -> dict:

        total = self.frames_captured + self.frames_skipped
        skip_rate = (self.frames_skipped / total * 100) if total > 0 else 0
        
        return {
            "frames_captured": self.frames_captured,
            "frames_skipped": self.frames_skipped,
            "skip_rate_percent": skip_rate,
            "storage_saved_percent": skip_rate,
        }
