"""Simple H.264 video capture using macOS native tools.

This uses a hybrid approach:
1. Capture frames as before (for OCR and instant access)
2. Periodically batch-convert frames to H.264 video segments
3. Delete original frames after successful conversion
"""

import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import structlog

from ..config import Config

logger = structlog.get_logger()


class VideoConverter:
    """Converts captured frames to H.264 video segments using ffmpeg."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize video converter.
        
        Args:
            config: Configuration instance
        """
        self.config = config or Config()
        self.frames_dir = self.config.get_frames_dir()
        self.video_dir = self.frames_dir.parent / "videos"
        self.video_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.segment_duration_minutes = self.config.get("video.segment_duration_minutes", 5)
        self.crf = self.config.get("video.crf", 23)  # 18-28, lower = better quality
        self.preset = self.config.get("video.preset", "medium")  # ultrafast, fast, medium, slow
        
        logger.info(
            "video_converter_initialized",
            segment_duration=self.segment_duration_minutes,
            crf=self.crf,
            preset=self.preset,
        )
    
    def _check_ffmpeg_available(self) -> bool:
        """Check if ffmpeg is installed.
        
        Returns:
            True if ffmpeg is available
        """
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def convert_frames_to_video(
        self,
        frame_paths: List[Path],
        output_path: Path,
        fps: float = 1.0,
    ) -> bool:
        """Convert a list of frames to H.264 video.
        
        Args:
            frame_paths: List of frame image paths (in order)
            output_path: Output video file path
            fps: Frames per second for the video
            
        Returns:
            True if conversion successful
        """
        if not frame_paths:
            logger.warning("no_frames_to_convert")
            return False
        
        if not self._check_ffmpeg_available():
            logger.error("ffmpeg_not_available")
            return False
        
        try:
            # Create a temporary file list for ffmpeg
            list_file = output_path.parent / f"{output_path.stem}_list.txt"
            
            with open(list_file, 'w') as f:
                for frame_path in frame_paths:
                    # ffmpeg concat demuxer format
                    f.write(f"file '{frame_path.absolute()}'\n")
                    f.write(f"duration {1.0/fps}\n")
                # Add last frame again for proper duration
                if frame_paths:
                    f.write(f"file '{frame_paths[-1].absolute()}'\n")
            
            # Run ffmpeg to create H.264 video
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-c:v", "libx264",
                "-preset", self.preset,
                "-crf", str(self.crf),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y",  # Overwrite output file
                str(output_path),
            ]
            
            logger.info(
                "starting_video_conversion",
                frames=len(frame_paths),
                output=str(output_path),
            )
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await result.communicate()
            
            # Clean up list file
            list_file.unlink(missing_ok=True)
            
            if result.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                original_size = sum(p.stat().st_size for p in frame_paths if p.exists())
                compression_ratio = (1 - file_size / original_size) * 100 if original_size > 0 else 0
                
                logger.info(
                    "video_conversion_successful",
                    frames=len(frame_paths),
                    output_size_mb=file_size / (1024 * 1024),
                    original_size_mb=original_size / (1024 * 1024),
                    compression_percent=compression_ratio,
                )
                return True
            else:
                logger.error(
                    "video_conversion_failed",
                    returncode=result.returncode,
                    stderr=stderr.decode() if stderr else None,
                )
                return False
                
        except Exception as e:
            logger.error("video_conversion_exception", error=str(e))
            return False
    
    async def convert_day_to_video(self, date: datetime) -> Optional[Path]:
        """Convert all frames from a specific day to video segments.
        
        Args:
            date: Date to convert
            
        Returns:
            Path to created video file or None
        """
        # Get all frames for the day
        day_dir = self.frames_dir / date.strftime("%Y/%m/%d")
        
        if not day_dir.exists():
            logger.warning("day_directory_not_found", date=date.strftime("%Y-%m-%d"))
            return None
        
        # Find all image files (png or webp)
        frame_files = sorted(day_dir.glob("*.png")) + sorted(day_dir.glob("*.webp"))
        
        if not frame_files:
            logger.warning("no_frames_found", date=date.strftime("%Y-%m-%d"))
            return None
        
        # Create output video path
        video_output_dir = self.video_dir / date.strftime("%Y/%m/%d")
        video_output_dir.mkdir(parents=True, exist_ok=True)
        output_path = video_output_dir / "full_day.mp4"
        
        # Convert to video
        success = await self.convert_frames_to_video(frame_files, output_path, fps=1.0)
        
        if success:
            # Optionally delete original frames to save space
            if self.config.get("video.delete_frames_after_conversion", False):
                for frame_file in frame_files:
                    try:
                        frame_file.unlink()
                        # Also delete corresponding JSON
                        json_file = frame_file.with_suffix('.json')
                        json_file.unlink(missing_ok=True)
                    except Exception as e:
                        logger.error("failed_to_delete_frame", file=str(frame_file), error=str(e))
            
            return output_path
        
        return None
