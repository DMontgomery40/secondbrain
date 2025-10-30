"""Direct H.264 video capture service using macOS screen recording.

This captures directly to H.264 video segments instead of individual screenshots,
providing massive storage savings (99%+) while maintaining full functionality.
"""

import asyncio
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import structlog

from ..config import Config

logger = structlog.get_logger()


class VideoCaptureService:
    """Service for capturing screen directly to H.264 video segments."""
    
    def __init__(self, config: Optional[Config] = None):

        self.config = config or Config()
        self.config.ensure_directories()
        
        # Video storage
        self.video_dir = self.config.get_frames_dir().parent / "videos"
        self.video_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.segment_duration = self.config.get("video.segment_duration_minutes", 5) * 60
        self.fps = self.config.get("capture.fps", 1)
        
        # State
        self.running = False
        self.current_process: Optional[asyncio.subprocess.Process] = None
        self.current_segment_path: Optional[Path] = None
        self.segment_start_time: Optional[float] = None
        self.segments_created = 0
        
        logger.info(
            "video_capture_service_initialized",
            segment_duration_min=self.segment_duration / 60,
            fps=self.fps,
        )
    
    def _get_segment_path(self, timestamp: datetime) -> Path:
        """Get path for a video segment.
        
        Args:
            timestamp: Start timestamp for segment
            
        Returns:
            Path to video file
        """
        date_dir = self.video_dir / timestamp.strftime("%Y/%m/%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        filename = timestamp.strftime("%H-%M-%S") + ".mp4"
        return date_dir / filename
    
    async def _start_new_segment(self, timestamp: datetime) -> bool:
        """Start recording a new video segment.
        
        Args:
            timestamp: Start time for segment
            
        Returns:
            True if started successfully
        """
        segment_path = self._get_segment_path(timestamp)
        
        try:
            # Use ffmpeg to record screen directly to H.264
            # This captures the main display at specified FPS
            cmd = [
                "ffmpeg",
                "-f", "avfoundation",  # macOS screen capture
                "-framerate", str(self.fps),
                "-i", "1:none",  # Capture display 1, no audio
                "-c:v", "libx264",
                "-preset", "ultrafast",  # Fast encoding for real-time
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-t", str(self.segment_duration),  # Duration limit
                "-y",
                str(segment_path),
            ]
            
            self.current_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            self.current_segment_path = segment_path
            self.segment_start_time = time.time()
            
            logger.info(
                "video_segment_started",
                path=str(segment_path),
                duration_min=self.segment_duration / 60,
            )
            
            return True
            
        except Exception as e:
            logger.error("failed_to_start_segment", error=str(e))
            return False
    
    async def _finalize_segment(self) -> Optional[Path]:

        if not self.current_process or not self.current_segment_path:
            return None
        
        try:
            # Send SIGINT to gracefully stop ffmpeg
            self.current_process.send_signal(subprocess.signal.SIGINT)
            
            # Wait for process to finish
            await self.current_process.wait()
            
            # Check if file was created
            if self.current_segment_path.exists():
                file_size = self.current_segment_path.stat().st_size
                duration = time.time() - self.segment_start_time if self.segment_start_time else 0
                
                logger.info(
                    "video_segment_finalized",
                    path=str(self.current_segment_path),
                    size_mb=file_size / (1024 * 1024),
                    duration_sec=duration,
                )
                
                segment_path = self.current_segment_path
                self.segments_created += 1
                
                # Reset state
                self.current_process = None
                self.current_segment_path = None
                self.segment_start_time = None
                
                return segment_path
            
            return None
            
        except Exception as e:
            logger.error("failed_to_finalize_segment", error=str(e))
            return None
    
    async def capture_loop(self):

        logger.info("video_capture_loop_started")
        self.running = True
        
        while self.running:
            # Start new segment
            timestamp = datetime.now()
            if await self._start_new_segment(timestamp):
                # Wait for segment duration or until stopped
                start_time = time.time()
                while self.running and (time.time() - start_time) < self.segment_duration:
                    await asyncio.sleep(1)
                
                # Finalize segment
                await self._finalize_segment()
            else:
                # Failed to start, wait and retry
                await asyncio.sleep(5)
        
        # Finalize any remaining segment
        if self.current_process:
            await self._finalize_segment()
        
        logger.info("video_capture_loop_stopped", segments_created=self.segments_created)
    
    def stop(self):

        logger.info("stopping_video_capture_service")
        self.running = False
    
    def get_stats(self) -> Dict[str, Any]:

        return {
            "running": self.running,
            "segments_created": self.segments_created,
            "current_segment": str(self.current_segment_path) if self.current_segment_path else None,
            "segment_duration_min": self.segment_duration / 60,
        }
