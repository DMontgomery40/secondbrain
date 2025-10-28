"""Apple Vision framework OCR implementation for macOS."""

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from Quartz import (
    CGImageSourceCreateWithURL,
    CGImageSourceCreateImageAtIndex,
)
from Vision import (
    VNRecognizeTextRequest,
    VNImageRequestHandler,
)
from Foundation import NSURL

from ..config import Config

logger = structlog.get_logger()


class AppleVisionOCR:
    """OCR service using Apple's Vision framework (local, fast, free)."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize Apple Vision OCR service.
        
        Args:
            config: Configuration instance. If None, uses global config.
        """
        self.config = config or Config()
        
        # Configuration
        self.recognition_level = self.config.get("ocr.recognition_level", "accurate")  # "fast" or "accurate"
        self.include_semantic_context = self.config.get("ocr.include_semantic_context", False)
        
        logger.info(
            "apple_vision_ocr_initialized",
            recognition_level=self.recognition_level,
            local=True,
            cost="free"
        )

    def _perform_ocr_sync(self, image_path: Path) -> List[str]:
        """Perform OCR synchronously using Vision framework.
        
        Args:
            image_path: Path to image file
            
        Returns:
            List of recognized text strings
        """
        try:
            # Create URL from path
            url = NSURL.fileURLWithPath_(str(image_path))
            
            # Create image source
            image_source = CGImageSourceCreateWithURL(url, None)
            if not image_source:
                logger.error("failed_to_create_image_source", path=str(image_path))
                return []
            
            # Get CGImage
            cg_image = CGImageSourceCreateImageAtIndex(image_source, 0, None)
            if not cg_image:
                logger.error("failed_to_get_cgimage", path=str(image_path))
                return []
            
            # Create text recognition request
            request = VNRecognizeTextRequest.alloc().init()
            
            # Set recognition level (fast or accurate)
            if self.recognition_level == "fast":
                request.setRecognitionLevel_(0)  # VNRequestTextRecognitionLevelFast
            else:
                request.setRecognitionLevel_(1)  # VNRequestTextRecognitionLevelAccurate
            
            # Create request handler
            handler = VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
            
            # Perform request
            success = handler.performRequests_error_([request], None)
            
            if not success[0]:
                logger.error("vision_request_failed", error=success[1])
                return []
            
            # Extract text from results
            results = request.results()
            if not results:
                return []
            
            text_lines = []
            for observation in results:
                # Get top candidate
                candidates = observation.topCandidates_(1)
                if candidates and len(candidates) > 0:
                    text_lines.append(candidates[0].string())
            
            return text_lines
            
        except Exception as e:
            logger.error("ocr_exception", error=str(e), path=str(image_path))
            return []

    async def extract_text(
        self, image_path: Path, frame_id: str
    ) -> List[Dict[str, Any]]:
        """Extract text from an image using Apple Vision framework.
        
        Args:
            image_path: Path to image file
            frame_id: Frame identifier
            
        Returns:
            List of text block dictionaries
        """
        if not image_path.exists():
            logger.error("image_not_found", path=str(image_path))
            return []
        
        try:
            # Run OCR in executor to avoid blocking
            loop = asyncio.get_event_loop()
            text_lines = await loop.run_in_executor(
                None,
                self._perform_ocr_sync,
                image_path
            )
            
            if not text_lines:
                logger.debug("no_text_found", frame_id=frame_id)
                return []
            
            # Combine all text lines
            full_text = "\n".join(text_lines)
            
            # Normalize text
            normalized_text = self._normalize_text(full_text)
            
            # Determine block type based on content
            block_type = self._determine_block_type(full_text)
            
            # Create text block
            text_block = {
                "block_id": str(uuid.uuid4()),
                "frame_id": frame_id,
                "text": full_text,
                "normalized_text": normalized_text,
                "confidence": 0.95,  # Vision framework is generally very accurate
                "block_type": block_type,
            }
            
            if self.include_semantic_context:
                text_block["semantic_context"] = f"Screen capture with {len(text_lines)} text lines"
            
            logger.info(
                "ocr_completed",
                frame_id=frame_id,
                text_length=len(full_text),
                lines=len(text_lines),
                block_type=block_type,
            )
            
            return [text_block]
            
        except Exception as e:
            logger.error(
                "ocr_failed",
                frame_id=frame_id,
                error=str(e),
            )
            return []

    def _determine_block_type(self, text: str) -> str:
        """Determine the type of content based on text patterns.
        
        Args:
            text: Extracted text
            
        Returns:
            Block type string
        """
        # Simple heuristics to determine content type
        lines = text.split('\n')
        
        # Check for code patterns
        code_indicators = ['def ', 'class ', 'import ', 'function ', 'const ', 'let ', 'var ', '{', '}', '=>']
        code_count = sum(1 for line in lines if any(indicator in line for indicator in code_indicators))
        
        if code_count > len(lines) * 0.3:
            return "code"
        
        # Check for terminal patterns
        terminal_indicators = ['$', '>', '~/', 'bash', 'zsh', 'python']
        terminal_count = sum(1 for line in lines if any(indicator in line for indicator in terminal_indicators))
        
        if terminal_count > len(lines) * 0.2:
            return "terminal"
        
        # Check for UI elements (short lines, buttons, labels)
        short_lines = sum(1 for line in lines if len(line.strip()) < 30)
        if short_lines > len(lines) * 0.5:
            return "ui_element"
        
        # Default to mixed
        return "mixed"

    def _normalize_text(self, text: str) -> str:
        """Normalize text by removing extra whitespace.
        
        Args:
            text: Raw text
            
        Returns:
            Normalized text
        """
        import re
        
        # Remove multiple spaces
        text = re.sub(r' +', ' ', text)
        
        # Remove multiple newlines (but keep paragraph breaks)
        text = re.sub(r'\n\n+', '\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text

    async def process_batch(
        self, image_paths: List[tuple[Path, str]]
    ) -> List[List[Dict[str, Any]]]:
        """Process a batch of images.
        
        Args:
            image_paths: List of (image_path, frame_id) tuples
        
        Returns:
            List of text block lists (one per image)
        """
        results = []
        for image_path, frame_id in image_paths:
            try:
                result = await self.extract_text(image_path, frame_id)
                results.append(result)
            except Exception as e:
                logger.error(
                    "batch_processing_error",
                    frame_id=frame_id,
                    error=str(e),
                )
                results.append([])
        return results

    async def close(self) -> None:
        """Cleanup (no resources to release for local OCR)."""
        pass
