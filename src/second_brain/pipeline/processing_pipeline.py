"""Processing pipeline that integrates capture, OCR, and storage."""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import deque

import structlog

from ..capture import CaptureService
from ..capture.screenshot_buffer import ScreenshotBuffer
from ..config import Config
from ..database import Database
from ..ocr import OpenAIOCR, DeepSeekOCR
# Lazy import EmbeddingService to avoid importing heavy deps unless enabled

logger = structlog.get_logger()


class ProcessingPipeline:
    """Pipeline that coordinates capture, OCR, and storage."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize processing pipeline.

        Args:
            config: Configuration instance. If None, uses global config.
        """
        self.config = config or Config()

        # Initialize components
        self.capture_service = CaptureService(self.config)

        # Simple OCR engine selection - one or the other, no hybrid
        ocr_engine = self.config.get("ocr.engine", "openai")
        logger.info("initializing_ocr_engine", engine=ocr_engine)

        if ocr_engine == "deepseek":
            self.ocr_service = DeepSeekOCR(self.config)
        else:
            # Default to OpenAI for any other value (including 'openai', 'hybrid', etc.)
            self.ocr_service = OpenAIOCR(self.config)

        self.database = Database(config=self.config)
        # Initialize embeddings lazily and only if enabled in config
        self.embedding_service = None
        if self.config.get("embeddings.enabled", True):
            try:
                from ..embeddings import EmbeddingService  # type: ignore
                self.embedding_service = EmbeddingService(self.config)
            except Exception as embed_init_err:
                logger.warning(
                    "embedding_service_init_failed", error=str(embed_init_err)
                )

        # No screenshot buffering - keep it simple
        self.screenshot_buffer = None
        
        # OCR queue
        self.ocr_queue: deque = deque()
        self.batch_size = self.config.get("ocr.batch_size", 5)
        
        # State
        self.running = False
        self.ocr_task: Optional[asyncio.Task] = None
        self.capture_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.stats = {
            "frames_captured": 0,
            "frames_processed": 0,
            "frames_failed": 0,
            "ocr_queue_size": 0,
        }
        
        logger.info("processing_pipeline_initialized", batch_size=self.batch_size)

    async def _capture_loop(self):
        """Capture loop that adds frames to OCR queue."""
        logger.info("capture_loop_started")
        
        interval = 1.0 / self.capture_service.fps
        
        while self.running:
            loop_start = asyncio.get_event_loop().time()
            
            # Capture frame
            metadata = await self.capture_service.capture_frame()
            
            if metadata:
                # Add to OCR queue
                frame_path = self.config.get_frames_dir() / metadata["file_path"]
                self.ocr_queue.append((frame_path, metadata))
                self.stats["frames_captured"] += 1
                self.stats["ocr_queue_size"] = len(self.ocr_queue)
                
                logger.debug(
                    "frame_queued_for_ocr",
                    frame_id=metadata["frame_id"],
                    queue_size=len(self.ocr_queue),
                )
            
            # Calculate sleep time to maintain FPS
            elapsed = asyncio.get_event_loop().time() - loop_start
            sleep_time = max(0, interval - elapsed)
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        logger.info("capture_loop_stopped")

    async def _ocr_loop(self):
        """OCR processing loop that processes frames from queue."""
        logger.info("ocr_loop_started")
        
        while self.running or len(self.ocr_queue) > 0:
            # Wait if queue is empty
            if len(self.ocr_queue) == 0:
                await asyncio.sleep(0.5)
                continue
            
            # Collect batch
            batch: List[tuple[Path, Dict[str, Any]]] = []
            while len(batch) < self.batch_size and len(self.ocr_queue) > 0:
                batch.append(self.ocr_queue.popleft())
            
            self.stats["ocr_queue_size"] = len(self.ocr_queue)
            
            if not batch:
                continue
            
            logger.info("processing_ocr_batch", batch_size=len(batch))
            
            # Process batch
            try:
                # Extract frame paths and IDs
                image_paths = [(path, metadata["frame_id"]) for path, metadata in batch]

                # Run OCR on batch - simple, no fallback
                results = await self.ocr_service.process_batch(image_paths)
                
                # Store results in database
                for (frame_path, metadata), text_blocks in zip(batch, results):
                    try:
                        # Insert frame metadata
                        self.database.insert_frame(metadata)
                        
                        # Insert text blocks if any
                        if text_blocks:
                            self.database.insert_text_blocks(text_blocks)
                            # Index embeddings after successful DB write
                            if self.embedding_service:
                                try:
                                    self.embedding_service.index_text_blocks(metadata, text_blocks)
                                except Exception as embed_error:
                                    logger.error(
                                        "embedding_index_failed",
                                        frame_id=metadata["frame_id"],
                                        error=str(embed_error),
                                    )
                        
                        # Update window tracking
                        self.database.update_window_tracking(
                            metadata["app_bundle_id"],
                            metadata["app_name"],
                            metadata["timestamp"],
                        )
                        
                        self.stats["frames_processed"] += 1
                        
                        logger.info(
                            "frame_processed",
                            frame_id=metadata["frame_id"],
                            text_blocks=len(text_blocks),
                        )
                        
                    except Exception as e:
                        self.stats["frames_failed"] += 1
                        logger.error(
                            "frame_storage_failed",
                            frame_id=metadata["frame_id"],
                            error=str(e),
                        )
                
            except Exception as e:
                self.stats["frames_failed"] += len(batch)
                logger.error("batch_processing_failed", error=str(e))
        
        logger.info("ocr_loop_stopped")

    async def start(self):
        """Start the processing pipeline."""
        if self.running:
            logger.warning("pipeline_already_running")
            return
        
        logger.info("starting_processing_pipeline")
        self.running = True
        
        # Start capture and OCR loops
        self.capture_task = asyncio.create_task(self._capture_loop())
        self.ocr_task = asyncio.create_task(self._ocr_loop())
        
        logger.info("processing_pipeline_started")

    async def stop(self):
        """Stop the processing pipeline."""
        if not self.running:
            logger.warning("pipeline_not_running")
            return
        
        logger.info("stopping_processing_pipeline")
        self.running = False
        
        # Wait for tasks to complete
        if self.capture_task:
            await self.capture_task
        
        if self.ocr_task:
            await self.ocr_task
        
        # Close database
        self.database.close()
        
        logger.info(
            "processing_pipeline_stopped",
            frames_captured=self.stats["frames_captured"],
            frames_processed=self.stats["frames_processed"],
            frames_failed=self.stats["frames_failed"],
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "running": self.running,
            "frames_captured": self.stats["frames_captured"],
            "frames_processed": self.stats["frames_processed"],
            "frames_failed": self.stats["frames_failed"],
            "ocr_queue_size": self.stats["ocr_queue_size"],
            "capture_stats": self.capture_service.get_stats(),
            "database_stats": self.database.get_database_stats(),
        }
