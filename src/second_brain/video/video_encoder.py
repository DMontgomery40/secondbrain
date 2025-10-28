"""H.264 video encoder using Apple's AVFoundation framework.

This module provides hardware-accelerated video encoding for efficient storage
of screen captures, similar to how Rewind handles video compression.
"""

import asyncio
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
from Foundation import (
    NSURL,
    NSMutableDictionary,
)
from AVFoundation import (
    AVAssetWriter,
    AVAssetWriterInput,
    AVAssetWriterInputPixelBufferAdaptor,
    AVFileTypeMPEG4,
    AVVideoCodecTypeH264,
    AVVideoCodecKey,
    AVVideoWidthKey,
    AVVideoHeightKey,
    AVVideoCompressionPropertiesKey,
    AVVideoAverageBitRateKey,
    AVVideoProfileLevelKey,
    AVVideoProfileLevelH264HighAutoLevel,
)
from CoreMedia import (
    CMTimeMake,
    CMTimeMakeWithSeconds,
    kCMPixelFormat_32ARGB,
)
from CoreVideo import (
    CVPixelBufferCreate,
    CVPixelBufferLockBaseAddress,
    CVPixelBufferUnlockBaseAddress,
    CVPixelBufferGetBaseAddress,
    kCVPixelBufferCGImageCompatibilityKey,
    kCVPixelBufferCGBitmapContextCompatibilityKey,
)
from Quartz import (
    CGImageGetWidth,
    CGImageGetHeight,
    CGImageGetDataProvider,
    CGDataProviderCopyData,
    CGImageSourceCreateWithURL,
    CGImageSourceCreateImageAtIndex,
)

from ..config import Config

logger = structlog.get_logger()


class VideoSegment:
    """Represents a video segment (5-minute chunk)."""
    
    def __init__(self, segment_id: str, start_time: datetime, video_path: Path):
        self.segment_id = segment_id
        self.start_time = start_time
        self.video_path = video_path
        self.frame_count = 0
        self.duration_seconds = 0.0
        self.file_size_bytes = 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "segment_id": self.segment_id,
            "start_time": int(self.start_time.timestamp()),
            "video_path": str(self.video_path),
            "frame_count": self.frame_count,
            "duration_seconds": self.duration_seconds,
            "file_size_bytes": self.file_size_bytes,
        }


