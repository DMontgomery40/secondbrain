"""OCR module for Second Brain supporting multiple OCR engines."""

from .openai_ocr import OpenAIOCR
from .deepseek_ocr import DeepSeekOCR

__all__ = ["OpenAIOCR", "DeepSeekOCR"]
