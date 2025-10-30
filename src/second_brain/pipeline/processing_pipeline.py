"""Processing pipeline that integrates capture, OCR, and storage."""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import deque

import structlog

from ..capture import CaptureService
from ..config import Config
from ..database import Database
from ..ocr import AppleVisionOCR
from ..summarization import SummarizationService

logger = structlog.get_logger()


class ProcessingPipeline:
    """Pipeline that coordinates capture, OCR, and storage."""

    def __init__(self, config: Optional[Config] = None):

        self.config = config or Config()
        
        # Initialize components
        self.capture_service = CaptureService(self.config)
        self.ocr_service = AppleVisionOCR(self.config)
        self.database = Database(config=self.config)
        
        # Initialize embedding service (optional - may have compatibility issues)
        self.embedding_service: Optional[object] = None
        try:
            from ..embeddings import EmbeddingService
            self.embedding_service = EmbeddingService(self.config)
        except Exception as e:
            logger.warning("embedding_service_disabled", reason=str(e))
        
        # Initialize summarization service (optional - requires API key)
        self.summarization_service: Optional[SummarizationService] = None
        try:
            self.summarization_service = SummarizationService(self.config)
        except ValueError as e:
            logger.warning("summarization_service_disabled", reason=str(e))
        
        # OCR queue
        self.ocr_queue: deque = deque()
        self.batch_size = self.config.get("ocr.batch_size", 5)
        
        # State
        self.running = False
        self.ocr_task: Optional[asyncio.Task] = None
        self.capture_task: Optional[asyncio.Task] = None
        self.summarization_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.stats = {
            "frames_captured": 0,
            "frames_processed": 0,
            "frames_failed": 0,
            "ocr_queue_size": 0,
        }
        
        logger.info("processing_pipeline_initialized", batch_size=self.batch_size)

    async def _capture_loop(self):

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
                
                # Run OCR on batch
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
                            try:
                                if self.embedding_service:
                                    self.embedding_service.index_text_blocks(metadata, text_blocks)
                            except Exception as embed_error:
                                # Only log as error if it's not a known compatibility issue
                                error_str = str(embed_error)
                                if "cached_download" in error_str or "url" in error_str:
                                    # Silently skip embedding for compatibility issues
                                    pass
                                else:
                                    logger.error(
                                        "embedding_index_failed",
                                        frame_id=metadata["frame_id"],
                                        error=error_str,
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

        if self.running:
            logger.warning("pipeline_already_running")
            return
        
        logger.info("starting_processing_pipeline")
        self.running = True
        
        # Start capture and OCR loops
        self.capture_task = asyncio.create_task(self._capture_loop())
        self.ocr_task = asyncio.create_task(self._ocr_loop())
        
        # Start summarization loop if enabled
        if self.summarization_service:
            self.summarization_task = asyncio.create_task(
                self.summarization_service.summarization_loop(self.database)
            )
            logger.info("summarization_loop_started")
        
        logger.info("processing_pipeline_started")

    async def stop(self):

        if not self.running:
            logger.warning("pipeline_not_running")
            return
        
        logger.info("stopping_processing_pipeline")
        self.running = False
        
        # Stop summarization service
        if self.summarization_service:
            self.summarization_service.stop()
        
        # Wait for tasks to complete
        if self.capture_task:
            await self.capture_task
        
        if self.ocr_task:
            await self.ocr_task
        
        if self.summarization_task:
            await self.summarization_task

        # Close services
        try:
            await self.ocr_service.close()
        except Exception as error:
            logger.warning("ocr_service_close_failed", error=str(error))
        
        if self.summarization_service:
            try:
                await self.summarization_service.close()
            except Exception as error:
                logger.warning("summarization_service_close_failed", error=str(error))

        # Close database
        self.database.close()
        
        logger.info(
            "processing_pipeline_stopped",
            frames_captured=self.stats["frames_captured"],
            frames_processed=self.stats["frames_processed"],
            frames_failed=self.stats["frames_failed"],
        )

    def get_stats(self) -> Dict[str, Any]:

        return {
            "running": self.running,
            "frames_captured": self.stats["frames_captured"],
            "frames_processed": self.stats["frames_processed"],
            "frames_failed": self.stats["frames_failed"],
            "ocr_queue_size": self.stats["ocr_queue_size"],
            "capture_stats": self.capture_service.get_stats(),
            "database_stats": self.database.get_database_stats(),
        }
