"""Screen capture service for Second Brain."""

import asyncio
import json
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import psutil
import structlog
from Quartz import (
    CGWindowListCopyWindowInfo,
    CGDisplayBounds,
    CGMainDisplayID,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
)

from ..config import Config
from .frame_differ import FrameDiffer
from .activity_monitor import ActivityMonitor

logger = structlog.get_logger()


class CaptureService:
    """Service for capturing screenshots and window metadata."""

    def __init__(self, config: Optional[Config] = None):

        self.config = config or Config()
        self.config.ensure_directories()
        self.frames_dir = self.config.get_frames_dir()
        
        # Configuration
        self.fps = self.config.get("capture.fps", 1)
        self.format = self.config.get("capture.format", "webp")  # WebP for 25-35% savings
        self.quality = self.config.get("capture.quality", 85)
        self.max_disk_usage_gb = self.config.get("capture.max_disk_usage_gb", 100)
        self.min_free_space_gb = self.config.get("capture.min_free_space_gb", 10)
        
        # Smart capture - frame change detection
        self.enable_frame_diff = self.config.get("capture.enable_frame_diff", True)
        self.frame_differ: Optional[FrameDiffer] = None
        if self.enable_frame_diff:
            similarity_threshold = self.config.get("capture.similarity_threshold", 0.95)
            self.frame_differ = FrameDiffer(similarity_threshold=similarity_threshold)
        
        # Adaptive FPS - adjust capture rate based on activity
        self.enable_adaptive_fps = self.config.get("capture.enable_adaptive_fps", True)
        self.activity_monitor: Optional[ActivityMonitor] = None
        if self.enable_adaptive_fps:
            idle_threshold = self.config.get("capture.idle_threshold_seconds", 30.0)
            idle_fps = self.config.get("capture.idle_fps", 0.2)
            self.activity_monitor = ActivityMonitor(
                idle_threshold_seconds=idle_threshold,
                active_fps=self.fps,
                idle_fps=idle_fps,
            )
        
        # State
        self.running = False
        self.frames_captured = 0
        self.frames_skipped = 0
        self.last_capture_time = 0.0
        self._screen_resolution_cache: Optional[str] = None
        self._frames_dir_usage_bytes = self._calculate_frames_dir_size()
        
        logger.info(
            "capture_service_initialized",
            fps=self.fps,
            format=self.format,
            max_disk_gb=self.max_disk_usage_gb,
        )

    def _calculate_frames_dir_size(self) -> int:

        total_size = 0
        if not self.frames_dir.exists():
            return total_size
        for path in self.frames_dir.rglob("*"):
            if path.is_file():
                try:
                    total_size += path.stat().st_size
                except OSError:
                    continue
        return total_size

    def _get_active_window_info(self) -> Dict[str, Any]:

        try:
            # Get list of all windows
            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            )
            
            # Find the frontmost window (layer 0)
            for window in window_list:
                if window.get("kCGWindowLayer", -1) == 0:
                    owner_name = window.get("kCGWindowOwnerName", "Unknown")
                    window_name = window.get("kCGWindowName", "")
                    owner_pid = window.get("kCGWindowOwnerPID", 0)
                    
                    # Try to get bundle ID from process
                    bundle_id = "unknown"
                    try:
                        # Attempt to inspect the process; fall back to heuristic if unavailable
                        psutil.Process(owner_pid)
                        # Simplified heuristic for bundle id
                        bundle_id = f"com.{owner_name.lower().replace(' ', '')}"
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    
                    return {
                        "window_title": window_name or owner_name,
                        "app_name": owner_name,
                        "app_bundle_id": bundle_id,
                        "window_bounds": window.get("kCGWindowBounds", {}),
                    }
            
            return {
                "window_title": "Unknown",
                "app_name": "Unknown",
                "app_bundle_id": "unknown",
                "window_bounds": {},
            }
            
        except Exception as e:
            logger.error("failed_to_get_window_info", error=str(e))
            return {
                "window_title": "Unknown",
                "app_name": "Unknown",
                "app_bundle_id": "unknown",
                "window_bounds": {},
            }

    def _get_screen_resolution(self) -> str:

        if self._screen_resolution_cache:
            return self._screen_resolution_cache
        
        try:
            bounds = CGDisplayBounds(CGMainDisplayID())
            width = int(bounds.size.width)
            height = int(bounds.size.height)
            self._screen_resolution_cache = f"{width}x{height}"
            return self._screen_resolution_cache
        except Exception as error:
            logger.error("failed_to_get_resolution", error=str(error))
            # Fall back to system_profiler (only once)
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in result.stdout.split("\n"):
                    if "Resolution" in line:
                        parts = line.split(":")
                        if len(parts) > 1:
                            self._screen_resolution_cache = parts[1].strip().replace(" ", "")
                            return self._screen_resolution_cache
            except Exception as fallback_error:
                logger.error("resolution_fallback_failed", error=str(fallback_error))
        self._screen_resolution_cache = "unknown"
        return self._screen_resolution_cache

    def _check_disk_space(self) -> bool:

        try:
            # Get disk usage for the frames directory
            disk_usage = psutil.disk_usage(str(self.frames_dir))
            
            # Calculate free space in GB
            free_gb = disk_usage.free / (1024 ** 3)
            
            # Check if we have minimum free space
            if free_gb < self.min_free_space_gb:
                logger.warning(
                    "insufficient_disk_space",
                    free_gb=free_gb,
                    min_required_gb=self.min_free_space_gb,
                )
                return False
            
            # Check cached usage of frames directory
            total_gb = self._frames_dir_usage_bytes / (1024 ** 3)
            
            if total_gb > self.max_disk_usage_gb:
                logger.warning(
                    "max_disk_usage_exceeded",
                    total_gb=total_gb,
                    max_gb=self.max_disk_usage_gb,
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error("disk_space_check_failed", error=str(e))
            return True  # Continue on error

    def _get_frame_path(self, timestamp: datetime) -> Path:
        """Get the file path for a frame.
        
        Args:
            timestamp: Timestamp for the frame
            
        Returns:
            Path to save the frame
        """
        # Create directory structure: YYYY/MM/DD/
        date_dir = self.frames_dir / timestamp.strftime("%Y/%m/%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename: HH-MM-SS-mmm.png
        filename = timestamp.strftime("%H-%M-%S-%f")[:-3] + f".{self.format}"
        
        return date_dir / filename

    async def capture_frame(self) -> Optional[Dict[str, Any]]:

        # Check disk space
        if not self._check_disk_space():
            logger.warning("capture_paused_disk_space")
            return None
        
        # Generate frame ID and timestamp
        frame_id = str(uuid.uuid4())
        timestamp = datetime.now()
        unix_timestamp = int(timestamp.timestamp())
        
        # Get frame path
        frame_path = self._get_frame_path(timestamp)
        
        try:
            # Capture screenshot using screencapture (always outputs PNG)
            temp_png_path = frame_path.with_suffix('.png')
            result = subprocess.run(
                ["screencapture", "-x", str(temp_png_path)],
                capture_output=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                logger.error("screencapture_failed", returncode=result.returncode)
                return None
            
            # Convert to WebP if format is webp
            if self.format == "webp":
                try:
                    from PIL import Image
                    img = Image.open(temp_png_path)
                    img.save(frame_path, 'WEBP', quality=self.quality, method=6)
                    temp_png_path.unlink()  # Delete temp PNG
                except Exception as e:
                    logger.error("webp_conversion_failed", error=str(e))
                    # Fall back to PNG
                    frame_path = temp_png_path
            else:
                frame_path = temp_png_path
            
            # Check if frame should be kept (frame change detection)
            if self.frame_differ and not self.frame_differ.should_capture_frame(frame_path):
                # Frame is too similar to previous - delete it and skip
                frame_path.unlink()
                self.frames_skipped += 1
                return None
            
            # Get file size
            file_size = frame_path.stat().st_size
            self._frames_dir_usage_bytes += file_size
            
            # Get window info
            window_info = self._get_active_window_info()
            
            # Get screen resolution
            screen_resolution = self._get_screen_resolution()
            
            # Create metadata
            metadata = {
                "frame_id": frame_id,
                "timestamp": unix_timestamp,
                "iso_timestamp": timestamp.isoformat(),
                "window_title": window_info["window_title"],
                "app_bundle_id": window_info["app_bundle_id"],
                "app_name": window_info["app_name"],
                "file_path": str(frame_path.relative_to(self.frames_dir)),
                "file_size_bytes": file_size,
                "screen_resolution": screen_resolution,
            }
            
            # Save metadata JSON
            metadata_path = frame_path.with_suffix(".json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            try:
                self._frames_dir_usage_bytes += metadata_path.stat().st_size
            except OSError:
                pass
            
            self.frames_captured += 1
            self.last_capture_time = time.time()
            
            logger.info(
                "frame_captured",
                frame_id=frame_id,
                app=window_info["app_name"],
                size_kb=file_size // 1024,
            )
            
            return metadata
            
        except subprocess.TimeoutExpired:
            logger.error("screencapture_timeout")
            return None
        except Exception as e:
            logger.error("capture_failed", error=str(e))
            return None

    async def capture_loop(self):

        logger.info("capture_loop_started", fps=self.fps, adaptive_fps=self.enable_adaptive_fps)
        self.running = True
        
        while self.running:
            loop_start = time.time()
            
            # Get current FPS (adaptive or fixed)
            current_fps = self.fps
            if self.activity_monitor:
                current_fps = self.activity_monitor.get_adaptive_fps()
            
            interval = 1.0 / current_fps
            
            # Capture frame
            await self.capture_frame()
            
            # Calculate sleep time to maintain FPS
            elapsed = time.time() - loop_start
            sleep_time = max(0, interval - elapsed)
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        logger.info("capture_loop_stopped", total_frames=self.frames_captured, frames_skipped=self.frames_skipped)

    def stop(self):

        logger.info("stopping_capture_service")
        self.running = False

    def get_stats(self) -> Dict[str, Any]:

        stats = {
            "running": self.running,
            "frames_captured": self.frames_captured,
            "frames_skipped": self.frames_skipped,
            "fps": self.fps,
            "last_capture_time": self.last_capture_time,
            "uptime_seconds": time.time() - self.last_capture_time if self.last_capture_time > 0 else 0,
        }
        
        # Add frame differ stats if enabled
        if self.frame_differ:
            differ_stats = self.frame_differ.get_stats()
            stats["frame_differ"] = differ_stats
            stats["storage_saved_percent"] = differ_stats.get("storage_saved_percent", 0)
        
        # Add activity monitor stats if enabled
        if self.activity_monitor:
            activity_stats = self.activity_monitor.get_stats()
            stats["activity_monitor"] = activity_stats
            stats["current_fps"] = activity_stats.get("current_fps", self.fps)
        
        return stats
