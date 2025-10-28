"""Activity monitoring for adaptive FPS.

Detects user activity (keyboard/mouse) to adjust capture frame rate.
"""

import time
from typing import Optional

import structlog
from Quartz import (
    CGEventSourceSecondsSinceLastEventType,
    kCGEventSourceStateHIDSystemState,
    kCGAnyInputEventType,
)

logger = structlog.get_logger()


class ActivityMonitor:
    """Monitors user activity to enable adaptive FPS."""
    
    def __init__(
        self,
        idle_threshold_seconds: float = 30.0,
        active_fps: float = 1.0,
        idle_fps: float = 0.2,
    ):
        """Initialize activity monitor.
        
        Args:
            idle_threshold_seconds: Seconds of inactivity before considered idle
            active_fps: FPS when user is active
            idle_fps: FPS when user is idle
        """
        self.idle_threshold = idle_threshold_seconds
        self.active_fps = active_fps
        self.idle_fps = idle_fps
        self.last_activity_time = time.time()
        
        logger.info(
            "activity_monitor_initialized",
            idle_threshold=idle_threshold_seconds,
            active_fps=active_fps,
            idle_fps=idle_fps,
        )
    
    def get_seconds_since_last_input(self) -> float:
        """Get seconds since last keyboard/mouse input.
        
        Returns:
            Seconds since last input event
        """
        try:
            # Get seconds since last input event (keyboard or mouse)
            seconds = CGEventSourceSecondsSinceLastEventType(
                kCGEventSourceStateHIDSystemState,
                kCGAnyInputEventType
            )
            return seconds
        except Exception as e:
            logger.error("failed_to_get_input_time", error=str(e))
            return 0.0
    
    def is_user_active(self) -> bool:
        """Check if user is currently active.
        
        Returns:
            True if user is active, False if idle
        """
        seconds_idle = self.get_seconds_since_last_input()
        return seconds_idle < self.idle_threshold
    
    def get_adaptive_fps(self) -> float:
        """Get the appropriate FPS based on current activity.
        
        Returns:
            FPS value (active_fps or idle_fps)
        """
        if self.is_user_active():
            return self.active_fps
        else:
            return self.idle_fps
    
    def get_stats(self) -> dict:
        """Get activity monitor statistics.
        
        Returns:
            Dictionary with statistics
        """
        seconds_idle = self.get_seconds_since_last_input()
        is_active = seconds_idle < self.idle_threshold
        current_fps = self.active_fps if is_active else self.idle_fps
        
        return {
            "is_active": is_active,
            "seconds_idle": seconds_idle,
            "current_fps": current_fps,
            "active_fps": self.active_fps,
            "idle_fps": self.idle_fps,
        }
