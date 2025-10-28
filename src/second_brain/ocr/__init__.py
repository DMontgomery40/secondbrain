"""OCR module for Second Brain supporting multiple OCR engines.

100% LOCAL - No cloud dependencies!

Available engines:
- AppleVisionOCR: Local, fast, free (macOS Vision framework) - DEFAULT
- DeepSeekOCR: Local, free, cutting-edge multimodal (MLX-VLM) - NEW!
"""

from .apple_vision_ocr import AppleVisionOCR
from .deepseek_ocr import DeepSeekOCR

# Default OCR is Apple Vision (local, fast, free, built-in)
OCR = AppleVisionOCR

__all__ = ["AppleVisionOCR", "DeepSeekOCR", "OCR"]