class H264VideoEncoder:
    """Hardware-accelerated H.264 video encoder for screen captures."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize video encoder.
        
        Args:
            config: Configuration instance
        """
        self.config = config or Config()
        
        # Configuration
        self.segment_duration = self.config.get("video.segment_duration_minutes", 5) * 60
        self.bitrate = self.config.get("video.bitrate_mbps", 2) * 1_000_000  # Convert to bps
        self.fps = self.config.get("capture.fps", 1)
        
        # State
        self.current_writer: Optional[AVAssetWriter] = None
        self.current_input: Optional[AVAssetWriterInput] = None
        self.current_adaptor: Optional[AVAssetWriterInputPixelBufferAdaptor] = None
        self.current_segment: Optional[VideoSegment] = None
        self.segment_start_time: Optional[float] = None
        self.frame_number = 0
        
        # Video directory
        self.video_dir = self.config.get_frames_dir().parent / "videos"
        self.video_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            "h264_encoder_initialized",
            segment_duration_min=self.segment_duration / 60,
            bitrate_mbps=self.bitrate / 1_000_000,
            hardware_accelerated=True,
        )
    
    def _create_new_segment(self, timestamp: datetime) -> VideoSegment:
        """Create a new video segment.
        
        Args:
            timestamp: Start timestamp for the segment
            
        Returns:
            New VideoSegment instance
        """
        # Generate segment ID
        segment_id = hashlib.md5(
            f"{timestamp.isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Create video path: videos/YYYY/MM/DD/HH-MM-SS.mp4
        date_dir = self.video_dir / timestamp.strftime("%Y/%m/%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        video_path = date_dir / f"{timestamp.strftime('%H-%M-%S')}.mp4"
        
        segment = VideoSegment(segment_id, timestamp, video_path)
        logger.info("new_video_segment_created", segment_id=segment_id, path=str(video_path))
        
        return segment
    
    def _create_video_writer(
        self, 
        output_path: Path, 
        width: int, 
        height: int
    ) -> Tuple[AVAssetWriter, AVAssetWriterInput, AVAssetWriterInputPixelBufferAdaptor]:
        """Create AVAssetWriter for H.264 encoding.
        
        Args:
            output_path: Path to output video file
            width: Video width
            height: Video height
            
        Returns:
            Tuple of (writer, input, adaptor)
        """
        # Create output URL
        url = NSURL.fileURLWithPath_(str(output_path))
        
        # Create asset writer
        writer = AVAssetWriter.alloc().initWithURL_fileType_error_(
            url, AVFileTypeMPEG4, None
        )[0]
        
        if not writer:
            raise RuntimeError("Failed to create AVAssetWriter")
        
        # Configure video settings for H.264
        video_settings = NSMutableDictionary.dictionary()
        video_settings[AVVideoCodecKey] = AVVideoCodecTypeH264
        video_settings[AVVideoWidthKey] = width
        video_settings[AVVideoHeightKey] = height
        
        # Compression properties
        compression_props = NSMutableDictionary.dictionary()
        compression_props[AVVideoAverageBitRateKey] = self.bitrate
        compression_props[AVVideoProfileLevelKey] = AVVideoProfileLevelH264HighAutoLevel
        video_settings[AVVideoCompressionPropertiesKey] = compression_props
        
        # Create writer input
        writer_input = AVAssetWriterInput.alloc().initWithMediaType_outputSettings_(
            "vide",  # AVMediaTypeVideo
            video_settings
        )
        writer_input.setExpectsMediaDataInRealTime_(False)
        
        # Create pixel buffer adaptor
        source_pixel_buffer_attributes = {
            str(kCVPixelBufferCGImageCompatibilityKey): True,
            str(kCVPixelBufferCGBitmapContextCompatibilityKey): True,
        }
        
        adaptor = AVAssetWriterInputPixelBufferAdaptor.alloc().initWithAssetWriterInput_sourcePixelBufferAttributes_(
            writer_input,
            source_pixel_buffer_attributes
        )
        
        # Add input to writer
        if writer.canAddInput_(writer_input):
            writer.addInput_(writer_input)
        else:
            raise RuntimeError("Cannot add input to AVAssetWriter")
        
        # Start writing
        if not writer.startWriting():
            raise RuntimeError(f"Failed to start writing: {writer.error()}")
        
        writer.startSessionAtSourceTime_(CMTimeMake(0, self.fps))
        
        return writer, writer_input, adaptor
    
    def _image_to_pixel_buffer(self, image_path: Path, width: int, height: int):
        """Convert image to CVPixelBuffer.
        
        Args:
            image_path: Path to image file
            width: Target width
            height: Target height
            
        Returns:
            CVPixelBuffer or None
        """
        try:
            # Load image
            url = NSURL.fileURLWithPath_(str(image_path))
            image_source = CGImageSourceCreateWithURL(url, None)
            if not image_source:
                logger.error("failed_to_load_image", path=str(image_path))
                return None
            
            cg_image = CGImageSourceCreateImageAtIndex(image_source, 0, None)
            if not cg_image:
                logger.error("failed_to_create_cgimage", path=str(image_path))
                return None
            
            # Create pixel buffer
            pixel_buffer = CVPixelBufferCreate(
                None,
                width,
                height,
                kCMPixelFormat_32ARGB,
                {
                    str(kCVPixelBufferCGImageCompatibilityKey): True,
                    str(kCVPixelBufferCGBitmapContextCompatibilityKey): True,
                },
                None
            )[1]
            
            if not pixel_buffer:
                logger.error("failed_to_create_pixel_buffer")
                return None
            
            # Lock pixel buffer
            CVPixelBufferLockBaseAddress(pixel_buffer, 0)
            
            # Get pixel data
            base_address = CVPixelBufferGetBaseAddress(pixel_buffer)
            
            # Copy image data to pixel buffer
            # This is a simplified version - in production you'd use CGBitmapContext
            data_provider = CGImageGetDataProvider(cg_image)
            data = CGDataProviderCopyData(data_provider)
            
            # Unlock pixel buffer
            CVPixelBufferUnlockBaseAddress(pixel_buffer, 0)
            
            return pixel_buffer
            
        except Exception as e:
            logger.error("image_to_pixel_buffer_failed", error=str(e))
            return None
    
    async def add_frame(
        self, 
        image_path: Path, 
        timestamp: datetime,
        width: int,
        height: int
    ) -> Optional[str]:
        """Add a frame to the current video segment.
        
        Args:
            image_path: Path to the frame image
            timestamp: Frame timestamp
            width: Frame width
            height: Frame height
            
        Returns:
            Segment ID if successful, None otherwise
        """
        try:
            # Check if we need to start a new segment
            if (self.current_segment is None or 
                self.segment_start_time is None or
                (time.time() - self.segment_start_time) >= self.segment_duration):
                
                # Finalize current segment if exists
                if self.current_segment:
                    await self._finalize_segment()
                
                # Create new segment
                self.current_segment = self._create_new_segment(timestamp)
                self.segment_start_time = time.time()
                self.frame_number = 0
                
                # Create video writer
                self.current_writer, self.current_input, self.current_adaptor = self._create_video_writer(
                    self.current_segment.video_path,
                    width,
                    height
                )
            
            # Convert image to pixel buffer
            pixel_buffer = self._image_to_pixel_buffer(image_path, width, height)
            if not pixel_buffer:
                return None
            
            # Calculate presentation time
            presentation_time = CMTimeMake(self.frame_number, self.fps)
            
            # Append pixel buffer
            if self.current_adaptor and self.current_input:
                # Wait for input to be ready
                while not self.current_input.isReadyForMoreMediaData():
                    await asyncio.sleep(0.01)
                
                success = self.current_adaptor.appendPixelBuffer_withPresentationTime_(
                    pixel_buffer,
                    presentation_time
                )
                
                if success:
                    self.frame_number += 1
                    self.current_segment.frame_count += 1
                    self.current_segment.duration_seconds = self.frame_number / self.fps
                    
                    logger.debug(
                        "frame_added_to_video",
                        segment_id=self.current_segment.segment_id,
                        frame_number=self.frame_number
                    )
                    
                    return self.current_segment.segment_id
                else:
                    logger.error("failed_to_append_pixel_buffer")
                    return None
            
            return None
            
        except Exception as e:
            logger.error("add_frame_failed", error=str(e))
            return None
    
    async def _finalize_segment(self) -> Optional[VideoSegment]:
        """Finalize the current video segment.
        
        Returns:
            Finalized VideoSegment or None
        """
        if not self.current_segment or not self.current_writer:
            return None
        
        try:
            # Mark input as finished
            if self.current_input:
                self.current_input.markAsFinished()
            
            # Finish writing
            self.current_writer.finishWriting()
            
            # Get file size
            if self.current_segment.video_path.exists():
                self.current_segment.file_size_bytes = self.current_segment.video_path.stat().st_size
            
            logger.info(
                "video_segment_finalized",
                segment_id=self.current_segment.segment_id,
                frames=self.current_segment.frame_count,
                duration=self.current_segment.duration_seconds,
                size_mb=self.current_segment.file_size_bytes / (1024 * 1024),
            )
            
            segment = self.current_segment
            
            # Reset state
            self.current_writer = None
            self.current_input = None
            self.current_adaptor = None
            self.current_segment = None
            self.segment_start_time = None
            self.frame_number = 0
            
            return segment
            
        except Exception as e:
            logger.error("finalize_segment_failed", error=str(e))
            return None
    
    async def close(self):
        """Close the encoder and finalize any pending segment."""
        if self.current_segment:
            await self._finalize_segment()
