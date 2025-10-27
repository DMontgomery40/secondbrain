"""OCR module exports for Second Brain."""

from .openai_ocr import OpenAIOCR
from .deepseek_ocr import DeepSeekOCR  # type: ignore F401

__all__ = ["OpenAIOCR", "DeepSeekOCR"]
