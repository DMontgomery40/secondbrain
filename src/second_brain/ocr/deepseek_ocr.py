"""
DeepSeek OCR engine - alternative to OpenAI Vision
Matches existing OCRResult interface for drop-in compatibility
"""

import asyncio
import base64
import io
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import structlog
from PIL import Image

from ..config import Config

logger = structlog.get_logger()


class DeepSeekOCR:
    """DeepSeek OCR implementation matching OpenAIOCR interface."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize DeepSeek OCR service.

        Args:
            config: Configuration instance. If None, uses global config.
        """
        self.config = config or Config()

        # Configuration (MLX backend only)
        self.model_id = self.config.get('ocr.deepseek_model', 'mlx-community/DeepSeek-OCR-4bit')
        self.mode = self.config.get('ocr.deepseek_mode', 'optimal')
        self.max_retries = self.config.get('ocr.max_retries', 3)
        self.timeout = self.config.get('ocr.timeout_seconds', 30)
        self.include_semantic_context = self.config.get('ocr.include_semantic_context', True)

        # Rate limiting (similar to OpenAI OCR)
        self.rate_limit_rpm = self.config.get('ocr.rate_limit_rpm', 50)
        self.min_request_interval = 60.0 / self.rate_limit_rpm
        self.last_request_time = 0.0
        self._rate_limit_lock = asyncio.Lock()

        # MLX state (lazy-loaded)
        self._mlx_model = None
        self._mlx_processor = None
        self._mlx_config = None
        self._mlx_loaded = False

        logger.info(
            "deepseek_ocr_initialized",
            backend="mlx",
            mode=self.mode,
            model_id=self.model_id,
        )

    def _encode_image(self, image_path: Path) -> str:
        """Encode image to base64.

        Args:
            image_path: Path to image file

        Returns:
            Base64 encoded image string
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _build_prompt(self) -> str:
        """Build the vision prompt for text extraction.

        Returns:
            Prompt string for DeepSeek OCR API
        """
        if self.include_semantic_context:
            return '<image>\n<|grounding|>Extract all visible text from this screenshot and provide semantic context about what is shown.'
        else:
            return '<image>\n<|grounding|>Convert the document to markdown.'

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        async with self._rate_limit_lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                logger.debug("rate_limiting", sleep_seconds=sleep_time)
                await asyncio.sleep(sleep_time)

            self.last_request_time = time.time()

    def _ensure_mlx_loaded(self) -> None:
        """Lazy-load MLX VLM model and processor."""
        if self._mlx_loaded:
            return
        try:
            # Import here to avoid hard dependency when using Docker backend
            from mlx_vlm import load as mlx_load
            from mlx_vlm.utils import load_config as mlx_load_config
            from mlx_vlm.prompt_utils import apply_chat_template

            model, processor = mlx_load(self.model_id)
            config = mlx_load_config(self.model_id)

            # Stash
            self._mlx_model = model
            self._mlx_processor = processor
            self._mlx_config = config
            self._mlx_apply_chat_template = apply_chat_template
            self._mlx_loaded = True

            logger.info("mlx_backend_loaded", model_id=self.model_id)
        except Exception as exc:
            logger.error("mlx_backend_load_failed", error=str(exc))
            raise

    def _process_via_mlx(self, image: Image.Image) -> Dict[str, Any]:
        """Run OCR using local MLX VLM backend.

        Returns a dict compatible with Docker response structure: {"result": str, "confidence": float, ...}
        """
        # Ensure model is loaded
        self._ensure_mlx_loaded()

        from mlx_vlm import generate as mlx_generate

        # Build prompt tuned for OCR; ask for plain text with structure
        if self.include_semantic_context:
            user_prompt = (
                "You are an OCR model. Read the entire screenshot and extract all visible text. "
                "Preserve order and logical grouping. Provide brief semantic context at the top under 'Context:'.\n\n"
                "Return plain text."
            )
        else:
            user_prompt = (
                "Extract all visible text from the image. Return plain text only."
            )

        # Apply chat template
        formatted = self._mlx_apply_chat_template(
            self._mlx_processor, self._mlx_config, user_prompt, num_images=1
        )

        # Run generation
        max_tokens = self.config.get('ocr.mlx_max_tokens', 1200)
        temperature = self.config.get('ocr.mlx_temperature', 0.0)

        output = mlx_generate(
            self._mlx_model,
            self._mlx_processor,
            formatted,
            [image],  # PIL Image list
            verbose=False,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Package result
        return {
            "result": str(output).strip(),
            "confidence": 0.92,  # heuristic baseline since model doesn't return scores
        }

    def _convert_to_text_blocks(self, deepseek_result: Dict[str, Any], frame_id: str) -> List[Dict[str, Any]]:
        """Convert DeepSeek format to text block format.

        Args:
            deepseek_result: Raw result from DeepSeek API
            frame_id: Frame identifier

        Returns:
            List of text block dictionaries
        """
        blocks = []

        if 'result' in deepseek_result:
            text = deepseek_result['result']

            # Parse markdown sections as blocks
            sections = re.split(r'\n#+\s', text)

            for idx, section in enumerate(sections):
                if section.strip():
                    # Create text block
                    text_block = {
                        "block_id": str(uuid.uuid4()),
                        "frame_id": frame_id,
                        "text": section.strip(),
                        "normalized_text": self._normalize_text(section.strip()),
                        "confidence": deepseek_result.get('confidence', 0.95),
                        "block_type": "text",
                    }

                    if self.include_semantic_context:
                        # Extract semantic context from the result
                        text_block["semantic_context"] = f"DeepSeek OCR extraction (section {idx + 1})"

                    blocks.append(text_block)

        # If no blocks were created, create a single block with all text
        if not blocks and 'result' in deepseek_result:
            text_block = {
                "block_id": str(uuid.uuid4()),
                "frame_id": frame_id,
                "text": deepseek_result['result'],
                "normalized_text": self._normalize_text(deepseek_result['result']),
                "confidence": deepseek_result.get('confidence', 0.95),
                "block_type": "mixed",
            }

            if self.include_semantic_context:
                text_block["semantic_context"] = "DeepSeek OCR extraction"

            blocks.append(text_block)

        return blocks

    async def extract_text(
        self, image_path: Path, frame_id: str
    ) -> List[Dict[str, Any]]:
        """Extract text from an image using DeepSeek OCR.

        Args:
            image_path: Path to image file
            frame_id: Frame identifier

        Returns:
            List of text block dictionaries
        """
        if not image_path.exists():
            logger.error("image_not_found", path=str(image_path))
            return []

        # Load image
        try:
            image = Image.open(image_path)
        except Exception as e:
            logger.error("image_loading_failed", path=str(image_path), error=str(e))
            return []

        # Retry logic
        for attempt in range(self.max_retries):
            try:
                # Rate limiting
                await self._rate_limit()

                # Make API call
                logger.debug("ocr_request_starting", frame_id=frame_id, attempt=attempt + 1, engine="deepseek")

                # Process via MLX backend
                result = self._process_via_mlx(image)

                # Convert to text blocks
                text_blocks = self._convert_to_text_blocks(result, frame_id)

                logger.info(
                    "ocr_completed",
                    frame_id=frame_id,
                    engine="deepseek",
                    text_length=len(result.get('result', '')),
                    block_count=len(text_blocks),
                    compression_ratio=result.get('compression_ratio', 10.0),
                )

                return text_blocks

            except requests.exceptions.Timeout as e:
                logger.warning(
                    "deepseek_timeout",
                    frame_id=frame_id,
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("ocr_failed_timeout", frame_id=frame_id)
                    return []

            except Exception as e:
                logger.error(
                    "ocr_unexpected_error",
                    frame_id=frame_id,
                    attempt=attempt + 1,
                    engine="deepseek",
                    error=str(e),
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    return []

        return []

    def _normalize_text(self, text: str) -> str:
        """Normalize text by removing extra whitespace.

        Args:
            text: Raw text

        Returns:
            Normalized text
        """
        # Remove multiple spaces
        text = re.sub(r' +', ' ', text)

        # Remove multiple newlines
        text = re.sub(r'\n\n+', '\n\n', text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    async def process_batch(
        self, image_paths: List[tuple[Path, str]]
    ) -> List[List[Dict[str, Any]]]:
        """Process a batch of images.

        This is a key feature of DeepSeek - batch processing with image combination
        reduces API costs by 10-20x compared to individual frame processing.

        Args:
            image_paths: List of (image_path, frame_id) tuples

        Returns:
            List of text block lists (one per image)
        """
        if not image_paths:
            return []

        if len(image_paths) == 1:
            return [await self.extract_text(image_paths[0][0], image_paths[0][1])]

        # Import image combiner
        from ..capture.image_combiner import combine_screenshot_files

        # Extract paths and frame IDs
        paths = [path for path, _ in image_paths]
        frame_ids = [frame_id for _, frame_id in image_paths]

        try:
            # Rate limiting
            await self._rate_limit()

            logger.debug("batch_ocr_starting", batch_size=len(image_paths), engine="deepseek")

            # Combine images
            combined_image = combine_screenshot_files(
                paths,
                strategy='vertical_stack',
                max_width=4096,
                max_height=4096,
                spacing=20
            )

            # Process combined image via MLX backend
            result = self._process_via_mlx(combined_image)

            # Parse the combined result
            combined_text = result.get('result', '')

            # Split result back to individual frames
            # The combined text should be split based on natural boundaries
            processed_results = self._split_batch_results(combined_text, frame_ids)

            logger.info(
                "batch_ocr_completed",
                batch_size=len(image_paths),
                engine="deepseek",
                total_text_length=len(combined_text),
                compression_ratio=result.get('compression_ratio', 10.0),
            )

            return processed_results

        except Exception as exc:
            logger.error(
                "batch_processing_error",
                batch_size=len(image_paths),
                error=str(exc),
            )
            # Fallback to individual processing
            logger.info("falling_back_to_individual_processing", batch_size=len(image_paths))
            processed_results = []
            for image_path, frame_id in image_paths:
                try:
                    processed_results.append(await self.extract_text(image_path, frame_id))
                except Exception as e:
                    logger.error("individual_processing_error", frame_id=frame_id, error=str(e))
                    processed_results.append([])
            return processed_results

    def _split_batch_results(
        self, combined_text: str, frame_ids: List[str]
    ) -> List[List[Dict[str, Any]]]:
        """Split combined OCR result back to individual frames.

        Args:
            combined_text: Combined text from all frames
            frame_ids: List of frame identifiers

        Returns:
            List of text block lists (one per frame)
        """
        # Split text into roughly equal chunks based on number of frames
        lines = combined_text.split('\n')
        lines_per_frame = max(1, len(lines) // len(frame_ids))

        results = []
        for idx, frame_id in enumerate(frame_ids):
            # Calculate line range for this frame
            start_line = idx * lines_per_frame
            if idx == len(frame_ids) - 1:
                # Last frame gets remaining lines
                end_line = len(lines)
            else:
                end_line = start_line + lines_per_frame

            # Extract text for this frame
            frame_text = '\n'.join(lines[start_line:end_line])

            if frame_text.strip():
                text_block = {
                    "block_id": str(uuid.uuid4()),
                    "frame_id": frame_id,
                    "text": frame_text,
                    "normalized_text": self._normalize_text(frame_text),
                    "confidence": 0.90,
                    "block_type": "text",
                }

                if self.include_semantic_context:
                    text_block["semantic_context"] = f"DeepSeek batch OCR (frame {idx + 1}/{len(frame_ids)})"

                results.append([text_block])
            else:
                results.append([])

        return results
